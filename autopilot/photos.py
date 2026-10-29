"""Finds a fresh photo: Google Drive first (your own shoots), then free web photos (Pexels, Openverse CC0)."""
import os, io, re, json, random, hashlib, logging
from dataclasses import dataclass, field
from pathlib import Path
from PIL import Image, ImageOps
from . import ledger as L
from .config import ROOT, load_yaml

log = logging.getLogger("photos")
IMG_EXT = (".jpg", ".jpeg", ".png", ".webp")

@dataclass
class Photo:
    id: str                 # e.g. drive:<fileId>, local:<stem>, pexels:123
    name: str               # file stem (also stored in the ledger)
    source: str             # drive | local | pexels | openverse
    path: str               # local file, already downsized
    kind: str = "car"       # car | scenery
    credit: str = ""
    text: str = ""          # title/alt text from the source (used to confirm the place)
    flags: list = field(default_factory=list)
    hash: int = 0
    w: int = 0
    h: int = 0

    @property
    def portrait(self):
        return self.h >= self.w * 1.1

    def keys(self):
        return [self.id, "name:" + self.name]

# ---------------------------------------------------------------- helpers
def prep(src, dest, max_side=1800):
    """Auto-rotate, shrink and save as JPEG. Never alters the picture itself (no blur, no overlays)."""
    im = ImageOps.exif_transpose(Image.open(src)).convert("RGB")
    im.thumbnail((max_side, max_side), Image.LANCZOS)
    Path(dest).parent.mkdir(parents=True, exist_ok=True)
    im.save(dest, "JPEG", quality=90)
    return im.size

_cascade = None
def has_face(path):
    """Best-effort face check (OpenCV, open source). Returns None when OpenCV is not installed."""
    global _cascade
    try:
        import cv2
        if _cascade is None:
            _cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    except Exception:
        return None
    g = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
    if g is None:
        return None
    s = 800 / max(g.shape)
    if s < 1:
        g = cv2.resize(g, None, fx=s, fy=s)
    faces = _cascade.detectMultiScale(g, 1.1, 6, minSize=(max(24, g.shape[1] // 30),) * 2)
    return len(faces) > 0

def http_json(url, headers=None, params=None, timeout=25):
    import requests
    r = requests.get(url, headers=headers, params=params, timeout=timeout)
    r.raise_for_status()
    return r.json()

def http_file(url, dest, timeout=60, max_mb=40):
    import requests
    with requests.get(url, stream=True, timeout=timeout) as r:
        r.raise_for_status()
        Path(dest).parent.mkdir(parents=True, exist_ok=True)
        n = 0
        with open(dest, "wb") as f:
            for ch in r.iter_content(1 << 16):
                n += len(ch)
                if n > max_mb << 20:
                    raise IOError("file too large")
                f.write(ch)

# ---------------------------------------------------------------- sources
class LocalSource:
    """A folder of photos (optional extra pool; the tests use it as a stand-in for Drive)."""
    name = "local"
    def __init__(self, cfg):
        c = cfg["sources"]["local"]
        d = Path(c["dir"]); self.dir = d if d.is_absolute() else ROOT / d
    def list(self):
        if not self.dir.exists():
            return []
        return [{"id": "local:" + p.stem, "name": p.stem, "ref": str(p)} for p in sorted(self.dir.rglob("*")) if p.suffix.lower() in IMG_EXT]
    def fetch(self, item, dest):
        return prep(item["ref"], dest)

class DriveSource:
    """Reads every image under the Drive folder(s) with a service account (read-only)."""
    name = "drive"
    def __init__(self, cfg):
        self.c = cfg["sources"]["drive"]; self._svc = None; self._items = None
    def _service(self):
        if self._svc is None:
            from google.oauth2 import service_account
            from googleapiclient.discovery import build
            raw = os.environ.get(self.c["service_account_env"], "")
            if not raw:
                raise RuntimeError("Drive secret %s is empty" % self.c["service_account_env"])
            creds = service_account.Credentials.from_service_account_info(
                json.loads(raw), scopes=["https://www.googleapis.com/auth/drive.readonly"])
            self._svc = build("drive", "v3", credentials=creds, cache_discovery=False)
        return self._svc
    def list(self):
        if self._items is not None:
            return self._items
        s = self._service(); out = []; seen = set(); stack = list(self.c["folder_ids"])
        cap = self.c.get("max_download_mb", 40) << 20
        while stack:
            fid = stack.pop()
            if fid in seen:
                continue
            seen.add(fid); tok = None
            while True:
                r = s.files().list(q=f"'{fid}' in parents and trashed=false", pageSize=200, pageToken=tok,
                                   fields="nextPageToken,files(id,name,mimeType,size)",
                                   supportsAllDrives=True, includeItemsFromAllDrives=True).execute()
                for f in r.get("files", []):
                    if f["mimeType"] == "application/vnd.google-apps.folder":
                        stack.append(f["id"])
                    elif f["name"].lower().endswith(IMG_EXT) and int(f.get("size", 0)) <= cap:
                        out.append({"id": "drive:" + f["id"], "name": os.path.splitext(f["name"])[0], "ref": f["id"]})
                tok = r.get("nextPageToken")
                if not tok:
                    break
        self._items = out
        log.info("Drive: %d images found", len(out))
        return out
    def fetch(self, item, dest):
        from googleapiclient.http import MediaIoBaseDownload
        buf = io.BytesIO()
        dl = MediaIoBaseDownload(buf, self._service().files().get_media(fileId=item["ref"], supportsAllDrives=True))
        done = False
        while not done:
            _, done = dl.next_chunk()
        tmp = Path(dest).with_suffix(".orig")
        tmp.parent.mkdir(parents=True, exist_ok=True); tmp.write_bytes(buf.getvalue())
        try:
            return prep(tmp, dest)
        finally:
            tmp.unlink(missing_ok=True)

class PexelsSource:
    name = "pexels"
    def __init__(self, cfg):
        self.key = os.environ.get(cfg["sources"]["pexels"]["api_key_env"], "")
    def search(self, query, rng):
        if not self.key:
            return []
        d = http_json("https://api.pexels.com/v1/search", headers={"Authorization": self.key},
                      params={"query": query, "per_page": 40, "page": rng.randint(1, 3), "orientation": "portrait"})
        return [{"id": "pexels:%s" % p["id"], "name": "pexels-%s" % p["id"], "url": p["src"].get("large2x") or p["src"]["original"],
                 "w": p["width"], "h": p["height"], "text": " ".join([p.get("alt") or "", p.get("url") or ""]),
                 "credit": "Photo by %s on Pexels" % p.get("photographer", "?")} for p in d.get("photos", [])]
    def fetch(self, item, dest):
        http_file(item["url"], str(dest) + ".orig"); return _finish(dest)

class OpenverseSource:
    """Only CC0 and public-domain images, so no attribution is needed."""
    name = "openverse"
    def __init__(self, cfg):
        self.lic = cfg["sources"]["openverse"].get("licenses", "cc0,pdm")
    def search(self, query, rng):
        d = http_json("https://api.openverse.org/v1/images/", params={
            "q": query, "license": self.lic, "category": "photograph", "page_size": 30, "page": rng.randint(1, 2), "extension": "jpg"})
        out = []
        for p in d.get("results", []):
            if not p.get("url"):
                continue
            out.append({"id": "openverse:%s" % p["id"], "name": "openverse-%s" % p["id"], "url": p["url"],
                        "w": p.get("width") or 0, "h": p.get("height") or 0,
                        "text": " ".join([p.get("title") or ""] + [t.get("name", "") for t in p.get("tags") or []]),
                        "credit": "%s (%s, via Openverse)" % (p.get("creator") or "unknown", (p.get("license") or "").upper())})
        return out
    def fetch(self, item, dest):
        http_file(item["url"], str(dest) + ".orig"); return _finish(dest)

def _finish(dest):
    o = Path(str(dest) + ".orig")
    try:
        return prep(o, dest)
    finally:
        o.unlink(missing_ok=True)

# ---------------------------------------------------------------- picker
class Picker:
    def __init__(self, cfg, ledger, today, rng, cache=None, drive=None, web=None):
        self.cfg, self.led, self.today, self.rng = cfg, ledger, today, rng
        self.cache = Path(cache or ROOT / "cache")
        self.meta = load_yaml("photo_meta.yaml")
        s = cfg["sources"]
        self.pool = []          # own photos (Drive / local)
        if drive is not None:
            self.pool.append(drive)
        else:
            if s["drive"]["enabled"] and os.environ.get(s["drive"]["service_account_env"]):
                self.pool.append(DriveSource(cfg))
            if s["local"]["enabled"]:
                self.pool.append(LocalSource(cfg))
        self.web = web if web is not None else [x(cfg) for k, x in (("pexels", PexelsSource), ("openverse", OpenverseSource)) if s[k]["enabled"]]
        self.notes = []
        self.tried = set()

    def _meta(self, name):
        return self.meta.get(name) or self.meta.get(name.split(".")[0])

    def _load(self, src, item, kind, flags, extra=None):
        dest = self.cache / src.name / (hashlib.md5(item["id"].encode()).hexdigest()[:16] + ".jpg")
        try:
            if not dest.exists():
                src.fetch(item, dest)
            im = Image.open(dest); w, h = im.size
        except Exception as e:
            log.warning("fetch failed %s: %s", item["id"], e); return None
        if min(w, h) < self.cfg["photos"]["min_short_side"]:
            return None
        hv = L.dhash(dest)
        why = self.led.blocked(["name:" + item["name"], item["id"]], hv, self.today, self.cfg)
        if why:
            log.info("skip %s: %s", item["id"], why); return None
        if not self.cfg["photos"]["allow_people_photos"] and has_face(dest):
            log.info("skip %s: face detected", item["id"]); return None
        e = extra or {}
        return Photo(item["id"], item["name"], src.name, str(dest), kind, e.get("credit", "Arah Rides" if src.name in ("drive", "local") else ""),
                     e.get("text", ""), flags, hv, w, h)

    def _own(self, want):
        cands = []
        for src in self.pool:
            try:
                items = src.list()
            except Exception as e:
                self.notes.append("%s unavailable: %s" % (src.name, e)); continue
            for it in items:
                if it["id"] in self.tried or self.led.blocked(["name:" + it["name"], it["id"]], None, self.today, self.cfg):
                    continue
                m = self._meta(it["name"]); q = 3
                if m:
                    if m["kind"] != want or (m["people"] and not self.cfg["photos"]["allow_people_photos"]) or m["quality"] < 3:
                        continue
                    q = m["quality"]; flags = [] 
                else:
                    if want != "car" or not self.cfg["photos"]["allow_unreviewed_drive"]:
                        continue
                    flags = ["New Drive photo I have not looked at: check the picture"]
                cands.append((-q, self.rng.random(), src, it, flags))
        cands.sort(key=lambda t: t[:2])
        for _, _, src, it, flags in cands[:25]:
            self.tried.add(it["id"])
            p = self._load(src, it, want, flags)
            if p:
                if self._meta(it["name"]) and self._meta(it["name"]).get("plate_visible"):
                    p.flags.append("Number plate visible (kept sharp on purpose)")
                return p
        return None

    def car(self):
        return self._own("car")

    def scene(self, query, place=None):
        """Scenery photo for a place: free web photos first, then own scenery photos."""
        for web in self.web:
            try:
                items = web.search(query, self.rng)
            except Exception as e:
                self.notes.append("%s search failed: %s" % (web.name, str(e)[:80])); continue
            self.rng.shuffle(items)
            good = [i for i in items if min(i.get("w", 9999), i.get("h", 9999)) >= self.cfg["photos"]["min_short_side"]
                    and i["id"] not in self.tried and not self.led.blocked(["name:" + i["name"], i["id"]], None, self.today, self.cfg)]
            if place:   # prefer pictures whose own description names the place
                good.sort(key=lambda i: 0 if place.lower() in i.get("text", "").lower() else 1)
            for it in good[:8]:
                self.tried.add(it["id"])
                p = self._load(web, it, "scenery", ["Web photo: check it shows Jamaica and has no recognisable people or brands"],
                               {"credit": it.get("credit", ""), "text": it.get("text", "")})
                if p:
                    p.flags.append("Place confirmed by photo description" if place and place.lower() in p.text.lower()
                                   else "Place NOT confirmed by the photo description")
                    return p
        return self._own("scenery")
