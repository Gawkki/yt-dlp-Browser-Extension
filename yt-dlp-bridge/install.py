#!/usr/bin/env python3
"""Register (or remove) the yt-dlp Bridge native messaging host.

    python install.py              # register for every browser it finds
    python install.py --browser chrome firefox
    python install.py --test       # check the host answers a ping
    python install.py --uninstall

The Chrome extension ID is fixed by the "key" in extension/manifest.json,
so you never have to copy an ID around.
"""
import argparse
import json
import os
import struct
import subprocess
import sys

HOST_NAME = "com.ytdlp_bridge.host"
CHROME_EXT_ID = "aihkkhgjlgelmdmkmbmlahamadifokdl"
FIREFOX_EXT_ID = "yt-dlp-bridge@local"
ROOT = os.path.dirname(os.path.abspath(__file__))
HOST_PY = os.path.join(ROOT, "host", "ytdlp_host.py")
IS_WIN = os.name == "nt"
IS_MAC = sys.platform == "darwin"
HOME = os.path.expanduser("~")

# browser -> (kind, unix dir that holds NativeMessagingHosts, windows registry key)
if IS_MAC:
    SUPPORT = os.path.join(HOME, "Library", "Application Support")
    UNIX_DIRS = {
        "chrome": ("chromium", os.path.join(SUPPORT, "Google", "Chrome")),
        "chromium": ("chromium", os.path.join(SUPPORT, "Chromium")),
        "brave": ("chromium", os.path.join(SUPPORT, "BraveSoftware", "Brave-Browser")),
        "edge": ("chromium", os.path.join(SUPPORT, "Microsoft Edge")),
        "vivaldi": ("chromium", os.path.join(SUPPORT, "Vivaldi")),
        "firefox": ("firefox", os.path.join(SUPPORT, "Mozilla")),
    }
    FIREFOX_SUBDIR = "NativeMessagingHosts"
else:
    CFG = os.path.join(HOME, ".config")
    UNIX_DIRS = {
        "chrome": ("chromium", os.path.join(CFG, "google-chrome")),
        "chromium": ("chromium", os.path.join(CFG, "chromium")),
        "brave": ("chromium", os.path.join(CFG, "BraveSoftware", "Brave-Browser")),
        "edge": ("chromium", os.path.join(CFG, "microsoft-edge")),
        "vivaldi": ("chromium", os.path.join(CFG, "vivaldi")),
        "firefox": ("firefox", os.path.join(HOME, ".mozilla")),
    }
    FIREFOX_SUBDIR = "native-messaging-hosts"

WIN_KEYS = {
    "chrome": ("chromium", r"Software\Google\Chrome\NativeMessagingHosts"),
    "chromium": ("chromium", r"Software\Chromium\NativeMessagingHosts"),
    "brave": ("chromium", r"Software\BraveSoftware\Brave-Browser\NativeMessagingHosts"),
    "edge": ("chromium", r"Software\Microsoft\Edge\NativeMessagingHosts"),
    "vivaldi": ("chromium", r"Software\Vivaldi\NativeMessagingHosts"),
    "firefox": ("firefox", r"Software\Mozilla\NativeMessagingHosts"),
}


def make_launcher():
    """Browsers need a single executable path; wrap 'python host.py' in a tiny script."""
    if IS_WIN:
        path = os.path.join(ROOT, "host", "run_host.bat")
        with open(path, "w", newline="\r\n") as f:
            f.write(f'@echo off\r\n"{sys.executable}" -u "{HOST_PY}"\r\n')
    else:
        path = os.path.join(ROOT, "host", "run_host.sh")
        with open(path, "w") as f:
            f.write(f'#!/bin/sh\nexec "{sys.executable}" -u "{HOST_PY}"\n')
        os.chmod(path, 0o755)
    os.chmod(HOST_PY, 0o755) if not IS_WIN else None
    return path


def manifest_for(kind, launcher):
    m = {
        "name": HOST_NAME,
        "description": "yt-dlp Bridge native host",
        "path": launcher,
        "type": "stdio",
    }
    if kind == "chromium":
        m["allowed_origins"] = [f"chrome-extension://{CHROME_EXT_ID}/"]
    else:
        m["allowed_extensions"] = [FIREFOX_EXT_ID]
    return m


def unix_target_dirs(browser):
    kind, base = UNIX_DIRS[browser]
    sub = FIREFOX_SUBDIR if kind == "firefox" else "NativeMessagingHosts"
    dirs = [(base, os.path.join(base, sub))]
    if not IS_MAC:  # snap-packaged browsers keep their config elsewhere
        snap = {"chromium": "chromium", "firefox": "firefox"}.get(browser)
        if snap and os.path.isdir(os.path.join(HOME, "snap", snap)):
            if browser == "firefox":
                sb = os.path.join(HOME, "snap", "firefox", "common", ".mozilla")
                dirs.append((sb, os.path.join(sb, "native-messaging-hosts")))
            else:
                sb = os.path.join(HOME, "snap", "chromium", "common", "chromium")
                dirs.append((sb, os.path.join(sb, "NativeMessagingHosts")))
    return dirs


def install(browsers, launcher):
    done = []
    for b in browsers:
        kind = UNIX_DIRS[b][0]
        manifest = manifest_for(kind, launcher)
        if IS_WIN:
            import winreg
            manifest_path = os.path.join(ROOT, "host", f"{HOST_NAME}.{kind}.json")
            with open(manifest_path, "w") as f:
                json.dump(manifest, f, indent=2)
            key = WIN_KEYS[b][1] + "\\" + HOST_NAME
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, key) as k:
                winreg.SetValueEx(k, "", 0, winreg.REG_SZ, manifest_path)
            done.append(f"{b}: HKCU\\{key}")
        else:
            for base, target in unix_target_dirs(b):
                if not os.path.isdir(base):
                    continue
                os.makedirs(target, exist_ok=True)
                p = os.path.join(target, HOST_NAME + ".json")
                with open(p, "w") as f:
                    json.dump(manifest, f, indent=2)
                done.append(f"{b}: {p}")
    return done


def uninstall(browsers):
    removed = []
    for b in browsers:
        if IS_WIN:
            import winreg
            try:
                winreg.DeleteKey(winreg.HKEY_CURRENT_USER, WIN_KEYS[b][1] + "\\" + HOST_NAME)
                removed.append(b)
            except OSError:
                pass
        else:
            for _, target in unix_target_dirs(b):
                p = os.path.join(target, HOST_NAME + ".json")
                if os.path.exists(p):
                    os.remove(p)
                    removed.append(p)
    return removed


def detect_browsers():
    if IS_WIN:
        return list(WIN_KEYS)  # registry keys are harmless for browsers you do not have
    return [b for b in UNIX_DIRS if any(os.path.isdir(base) for base, _ in unix_target_dirs(b))]


def test_host(launcher):
    """Start the host exactly as a browser would and send it a ping."""
    cmd = [launcher] if not IS_WIN else ["cmd", "/c", launcher]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            env={"PATH": "/usr/bin:/bin"} if not IS_WIN else None)
    payload = json.dumps({"action": "ping"}).encode()
    proc.stdin.write(struct.pack("=I", len(payload)) + payload)
    proc.stdin.flush()
    raw = proc.stdout.read(4)
    if len(raw) < 4:
        proc.kill()
        return None, proc.stderr.read().decode(errors="replace")
    (n,) = struct.unpack("=I", raw)
    reply = json.loads(proc.stdout.read(n).decode())
    proc.stdin.close()
    proc.wait(timeout=5)
    return reply, ""


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--browser", nargs="+", choices=list(UNIX_DIRS), help="default: every browser found")
    ap.add_argument("--uninstall", action="store_true")
    ap.add_argument("--test", action="store_true", help="only test the host, do not register")
    args = ap.parse_args()

    if sys.version_info < (3, 8):
        sys.exit("Python 3.8+ is required.")

    browsers = args.browser or detect_browsers()
    if args.uninstall:
        removed = uninstall(browsers or list(UNIX_DIRS))
        print("Removed:", *removed, sep="\n  ") if removed else print("Nothing to remove.")
        return

    launcher = make_launcher()
    if not args.test:
        if not browsers:
            sys.exit("No supported browser profile folders found. Use --browser chrome|firefox|... to force one.")
        done = install(browsers, launcher)
        if not done:
            sys.exit("Nothing was registered. Open your browser once, then re-run (or pass --browser).")
        print("Registered native host:")
        for d in done:
            print("  " + d)

    print("\nTesting the host...")
    reply, err = test_host(launcher)
    if not reply:
        print("  FAILED: the host did not answer.\n  " + err.strip())
        sys.exit(1)
    print(f"  host v{reply['host_version']} OK")
    print("  yt-dlp:", reply["ytdlp_version"] or "NOT FOUND (install it: pip install -U yt-dlp)")
    print("  ffmpeg:", reply["ffmpeg"] or "NOT FOUND (needed to merge video+audio and make mp3)")
    print("  downloads go to:", reply["download_dir"])
    print("\nNow fully restart your browser, then load the extension (see README.md).")


if __name__ == "__main__":
    main()
