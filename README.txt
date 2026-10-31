VIDEO DOWNLOADER (MP3 / MP4)
============================

HOW TO USE
1. Double-click "Video Downloader.exe".
   - First launch downloads ffmpeg (~31 MB) into the "tools" folder. One time only.
   - Windows may show "Windows protected your PC" because the exe isn't signed:
     click "More info" -> "Run anyway".
2. Paste one or more links (one per line): YouTube, Facebook, TikTok, X/Twitter,
   Instagram, Vimeo, Reddit and ~1,800 other sites.
3. Pick MP4 (video) or MP3 (audio), choose the quality, click Download.
4. Files go to the "Downloads" folder next to the exe (change it with Browse...).

TIPS
- If a site stops working, click "Update yt-dlp". It updates tools\yt-dlp.exe in place.
- For full YouTube support, install Deno once:  winget install DenoLand.Deno
- Keep the "tools" folder next to the exe. You can make a desktop shortcut to the exe.
- MP4 files are named with their resolution, e.g. "Title [id] (1080p).mp4".

FOLDER
  Video Downloader.exe   the app
  tools\yt-dlp.exe       downloader engine (self-updating)
  tools\ffmpeg.exe       converter (downloaded on first launch)
  source\downloader.py   source code

Only download videos you own or have permission to save.
