# 🎬 yt-dlp-Browser-Extension

A browser extension for **Chrome, Edge, Brave, Chromium, and Firefox** that downloads video and audio from the current page using `yt-dlp` directly on your computer. The entire process is automated and easy to set up!

## 📋 Requirements

- 🐍 **Python 3.8 or above:** [Download Python](https://www.python.org/downloads/)
  - ⚠️ During installation, make sure to check **"Add Python to PATH"**.

## 🚀 Installation (3 Steps)

### 1️⃣ Install the required tools

Run `yt-dlp.bat`.

It automatically downloads and installs the latest versions of **yt-dlp, Deno, and FFmpeg**, then adds them to your `PATH`.

✅ Once finished, it creates a folder named `ytdlp-tools`.

> Note: if you moved the folder elsewehere after running "yt-dlp.bat" just open the folder and run "relink-path.bat" it will repair the PATH for you.

### 2️⃣ Install the native messaging host

📦 Extract `yt-dlp-bridge.zip` to a permanent location. **Don't move the folder after installation.**

▶️ Open the extracted folder and run:

   ```bash
   Run install.py
   ```

### 3️⃣ Load the browser extension

Choose the instructions for your browser:

#### 🌐 Chrome / Edge / Brave / Chromium

1. Open `chrome://extensions` (for Edge, use `edge://extensions`).
2. Enable **Developer mode**.
3. Click **Load unpacked**.
4. Select the `extension` folder.


#### 🦊 For Firefox

1. Open a terminal in the extracted folder.
2. Run the following command to generate the Firefox-compatible extension:

   ```bash
   Run build_firefox.py
   ```

3. Open `about:debugging#/runtime/this-firefox`.
4. Click **Load Temporary Add-on**.
5. Select `extension-firefox/manifest.json`.

⚠️ **Note:** Temporary add-ons are removed when Firefox closes. A permanent installation requires the add-on to be signed.

🔄 **Finally, fully close and reopen your browser** after completing the installation.

## 🎮 Usage

1. 🌐 Open a page containing a video or audio source.
2. 🖱️ Click the extension icon.
3. ⚙️ Choose your preferred format.
4. ⬇️ Press **Download**. 🎉🎉🎉🎉🎉🎉

💡 You can also right-click a link or page and select **"Download ... with yt-dlp"**.

📁 **Default download location:** `~/Downloads/yt-dlp-bridge`

You can change the download folder using the optional configuration below.

### 🔐 Download videos that require login

For videos that require you to be logged in:

1. Open the extension's settings.
2. Set **Use login from** to **This browser**.
3. Approve the site's permission prompt when requested.
4. Start the download.

🔒 The extension reads the site's cookies itself and passes them to `yt-dlp` for that download. The temporary cookie file is deleted afterward.

💡 Other options, such as Firefox, Chrome, and Brave, make `yt-dlp` read the browser's cookie database directly. This can fail with Chromium-based browsers on Windows while the browser is open.

### ⚙️ Optional configuration

You can customize the executable paths and download directory in `host/config.json`:

```json
{
  "ytdlp_path": "C:\\tools\\yt-dlp.exe",
  "ffmpeg_path": "...",
  "download_dir": "D:\\Videos"
}
```

## 🛠️ Troubleshooting

- 🔄 **Downloads suddenly stop working:** `yt-dlp` can fall behind when websites change. Re-run `yt-dlp.bat` to update the tools.

- 🔌 **"Specified native messaging host not found":** Run the installer for your browser:

  ```bash
  python install.py --browser <name>
  ```

  Then fully restart the browser. To verify that the helper starts correctly, run:

  ```bash
  python install.py --test
  ```

- 🐧 **Snap / Flatpak browsers:** These browsers are sandboxed and may be unable to run the native messaging host. Try the regular `.deb` / `.rpm` package or the official tarball build instead.

- 🛑 **Cancel a download:** Cancelling stops `yt-dlp` and any FFmpeg process it started. Partial `.part` files remain, allowing the download to resume when you download the same link again.

- ❌ **"yt-dlp not found":** Install `yt-dlp` or set `ytdlp_path` in `host/config.json`.

- 🔑 **YouTube 403 / sign-in errors:** Update `yt-dlp` and try setting **Use login from** to **This browser**.

  ```bash
  yt-dlp -U
  ```

- 🗑️ **Uninstall everything:** Run the following command from the extracted installer folder:

  ```bash
  python install.py --uninstall
  ```
