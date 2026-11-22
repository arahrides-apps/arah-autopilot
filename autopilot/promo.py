"""Sales promotions (content/promos.yaml): which promo is on today, the promo posts, and promo Reels cut from video clips in the Drive folder."""
import os, io, json, hashlib, logging, subprocess, shutil, datetime as dt
from pathlib import Path
from .config import ROOT, load_yaml
from . import queue as Q

log = logging.getLogger("promo")
VID_EXT = (".mp4", ".mov", ".m4v", ".webm")
W, H, FPS = 1080, 1920, 30

def active(date):
    try:
        promos = load_yaml("promos.yaml") or []
    except Exception:
        return None
    for p in promos:
        if str(p["start"]) <= str(date) <= str(p["end"]):
            return p
    return None

ANGLES = [
    ("Holiday savings: up to ${a} off.", "Use promo code {c} at checkout on ArahRides.com and save up to ${a} on your booking. Choose the car you want to drive and see Jamaica your way. {t}"),
    ("Book now. Save more.", "Promo code {c} takes up to ${a} off your Jamaica car rental. Airport pickup in Montego Bay, Kingston and Ocho Rios. {t}"),
    ("Christmas cars are filling up.", "Lock in your holiday car and save up to ${a} with code {c} at checkout. Cars are limited in December, so book early. {t}"),
    ("Landing in Jamaica soon?", "Have your car waiting. Use code {c} at checkout and save up to ${a} on ArahRides.com. {t}"),
    ("Family trip? Group trip?", "7, 12 and 15 seat vehicles are in limited supply. Use code {c} for up to ${a} off at checkout. {t}"),
    ("The deal ends soon.", "Code {c} saves you up to ${a} on every booking until the sale ends. Reserve your car on ArahRides.com today. {t}"),
]

def moment(p, k, date):
    a, c, t = p["amount"], p["code"], p.get("terms", "Conditions apply.")
    last = str(date) == str(p["end"])
    h, b = ANGLES[(date.toordinal() + k) % len(ANGLES)]
    if last:
        h, b = "Last day to save.", "Today is the last day: use code {c} at checkout and save up to ${a} on ArahRides.com. {t}"
    from . import templates as T
    holiday = bool(T.holiday_logo())
    b = b.format(a=a, c=c, t=t) + " Pay with Klarna, Affirm, Link, Google Pay or Apple Pay. Book your car rental in minutes on ArahRides.com or with Winston on WhatsApp."
    return {"k": ("Holiday " if holiday else "") + p["name"], "h": h.format(a=a, c=c), "b": b, "badge": "", "theme": "xmas" if holiday else "road"}

# ---- video clips from Drive ----------------------------------------------------------------------------
def _service(cfg):
    from .photos import DriveSource
    return DriveSource(cfg)._service()

def drive_videos(cfg):
    """[(id, name, size)] of every video under the Drive folder(s)."""
    c = cfg["sources"]["drive"]; s = _service(cfg); out = []; seen = set(); stack = list(c["folder_ids"])
    while stack:
        fid = stack.pop()
        if fid in seen: continue
        seen.add(fid); tok = None
        while True:
            r = s.files().list(q=f"'{fid}' in parents and trashed=false", pageSize=200, pageToken=tok,
                               fields="nextPageToken,files(id,name,mimeType,size)", supportsAllDrives=True, includeItemsFromAllDrives=True).execute()
            for f in r.get("files", []):
                if f["mimeType"] == "application/vnd.google-apps.folder": stack.append(f["id"])
                elif f["mimeType"].startswith("video/") or f["name"].lower().endswith(VID_EXT): out.append((f["id"], f["name"], int(f.get("size", 0))))
            tok = r.get("nextPageToken")
            if not tok: break
    return sorted(out)

USE = ROOT / "data" / "clip_use.json"

def _uses():
    try: return json.loads(USE.read_text())
    except Exception: return {}

def _pick(keys, date, days=None):
    """Strict no-reuse: only a clip not used in the last 90 days. Returns the key, or None when every clip has had its turn."""
    if days is None:
        try:
            from .config import load as _load_cfg; days = int(_load_cfg().get("reels", {}).get("video_reuse_days", 365))
        except Exception:
            days = 365
    u = _uses(); today = date if isinstance(date, dt.date) else dt.date.fromisoformat(str(date))
    def fresh(k):
        last = (u.get(k) or [None])[-1]
        return last is None or (today - dt.date.fromisoformat(last)).days >= days
    free = sorted(k for k in keys if fresh(k))
    return free[0] if free else None

def note_use(key, date):
    u = _uses(); u.setdefault(key, []).append(str(date)); u[key] = u[key][-50:]
    USE.parent.mkdir(parents=True, exist_ok=True); USE.write_text(json.dumps(u, indent=0))

def get_clip(cfg, date, k):
    """A clip for a promo Reel: (path, start_second, key) or None. Rotates through every clip and starts later in the clip each time it comes round."""
    test = os.environ.get("ARAH_TEST_CLIPS")
    if test:
        fs = {f.name: f for f in sorted(Path(test).glob("*.mp4"))}
        if not fs: return None
        key = _pick(list(fs), date)
        return (fs[key], 1, key) if key else None
    try:
        vids = drive_videos(cfg)
    except Exception as e:
        log.warning("Drive clips unavailable: %s", e); return None
    cap = int(cfg["reels"].get("max_clip_mb", 250)) << 20
    vids = {v[0]: v for v in vids if 0 < v[2] <= cap}
    if not vids: return None
    key = _pick(list(vids), date)
    if not key: return None
    dest = ROOT / "cache" / "clips" / (key + ".mp4")
    if not dest.exists():
        from googleapiclient.http import MediaIoBaseDownload
        dest.parent.mkdir(parents=True, exist_ok=True)
        with open(dest, "wb") as fh:
            dl = MediaIoBaseDownload(fh, _service(cfg).files().get_media(fileId=key, supportsAllDrives=True), chunksize=16 << 20)
            done = False
            while not done: _, done = dl.next_chunk()
    return dest, 1, key

def make_promo_reel(clip, p, out, seconds=8, hold=2.6, art=None, start=1):
    """Clip cropped to 1080x1920 (first `seconds` seconds, starting a little in), the promo banner over it, then the code end card."""
    from . import promo_art
    art = Path(art or (Q.DOCS / "media" / "promo")); banner, end = promo_art.render(p, art)
    out = Path(out); out.parent.mkdir(parents=True, exist_ok=True)
    fc = (f"[0:v]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},fps={FPS},setsar=1,format=yuv420p[a0];"
          f"[1:v]format=rgba[bn];[a0][bn]overlay=0:0,format=yuv420p[a];"
          f"[2:v]scale={W}:{H},fps={FPS},setsar=1,format=yuv420p[e];[a][e]concat=n=2:v=1:a=0[v]")
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-ss", str(start), "-t", str(seconds), "-i", str(clip),
           "-loop", "1", "-framerate", str(FPS), "-t", str(seconds), "-i", str(banner), "-loop", "1", "-framerate", str(FPS), "-t", str(hold), "-i", str(end),
           "-filter_complex", fc, "-map", "[v]", "-c:v", "libx264", "-crf", "22", "-preset", "veryfast", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(out)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0 or not out.exists() or out.stat().st_size < 20000:       # started past the end of a short clip: play it from the beginning
        cmd[cmd.index("-ss") + 1] = "0"
        r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0: raise RuntimeError("ffmpeg: " + r.stderr[-300:])
    return out
