#!/usr/bin/env python3
"""yt-dlp Bridge native messaging host.

Speaks the browser native-messaging protocol on stdin/stdout:
each message is a 4-byte native-endian length followed by UTF-8 JSON.
NOTHING else may be written to stdout.
"""
import json
import os
import re
import shutil
import signal
import struct
import subprocess
import sys
import tempfile
import threading
import uuid

VERSION = "1.0.0"
HERE = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(HERE, "config.json")

# Browsers start native hosts with a stripped-down PATH, so look in the usual places too.
EXTRA_DIRS = [
    "/opt/homebrew/bin", "/usr/local/bin", "/usr/bin", "/bin", "/snap/bin",
    os.path.expanduser("~/.local/bin"), os.path.expanduser("~/bin"),
    os.path.expanduser("~/.deno/bin"),
    os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\WinGet\Links"),
    os.path.expandvars(r"%ProgramData%\chocolatey\bin"),
    os.path.expandvars(r"%USERPROFILE%\scoop\shims"),
]

FORMATS = {
    "best": ["-f", "bv*[ext=mp4]+ba[ext=m4a]/bv*+ba/b", "--merge-output-format", "mp4"],
    "1080": ["-f", "bv*[height<=1080]+ba/b[height<=1080]", "--merge-output-format", "mp4"],
    "720": ["-f", "bv*[height<=720]+ba/b[height<=720]", "--merge-output-format", "mp4"],
    "480": ["-f", "bv*[height<=480]+ba/b[height<=480]", "--merge-output-format", "mp4"],
    "mp3": ["-x", "--audio-format", "mp3", "--audio-quality", "0"],
    "m4a": ["-x", "--audio-format", "m4a"],
}
COOKIE_BROWSERS = {"chrome", "chromium", "firefox", "edge", "brave", "opera", "safari", "vivaldi"}

_write_lock = threading.Lock()
_procs = {}
_cancelled = set()
_procs_lock = threading.Lock()


def load_config():
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def find_binary(name):
    cfg = load_config()
    configured = cfg.get(name.replace("-", "") + "_path") or cfg.get(name + "_path")
    if configured and os.path.isfile(configured):
        return configured
    search = os.pathsep.join([os.environ.get("PATH", "")] + [d for d in EXTRA_DIRS if d])
    return shutil.which(name, path=search)


def send(msg):
    data = json.dumps(msg).encode("utf-8")
    with _write_lock:
        sys.stdout.buffer.write(struct.pack("=I", len(data)))
        sys.stdout.buffer.write(data)
        sys.stdout.buffer.flush()


def read_message():
    raw = sys.stdin.buffer.read(4)
    if len(raw) < 4:
        return None
    (length,) = struct.unpack("=I", raw)
    data = sys.stdin.buffer.read(length)
    if len(data) < length:
        return None
    return json.loads(data.decode("utf-8"))


def tool_version(path, flag):
    try:
        out = subprocess.run([path, flag], capture_output=True, text=True, timeout=15)
        return (out.stdout or out.stderr).strip().splitlines()[0]
    except Exception:
        return None


def default_dir():
    cfg = load_config()
    return cfg.get("download_dir") or os.path.join(os.path.expanduser("~"), "Downloads", "yt-dlp-bridge")


def handle_ping(msg):
    ytdlp = find_binary("yt-dlp")
    ffmpeg = find_binary("ffmpeg")
    send({
        "type": "pong",
        "host_version": VERSION,
        "ytdlp": ytdlp,
        "ytdlp_version": tool_version(ytdlp, "--version") if ytdlp else None,
        "ffmpeg": ffmpeg,
        "download_dir": default_dir(),
    })


PCT = re.compile(r"\[download\]\s+(\d+(?:\.\d+)?)%")
SPEED = re.compile(r"\bat\s+(\S+/s)")
ETA = re.compile(r"\bETA\s+(\S+)")
DEST = [
    re.compile(r'\[download\] Destination: (.+)$'),
    re.compile(r'\[Merger\] Merging formats into "(.+)"$'),
    re.compile(r'\[ExtractAudio\] Destination: (.+)$'),
    re.compile(r'\[download\] (.+) has already been downloaded'),
]


def _force_kill(proc):
    if proc.poll() is None:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except Exception:
            proc.kill()


def kill_tree(proc):
    """Stop yt-dlp AND its children (ffmpeg, pip launcher shims)."""
    if proc.poll() is not None:
        return
    try:
        if os.name == "nt":
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                           capture_output=True, creationflags=0x08000000)
        else:
            os.killpg(proc.pid, signal.SIGTERM)
            threading.Timer(3, _force_kill, args=(proc,)).start()
    except Exception:
        proc.kill()


def run_download(job_id, msg):
    url = str(msg.get("url", "")).strip()
    if not re.match(r"^https?://", url, re.I):
        send({"type": "error", "id": job_id, "error": "That does not look like an http(s) link."})
        return
    ytdlp = find_binary("yt-dlp")
    if not ytdlp:
        send({"type": "error", "id": job_id,
              "error": "yt-dlp not found. Install it (pip install -U yt-dlp, brew install yt-dlp, "
                       "or winget install yt-dlp) and re-run install.py."})
        return

    fmt = msg.get("format", "best")
    if fmt not in FORMATS:
        fmt = "best"
    outdir = (msg.get("outdir") or "").strip() or default_dir()
    outdir = os.path.expanduser(outdir)
    try:
        os.makedirs(outdir, exist_ok=True)
    except OSError as e:
        send({"type": "error", "id": job_id, "error": f"Cannot use folder {outdir}: {e}"})
        return

    cmd = [ytdlp, "--newline", "--no-playlist", "--no-colors", "--ignore-config",
           "-P", outdir, "-o", "%(title).150B [%(id)s].%(ext)s"]
    ffmpeg = find_binary("ffmpeg")
    if ffmpeg:
        cmd += ["--ffmpeg-location", os.path.dirname(ffmpeg)]
    cmd += FORMATS[fmt]
    cookies = msg.get("cookies")
    cookie_file = None
    cookie_text = msg.get("cookie_text")
    if isinstance(cookie_text, str) and cookie_text.strip() and len(cookie_text) < 5_000_000:
        # Cookies sent by the extension itself: no browser database access needed.
        fd, cookie_file = tempfile.mkstemp(prefix="ytdlp-bridge-", suffix=".txt")  # mode 0600
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            f.write(cookie_text)
        cmd += ["--cookies", cookie_file]
    elif cookies in COOKIE_BROWSERS:
        cmd += ["--cookies-from-browser", cookies]
    cmd += ["--", url]

    def cleanup():
        if cookie_file:
            try:
                os.remove(cookie_file)
            except OSError:
                pass

    kwargs = {}
    if os.name == "nt":
        kwargs["creationflags"] = 0x08000000  # CREATE_NO_WINDOW
    else:
        kwargs["start_new_session"] = True  # own process group so cancel can kill the tree
    try:
        proc = subprocess.Popen(
            cmd, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", errors="replace", bufsize=1, **kwargs)
    except OSError as e:
        cleanup()
        send({"type": "error", "id": job_id, "error": f"Could not start yt-dlp: {e}"})
        return

    with _procs_lock:
        _procs[job_id] = proc
        already_cancelled = job_id in _cancelled
    send({"type": "started", "id": job_id, "outdir": outdir})
    if already_cancelled:  # cancel arrived before the process existed
        kill_tree(proc)

    filename = None
    last_lines = []
    for line in proc.stdout:
        line = line.rstrip("\r\n")
        if not line:
            continue
        last_lines = (last_lines + [line])[-6:]
        for rx in DEST:
            m = rx.search(line)
            if m:
                filename = m.group(1)
        m = PCT.search(line)
        if m:
            s, e = SPEED.search(line), ETA.search(line)
            send({"type": "progress", "id": job_id, "percent": float(m.group(1)),
                  "speed": s.group(1) if s else "", "eta": e.group(1) if e else ""})
        elif line.startswith("[") or line.startswith("ERROR"):
            send({"type": "log", "id": job_id, "line": line[:300]})

    code = proc.wait()
    cleanup()
    with _procs_lock:
        _procs.pop(job_id, None)
        cancelled = job_id in _cancelled
        _cancelled.discard(job_id)
    if cancelled and code != 0:
        send({"type": "cancelled", "id": job_id})
    elif code == 0:
        send({"type": "done", "id": job_id, "file": filename, "outdir": outdir})
    else:
        errs = [l for l in last_lines if l.startswith("ERROR")] or last_lines[-1:]
        text = (errs[-1] if errs else f"yt-dlp exited with code {code}")[:400]
        if "cookie database" in text.lower():
            text += "  Tip: choose \"This browser\" under Use login from instead."
        send({"type": "error", "id": job_id, "error": text})


def handle_cancel(msg):
    job_id = msg.get("id")
    with _procs_lock:
        _cancelled.add(job_id)
        proc = _procs.get(job_id)
    if proc:
        kill_tree(proc)


def main():
    if os.name == "nt":
        import msvcrt
        msvcrt.setmode(sys.stdin.fileno(), os.O_BINARY)
        msvcrt.setmode(sys.stdout.fileno(), os.O_BINARY)

    while True:
        try:
            msg = read_message()
        except Exception as e:  # malformed input
            send({"type": "error", "error": f"Bad message: {e}"})
            continue
        if msg is None:
            break
        action = msg.get("action")
        if action == "ping":
            handle_ping(msg)
        elif action == "download":
            job_id = msg.get("id") or uuid.uuid4().hex[:8]
            threading.Thread(target=run_download, args=(job_id, msg), daemon=True).start()
        elif action == "cancel":
            handle_cancel(msg)
        else:
            send({"type": "error", "error": f"Unknown action: {action}"})

    # Browser closed the connection: stop anything still running.
    with _procs_lock:
        for p in list(_procs.values()):
            kill_tree(p)
        _procs.clear()


if __name__ == "__main__":
    main()
