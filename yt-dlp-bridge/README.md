# yt-dlp Bridge

A browser extension (Chrome, Edge, Brave, Chromium, Firefox) that downloads the current
page's video/audio with yt-dlp on your own computer.

## Requirements
- Python 3.8+
- yt-dlp  (`pip install -U yt-dlp`, `brew install yt-dlp`, or `winget install yt-dlp`)
- ffmpeg  (needed to merge video+audio and to make MP3)

## Install (2 steps)

### 1. Register the helper
Unzip this folder somewhere permanent (don't move it afterwards), then:

    python install.py          # Windows: py install.py

It registers the helper for every browser it finds and tests it. You should see
"host ... OK". If you move the folder later, run it again.

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
Click the toolbar icon on a video page, pick a format, press Download.
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

Only download content you have the right to save.
