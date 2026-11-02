"""
Video Downloader - paste a link (YouTube, Facebook, TikTok, X, Vimeo, ...) and save it as MP3 or MP4.
Front-end for the official yt-dlp.exe. Packaged as "Video Downloader.exe" with PyInstaller.
Tools live in .\\tools next to the exe; anything missing is downloaded on first launch.
"""
import io
import os
import queue
import re
import shutil
import subprocess
import sys
import threading
import urllib.request
import zipfile
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

FROZEN = getattr(sys, "frozen", False)
APP_DIR = os.path.dirname(sys.executable if FROZEN else os.path.abspath(__file__))
TOOLS = os.path.join(APP_DIR, "tools")
DEFAULT_OUT = os.path.join(APP_DIR, "Downloads")
EXE = ".exe" if os.name == "nt" else ""
YTDLP = os.path.join(TOOLS, "yt-dlp" + EXE)
FFMPEG = os.path.join(TOOLS, "ffmpeg" + EXE)

YTDLP_URL = "https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp.exe"
# ffmpeg 7.1 (win64) from the imageio-ffmpeg wheel on PyPI — a stable, permanent URL.
FFMPEG_WHEEL = ("https://files.pythonhosted.org/packages/e5/55/1d50cdd78d862a30c2ce44f01cea387f77b364b21fa2fecf1590258b215b/"
                "imageio_ffmpeg-0.7.0-py3-none-win_amd64.whl")

MP4_QUALITIES = ["Best", "2160p (4K)", "1440p", "1080p", "720p", "480p", "360p"]
MP3_QUALITIES = ["320 kbps", "256 kbps", "192 kbps", "128 kbps", "96 kbps"]
MP3_DEFAULT = 3  # 128 kbps: small files, still sounds good
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
PROG_RE = re.compile(r"^PROG\s*([\d.]+)%\|(.*?)\|(.*?)\|(.*)$")
SPOTIFY_RE = re.compile(r"open\.spotify\.com/(?:intl-[a-z-]+/)?(playlist|album|track)/([A-Za-z0-9]+)")
URL_RE = re.compile(r"^[a-z][a-z0-9+.-]*://", re.I)
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/130.0 Safari/537.36")


def _walk(o):
    """Yield every dict inside a JSON structure."""
    if isinstance(o, dict):
        yield o
        for v in o.values():
            yield from _walk(v)
    elif isinstance(o, list):
        for v in o:
            yield from _walk(v)


def _artists(v):
    if isinstance(v, str):
        return v
    if isinstance(v, list):
        return ", ".join(a.get("name", "") if isinstance(a, dict) else str(a) for a in v)
    if isinstance(v, dict):  # {"items": [{"profile": {"name": ...}}]}
        names = [d.get("name") for d in _walk(v) if isinstance(d.get("name"), str)]
        return ", ".join(dict.fromkeys(names))
    return ""


def spotify_tracks(kind, sid):
    """Read song titles + artists from Spotify's public embed page (metadata only, no audio).
    Returns (collection_name, ["Artist - Title", ...])."""
    import json
    url = f"https://open.spotify.com/embed/{kind}/{sid}"
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "en"})
    with urllib.request.urlopen(req, timeout=30) as r:
        html = r.read().decode("utf-8", "replace")
    m = re.search(r'<script[^>]+id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.S)
    if not m:
        raise RuntimeError("Spotify page format changed (no track data found).")
    data = json.loads(m.group(1))

    name, songs = "", []
    for d in _walk(data):
        tl = d.get("trackList")
        if isinstance(tl, list) and tl:
            name = d.get("name") or d.get("title") or ""
            for t in tl:
                if not isinstance(t, dict):
                    continue
                title = t.get("title") or t.get("name") or ""
                artist = _artists(t.get("subtitle") or t.get("artists") or "")
                if title:
                    songs.append(f"{artist} - {title}" if artist else title)
            break
    if not songs:  # single track page
        for d in _walk(data):
            if d.get("type") == "track" or ("name" in d and "artists" in d):
                title = d.get("name") or d.get("title")
                artist = _artists(d.get("artists") or d.get("subtitle") or "")
                if title:
                    songs = [f"{artist} - {title}" if artist else title]
                    name = title
                    break
    if not songs:
        raise RuntimeError("Couldn't find any songs. Is the playlist public?")
    return name, list(dict.fromkeys(songs))  # drop duplicates, keep order


def find_js_runtimes():
    """YouTube needs a JavaScript runtime for full format access. Use whatever is installed."""
    home = os.path.expanduser("~")
    lad = os.environ.get("LOCALAPPDATA", "")
    candidates = [
        ("deno", [shutil.which("deno"), os.path.join(home, ".deno", "bin", "deno.exe"),
                  os.path.join(lad, "Microsoft", "WinGet", "Links", "deno.exe")]),
        ("node", [shutil.which("node"), r"C:\Program Files\nodejs\node.exe"]),
        ("bun", [shutil.which("bun"), os.path.join(home, ".bun", "bin", "bun.exe")]),
    ]
    found = []
    for name, paths in candidates:
        for p in paths:
            if p and os.path.isfile(p):
                found.append((name, p))
                break
    return found


def fetch(url, q, label):
    """Download url into memory, reporting progress to the UI queue."""
    req = urllib.request.Request(url, headers={"User-Agent": "VideoDownloader/1.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        total = int(r.headers.get("Content-Length") or 0)
        buf = io.BytesIO()
        done = 0
        while True:
            chunk = r.read(1 << 16)
            if not chunk:
                break
            buf.write(chunk)
            done += len(chunk)
            if total:
                q.put(("pct", done / total * 100))
                q.put(("status", f"{label}  {done / 1e6:.1f} / {total / 1e6:.1f} MB"))
        return buf.getvalue()


class App:
    def __init__(self, root):
        self.root = root
        self.q = queue.Queue()
        self.proc = None
        self.cancel = False

        root.title("Video Downloader  •  MP3 / MP4")
        root.geometry("700x540")
        root.minsize(580, 470)
        try:
            ttk.Style().theme_use("vista" if os.name == "nt" else "clam")
        except tk.TclError:
            pass
        if FROZEN:
            try:
                root.iconbitmap(sys.executable)
            except tk.TclError:
                pass

        pad = {"padx": 10, "pady": 4}
        main = ttk.Frame(root, padding=10)
        main.pack(fill="both", expand=True)

        ttk.Label(main, text="Links (YouTube, Spotify playlist, ...) or song names like  Bon Jovi - Always  — one per line:").pack(anchor="w", **pad)
        self.urls = tk.Text(main, height=4, wrap="none", font=("Consolas", 10))
        self.urls.pack(fill="x", **pad)
        b = ttk.Frame(main)
        b.pack(fill="x", padx=10)
        ttk.Button(b, text="Paste", command=self.paste).pack(side="left")
        ttk.Button(b, text="Clear", command=lambda: self.urls.delete("1.0", "end")).pack(side="left", padx=6)

        opts = ttk.LabelFrame(main, text="Options", padding=8)
        opts.pack(fill="x", **pad)
        self.fmt = tk.StringVar(value="mp4")
        ttk.Radiobutton(opts, text="MP4 (video)", variable=self.fmt, value="mp4",
                        command=self.on_fmt).grid(row=0, column=0, sticky="w")
        ttk.Radiobutton(opts, text="MP3 (audio only)", variable=self.fmt, value="mp3",
                        command=self.on_fmt).grid(row=0, column=1, sticky="w", padx=12)
        ttk.Label(opts, text="Quality:").grid(row=0, column=2, sticky="e", padx=(20, 4))
        self.quality = ttk.Combobox(opts, state="readonly", width=14, values=MP4_QUALITIES)
        self.quality.current(0)
        self.quality.grid(row=0, column=3, sticky="w")
        self.playlist = tk.BooleanVar(value=False)
        ttk.Checkbutton(opts, text="Download whole playlist if the link is a playlist",
                        variable=self.playlist).grid(row=1, column=0, columnspan=4, sticky="w", pady=(6, 0))
        ttk.Label(opts, text="Save to:").grid(row=2, column=0, sticky="w", pady=(6, 0))
        self.outdir = tk.StringVar(value=DEFAULT_OUT)
        ttk.Entry(opts, textvariable=self.outdir).grid(row=2, column=1, columnspan=2, sticky="ew", pady=(6, 0))
        ttk.Button(opts, text="Browse…", command=self.browse).grid(row=2, column=3, sticky="w", padx=4, pady=(6, 0))
        opts.columnconfigure(2, weight=1)

        act = ttk.Frame(main)
        act.pack(fill="x", **pad)
        self.dl_btn = ttk.Button(act, text="⬇  Download", command=self.start, state="disabled")
        self.dl_btn.pack(side="left")
        self.cancel_btn = ttk.Button(act, text="Cancel", command=self.do_cancel, state="disabled")
        self.cancel_btn.pack(side="left", padx=6)
        ttk.Button(act, text="Open folder", command=self.open_folder).pack(side="left")
        self.upd_btn = ttk.Button(act, text="Update yt-dlp", command=self.update_ytdlp, state="disabled")
        self.upd_btn.pack(side="right")

        self.status = tk.StringVar(value="Starting…")
        ttk.Label(main, textvariable=self.status).pack(anchor="w", **pad)
        self.bar = ttk.Progressbar(main, mode="determinate", maximum=100)
        self.bar.pack(fill="x", **pad)
        self.log = tk.Text(main, height=8, state="disabled", font=("Consolas", 9), bg="#f6f6f6")
        self.log.pack(fill="both", expand=True, **pad)

        foot = ttk.Frame(main)
        foot.pack(fill="x", padx=10)
        credit = tk.Label(foot, text="Made by dyeibs  •  github.com/dyeibs", fg="#888888",
                          cursor="hand2", font=("Segoe UI", 8))
        credit.pack(side="right")
        credit.bind("<Button-1>", lambda e: __import__("webbrowser").open("https://github.com/dyeibs"))
        credit.bind("<Enter>", lambda e: credit.configure(fg="#e02832"))
        credit.bind("<Leave>", lambda e: credit.configure(fg="#888888"))

        self.js = find_js_runtimes()
        root.after(100, self.poll)
        threading.Thread(target=self.setup_tools, daemon=True).start()

    # ---------------- first-run setup
    def setup_tools(self):
        try:
            os.makedirs(TOOLS, exist_ok=True)
            if not os.path.isfile(YTDLP):
                data = fetch(YTDLP_URL, self.q, "First run: downloading yt-dlp…")
                with open(YTDLP, "wb") as f:
                    f.write(data)
            if not os.path.isfile(FFMPEG):
                data = fetch(FFMPEG_WHEEL, self.q, "First run: downloading ffmpeg…")
                with zipfile.ZipFile(io.BytesIO(data)) as z:
                    name = next(n for n in z.namelist() if "binaries/ffmpeg" in n and n.endswith(".exe"))
                    with z.open(name) as src, open(FFMPEG, "wb") as dst:
                        shutil.copyfileobj(src, dst)
            ver = subprocess.run([YTDLP, "--version"], capture_output=True, text=True,
                                 creationflags=NO_WINDOW).stdout.strip()
            self.q.put(("log", f"yt-dlp {ver}  •  ffmpeg ready"))
            self.q.put(("log", "JS runtime: " + (", ".join(n for n, _ in self.js) if self.js else
                        "none — if YouTube gives errors, install Deno: winget install DenoLand.Deno")))
            self.q.put(("ready", True))
        except Exception as e:
            self.q.put(("log", f"Setup failed: {e}"))
            self.q.put(("status", "Setup failed — check your internet connection and reopen the app."))
            self.q.put(("pct", 0))

    # ---------------- UI helpers
    def on_fmt(self):
        mp4 = self.fmt.get() == "mp4"
        self.quality.configure(values=MP4_QUALITIES if mp4 else MP3_QUALITIES)
        self.quality.current(0 if mp4 else MP3_DEFAULT)

    def paste(self):
        try:
            self.urls.insert("end", self.root.clipboard_get().strip() + "\n")
        except tk.TclError:
            pass

    def browse(self):
        d = filedialog.askdirectory(initialdir=self.outdir.get() or APP_DIR)
        if d:
            self.outdir.set(os.path.normpath(d))

    def open_folder(self):
        d = self.outdir.get()
        os.makedirs(d, exist_ok=True)
        if os.name == "nt":
            os.startfile(d)
        else:
            subprocess.Popen(["xdg-open", d])

    def write_log(self, msg):
        self.log.configure(state="normal")
        self.log.insert("end", msg + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def set_busy(self, busy):
        self.dl_btn.configure(state="disabled" if busy else "normal")
        self.upd_btn.configure(state="disabled" if busy else "normal")
        self.cancel_btn.configure(state="normal" if busy else "disabled")

    def poll(self):
        try:
            while True:
                kind, val = self.q.get_nowait()
                if kind == "log":
                    self.write_log(val)
                elif kind == "status":
                    self.status.set(val)
                elif kind == "pct":
                    self.bar["value"] = val
                elif kind == "ready":
                    self.set_busy(False)
                    self.bar["value"] = 0
                    self.status.set("Ready. Paste a link and hit Download.")
                elif kind == "done":
                    self.set_busy(False)
                    if val:
                        self.bar["value"] = 100
        except queue.Empty:
            pass
        self.root.after(100, self.poll)

    # ---------------- download
    def build_args(self, url):
        q = self.quality.get()
        a = [YTDLP, "--newline", "--no-colors", "--encoding", "utf-8", "--windows-filenames",
             "--retries", "5", "--ffmpeg-location", FFMPEG, "--embed-metadata",
             "--progress-template",
             "download:PROG %(progress._percent_str)s|"
             "%(progress._total_bytes_str,progress._total_bytes_estimate_str)s|"
             "%(progress._speed_str)s|%(progress._eta_str)s",
             "--yes-playlist" if self.playlist.get() else "--no-playlist"]
        for name, path in self.js:
            a += ["--js-runtimes", f"{name}:{path}"]
        # MP4 names carry the resolution so an MP3 of the same video never reuses (and deletes) the MP4.
        name = "%(title).150B [%(id)s].%(ext)s" if self.fmt.get() == "mp3" else \
            "%(title).150B [%(id)s] (%(height&{}p|video)s).%(ext)s"
        a += ["-o", os.path.join(self.outdir.get(), name)]
        if self.fmt.get() == "mp3":
            a += ["-f", "bestaudio/best", "-x", "--audio-format", "mp3",
                  "--audio-quality", q.split()[0] + "K"]
        else:
            sort = "vcodec:h264,acodec:m4a"
            if q != "Best":
                sort = f"res:{q.split('p')[0]}," + sort
            a += ["-S", sort, "-f", "bv*+ba/b", "--merge-output-format", "mp4", "--remux-video", "mp4"]
        return a + ["--", url]

    def start(self):
        urls = [u.strip() for u in self.urls.get("1.0", "end").splitlines() if u.strip()]
        if not urls:
            messagebox.showinfo("Nothing to download", "Paste a link or type a song name first.")
            return
        os.makedirs(self.outdir.get(), exist_ok=True)
        self.cancel = False
        self.bar["value"] = 0
        self.set_busy(True)
        threading.Thread(target=self.run, args=(urls,), daemon=True).start()

    def do_cancel(self):
        self.cancel = True
        self.status.set("Cancelling…")
        p = self.proc
        if p and p.poll() is None:
            if os.name == "nt":  # also kill ffmpeg child processes
                subprocess.run(["taskkill", "/F", "/T", "/PID", str(p.pid)],
                               capture_output=True, creationflags=NO_WINDOW)
            else:
                p.kill()

    def expand(self, lines):
        """Turn the text box into download targets:
        - Spotify links -> each song searched on YouTube (Spotify audio is DRM-protected)
        - other links   -> downloaded as-is
        - plain text    -> treated as a song name and searched on YouTube"""
        hint = "official audio" if self.fmt.get() == "mp3" else "official music video"
        items = []
        for line in lines:
            sp = SPOTIFY_RE.search(line)
            if sp:
                kind, sid = sp.groups()
                self.q.put(("status", f"Reading Spotify {kind}…"))
                try:
                    name, songs = spotify_tracks(kind, sid)
                except Exception as e:
                    self.q.put(("log", f"ERROR reading Spotify link: {e}"))
                    continue
                self.q.put(("log", f"Spotify {kind} '{name}': {len(songs)} songs, searching each on YouTube"))
                if kind == "playlist" and len(songs) == 100:
                    self.q.put(("log", "Note: Spotify only shows the first 100 songs of a playlist here."))
                items += [(s, f"ytsearch1:{s} {hint}") for s in songs]
            elif URL_RE.match(line):
                items.append((line, line))
            else:
                items.append((line, f"ytsearch1:{line} {hint}"))
        return items

    def run(self, lines):
        ok_all = True
        failed = []
        items = self.expand(lines)
        for i, (label, url) in enumerate(items, 1):
            if self.cancel:
                break
            self.q.put(("log", f"[{i}/{len(items)}] {label}"))
            try:
                self.proc = subprocess.Popen(self.build_args(url), stdout=subprocess.PIPE,
                                             stderr=subprocess.STDOUT, text=True, encoding="utf-8",
                                             errors="replace", creationflags=NO_WINDOW)
                for line in self.proc.stdout:
                    self.handle_line(line.rstrip())
                rc = self.proc.wait()
            except Exception as e:
                self.q.put(("log", f"ERROR: {e}"))
                rc = 1
            if rc != 0 and not self.cancel:
                ok_all = False
                failed.append(label)
        if not items:
            ok_all = False
        if failed:
            self.q.put(("log", f"{len(failed)} failed: " + "; ".join(failed[:20])))
        if self.cancel:
            self.q.put(("status", "Cancelled."))
        elif ok_all:
            self.q.put(("status", f"Done! Saved to {self.outdir.get()}"))
        else:
            self.q.put(("status", "Finished with errors — see log. Try 'Update yt-dlp' if a site stopped working."))
        self.q.put(("done", ok_all and not self.cancel))

    def handle_line(self, line):
        m = PROG_RE.match(line)
        if m:
            pct, total, speed, eta = (s.strip() for s in m.groups())
            self.q.put(("pct", float(pct)))
            self.q.put(("status", f"{pct}%  of {total}  •  {speed}  •  ETA {eta}"))
            return
        if line.startswith("[download] Destination:"):
            self.q.put(("log", "Downloading: " + os.path.basename(line.split(":", 1)[1].strip())))
        elif line.startswith(("[Merger]", "[ExtractAudio]", "[VideoRemuxer]")):
            self.q.put(("status", "Processing with ffmpeg…"))
            if "Destination" in line or "Merging" in line:
                self.q.put(("log", line))
        elif "has already been downloaded" in line or line.startswith(("ERROR", "WARNING")):
            self.q.put(("log", line))

    # ---------------- update
    def update_ytdlp(self):
        def job():
            self.q.put(("status", "Updating yt-dlp…"))
            r = subprocess.run([YTDLP, "-U"], capture_output=True, text=True, creationflags=NO_WINDOW)
            for ln in (r.stdout + r.stderr).strip().splitlines()[-2:]:
                self.q.put(("log", ln))
            self.q.put(("status", "yt-dlp is up to date." if r.returncode == 0 else "Update failed — see log."))
            self.q.put(("done", False))
        self.set_busy(True)
        self.cancel_btn.configure(state="disabled")
        threading.Thread(target=job, daemon=True).start()


if __name__ == "__main__":
    root = tk.Tk()
    App(root)
    root.mainloop()
