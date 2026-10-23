# yt-dlp-Browser-Extension

A browser extension (Chrome, Edge, Brave, Chromium, Firefox) that downloads the current
page's video/audio with yt-dlp on your own computer.

## Requirements
- Python 3.8 or above https://www.python.org/downloads/ Make sure "Add Python to PATH" is checked.

## Install (3 steps)

### 1. Run yt-dlp.bat 
(it will automatically download and install the latest yt-dlp, deno, ffmpeg and adds them to PATH)
when it's done it will make a folder "ytdlp-tools"

Note: if you moved the folder elsewehere after running "yt-dlp.bat" just open the folder and run "relink-path.bat" it will repair the PATH for you.

### 2. Register the helper
Unzip this folder somewhere permanent (don't move it afterwards), then:

    python install.py          # Windows: py install.py


### 2. Load the extension
- **Chrome / Edge / Brave:** open `chrome://extensions` (or `edge://extensions`),
  turn on Developer mode, click "Load unpacked", pick the `extension` folder.
  The extension ID is fixed, so there is nothing to copy.
- **Firefox:** run `python build_firefox.py` once (it makes `extension-firefox/`, because
  Firefox needs a slightly different manifest), then open
  `about:debugging#/runtime/this-firefox`, "Load Temporary Add-on", and pick
  `extension-firefox/manifest.json`. (Temporary add-ons are removed when Firefox
  closes; a permanent install needs the add-on signed.)

Then **fully quit and reopen the browser** once.

## Use
Click the extension icon on a video page, pick a format, press Download.
You can also right-click a link or page: "Download ... with yt-dlp".
Files go to `~/Downloads/yt-dlp-bridge` unless you set a folder.

### Videos that need you to be logged in
Set **Use login from** to **This browser**. The extension reads that site's cookies
itself (after you approve a permission prompt for that site) and hands them to yt-dlp
for that one download; the temporary file is deleted afterwards. The other entries
(Firefox, Chrome, Brave...) make yt-dlp read the browser's cookie database directly,
which often fails for Chromium browsers on Windows while the browser is open.

Optional `host/config.json`:

    {"ytdlp_path": "C:\\tools\\yt-dlp.exe", "ffmpeg_path": "...", "download_dir": "D:\\Videos"}

## Troubleshooting
- IMPORTANT:sometimes yt-dlp could break when it falls behind in updates. If downloads start failing, re-run "yt-dlp.bat" to update everything.

- **"Specified native messaging host not found"**: run `python install.py --browser <name>`
  for the browser you actually use, then fully restart it. Run `python install.py --test`
  to confirm the helper starts.
- **Snap/Flatpak browsers** are sandboxed and often cannot run the helper; use the
  regular .deb/.rpm or the official tarball build instead.
- **Cancel**: stops yt-dlp and any ffmpeg it started. Partial `.part` files stay in the
  folder, so downloading the same link again resumes.
- **"yt-dlp not found"**: install it, or set `ytdlp_path` in `host/config.json`.
- **YouTube 403 / sign-in errors**: update yt-dlp (`yt-dlp -U`) and try "Use login from" your browser.
- Remove everything: `python install.py --uninstall`.
