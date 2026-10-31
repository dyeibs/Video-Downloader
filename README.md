![Video Downloader](banner.png)

# Video Downloader

Paste a link, pick **MP3** or **MP4**, done. A simple Windows app for downloading videos and music from YouTube and 1,800+ other sites.

<p align="center">
  <a href="https://github.com/dyeibs/video-downloader/releases/latest/download/Video.Downloader.exe">
    <img src="https://img.shields.io/badge/⬇%20Download-Video%20Downloader.exe-e02832?style=for-the-badge" alt="Download Video Downloader.exe">
  </a>
</p>

---

## 📥 How to install (2 minutes)

**1. Download the app**
Click the red **Download** button above, or go to [Releases](https://github.com/dyeibs/video-downloader/releases/latest) and download `Video.Downloader.exe`.

**2. Put it in its own folder**
Make a new folder (for example `Documents\Video Downloader`) and move the exe there.
The app creates a `tools` folder and a `Downloads` folder next to itself, so don't run it straight from your Downloads folder or your Desktop.

**3. Open it**
Double-click `Video.Downloader.exe`.

> **"Windows protected your PC"?** This shows up because the app isn't signed (signing certificates cost money).
> Click **More info**, then **Run anyway**. You only need to do this once.

**4. Wait for first-time setup**
The first time it opens, the app downloads its tools (about 55 MB). The bottom of the window shows the progress. When it says **"Ready"**, you're good to go.

**5. (Recommended) Turn on full YouTube support**
Open **PowerShell** or **Command Prompt**, paste this, and press Enter:
```
winget install DenoLand.Deno
```
Then close and reopen the app. Without this, some YouTube videos may fail or show fewer quality options.

---

## ▶️ How to use

1. Copy a video link (YouTube, Facebook, TikTok, X, Instagram, Vimeo, ...).
2. Click **Paste** in the app. You can add several links, one per line.
3. Choose **MP4** (video) or **MP3** (audio only), and pick a quality.
4. Click **⬇ Download**.
5. Click **Open folder** to see your files.

Tick **"Download whole playlist"** to grab every video in a playlist link.

---

## ❓ Troubleshooting

| Problem | Fix |
|---|---|
| A video that used to work now fails | Click **Update yt-dlp** in the app, then try again. Sites change often and this fixes most errors. |
| YouTube errors that mention "JavaScript" or "signature" | Do step 5 above (install Deno), then reopen the app. |
| Setup failed on first launch | Check your internet connection and reopen the app. |
| Antivirus deleted or blocked the exe | It's a false alarm common with Python apps. Add an exception, or [run from source](#-run-from-source). |
| I want my files saved somewhere else | Click **Browse…** next to "Save to". |

---

## ✨ Features
- **MP4** up to 4K, saved as H.264/AAC so it plays everywhere (Windows, phones, CapCut)
- **MP3** at 128–320 kbps
- Several links at once, and whole playlists
- Progress bar with speed and time left, plus a Cancel button
- One-click **Update yt-dlp** button

---

## 🛠️ For developers

### Run from source
Needs [Python 3.9+](https://www.python.org/downloads/). Tkinter comes with the Windows installer.
```
git clone https://github.com/dyeibs/video-downloader.git
cd video-downloader
python downloader.py
```

### Build the exe yourself
```
pip install pyinstaller
pyinstaller --onefile --windowed --name "Video Downloader" downloader.py
```
The exe ends up in the `dist` folder.

### Built with
Python · Tkinter · [yt-dlp](https://github.com/yt-dlp/yt-dlp) · [ffmpeg](https://ffmpeg.org)

---

⚠️ Only download videos you own or have permission to save.

Made by [dyeibs](https://github.com/dyeibs)
