"""Real video clips for Reels, from three places, in this order:

  1. YOUR OWN clips in the Drive folder (mp4 / mov anywhere under the Arah Rides Content folder). They always come first.
     Name them for what they show ("Negril beach sunset.mp4", "jerk stop Boston.mov", "family at airport.mp4") or put them in a
     sub-folder with that name: the name is how a clip is matched to a post's words.
  2. Pexels videos (PEXELS_API_KEY, free, commercial use allowed): the biggest free library of Caribbean footage.
  3. Wikimedia Commons videos (no key): real footage filmed in Jamaica, public domain / CC0 / CC BY only, filmed 2008 or later.
     CC BY clips are credited in the caption.
  4. Pixabay videos (PIXABAY_API_KEY, same key as the photos).

Every clip is checked by the AI on a frame (Jamaica, and it must fit the words) and is never used twice (data/clip_use.json).
Your own clips are trusted to be Jamaica, so only the fit is checked."""
import os, json, re, logging, subprocess, hashlib
from pathlib import Path
from .config import ROOT

log = logging.getLogger("webvideo")
CACHE = ROOT / "cache" / "webclips"
ADDED = [0]
COUNT = {"own": 0, "pexels": 0, "wikimedia": 0, "pixabay": 0}
CREDITS = {}                   # clip key -> credit line for the caption (CC BY clips)
KEYS = {}                      # local path -> clip key, so a post can record which clips it used

VID_EXT = (".mp4", ".mov", ".m4v", ".webm")
_CACHE_Q = {}


# ---------------------------------------------------------------- sources: each returns a list of hits
# hit = {"key", "tags" (words to match), "duration", "src" (url) or "drive" (file id), "own" (bool)}

def _get(url, params=None, headers=None):
    import requests, time
    for attempt in range(3):
        try:
            r = requests.get(url, params=params, headers=headers, timeout=30)
            if r.status_code == 429:
                time.sleep(20 * (attempt + 1)); continue
            r.raise_for_status(); return r.json()
        except Exception as e:
            log.warning("video search failed (%s): %s", url, e); return None
    return None

def _pixabay(q, n=30):
    key = os.environ.get("PIXABAY_API_KEY")
    if not key:
        return []
    j = _get("https://pixabay.com/api/videos/", {"key": key, "q": q[:100], "per_page": n, "safesearch": "true", "video_type": "film"}) or {}
    out = []
    for h in j.get("hits", []):
        if h.get("type") and h["type"] != "film":
            continue
        v = h.get("videos", {}); src = (v.get("medium") or v.get("large") or v.get("small") or {}).get("url")
        if src:
            out.append({"key": f"pixabay-video:{h['id']}", "tags": (h.get("tags") or "").lower(), "duration": h.get("duration", 0), "src": src, "own": False, "via": "pixabay"})
    return out

def _pexels(q, n=30):
    key = os.environ.get("PEXELS_API_KEY")
    if not key:
        return []
    out = []
    for orient in ("portrait", None):                       # vertical clips first: they fill a Reel without cropping
        params = {"query": q[:100], "per_page": n}
        if orient: params["orientation"] = orient
        j = _get("https://api.pexels.com/videos/search", params, {"Authorization": key}) or {}
        for v in j.get("videos", []):
            files = [f for f in v.get("video_files", []) if (f.get("file_type") or "").endswith("mp4") and f.get("link")]
            # a file around 1080 wide/tall: sharp enough, small enough to download quickly
            files.sort(key=lambda f: abs(min(f.get("width") or 0, f.get("height") or 0) - 1080))
            if not files:
                continue
            slug = re.sub(r"[-/]", " ", (v.get("url") or "").rstrip("/").rsplit("/", 1)[-1])
            slug = re.sub(r"\b\d+\b", "", slug)
            out.append({"key": f"pexels-video:{v['id']}", "tags": slug.lower(), "duration": v.get("duration", 0), "src": files[0]["link"], "own": False, "via": "pexels"})
        if len(out) >= 10:
            break
    return out

def _wikimedia(q, n=30):
    """Wikimedia Commons video search. Takes the 720p transcode (small, quick to download); old footage (before 2008) is skipped."""
    from .photos import WikimediaSource, re_tags
    j = _get("https://commons.wikimedia.org/w/api.php", {
        "action": "query", "format": "json", "generator": "search", "gsrsearch": q + " filetype:video", "gsrnamespace": 6, "gsrlimit": n,
        "prop": "videoinfo", "viprop": "url|size|mime|extmetadata|derivatives"}, WikimediaSource.UA) or {}
    out = []
    for pg in (j.get("query", {}).get("pages") or {}).values():
        vi = (pg.get("videoinfo") or [{}])[0]; md = vi.get("extmetadata") or {}
        if not WikimediaSource.free(md):
            continue
        when = (md.get("DateTimeOriginal") or {}).get("value") or (md.get("DateTime") or {}).get("value") or ""
        ym = re.search(r"(19\d\d|20\d\d)", when)
        if ym and int(ym.group(1)) < 2008:
            continue
        ders = [d for d in vi.get("derivatives") or [] if d.get("src") and re.search(r"(720|480|1080)p", d.get("src", ""))]
        ders.sort(key=lambda d: (0 if "720p" in d["src"] else 1 if "480p" in d["src"] else 2, 0 if "vp9" in d["src"] else 1))
        src = ders[0]["src"] if ders else (vi.get("url") if int(vi.get("size") or 0) < (80 << 20) else None)
        if not src:
            continue
        dur = float((md.get("Duration") or {}).get("value") or vi.get("duration") or 10) if str((md.get("Duration") or {}).get("value") or "").replace(".", "").isdigit() else 10
        text = (pg.get("title") or "") + " " + re_tags((md.get("ImageDescription") or {}).get("value") or "") + " " + re_tags((md.get("Categories") or {}).get("value") or "").replace("|", " ")
        lic = (md.get("LicenseShortName") or {}).get("value") or "public domain"
        who = re_tags((md.get("Artist") or {}).get("value") or "").strip()[:50] or "unknown"
        key = f"wikimedia-video:{pg['pageid']}"
        if lic.lower().startswith("cc by"):
            CREDITS[key] = f"🎥 Video: {who}, Wikimedia Commons ({lic})"
        out.append({"key": key, "tags": text.lower(), "duration": dur, "src": src, "own": False, "via": "wikimedia", "convert": True})
    return out

_OWN = None
def _own_list():
    """Every video file under the Drive folder(s), with its file name and folder names as its words."""
    global _OWN
    if _OWN is not None:
        return _OWN
    _OWN = []
    try:
        from .config import load as _load
        c = _load()["sources"]["drive"]
        raw = os.environ.get(c["service_account_env"], "")
        if not (c.get("enabled") and raw):
            return _OWN
        from google.oauth2 import service_account
        from googleapiclient.discovery import build
        creds = service_account.Credentials.from_service_account_info(json.loads(raw), scopes=["https://www.googleapis.com/auth/drive.readonly"])
        s = build("drive", "v3", credentials=creds, cache_discovery=False)
        stack = [(f, "") for f in c["folder_ids"]]; seen = set()
        while stack:
            fid, path = stack.pop()
            if fid in seen:
                continue
            seen.add(fid); tok = None
            while True:
                r = s.files().list(q=f"'{fid}' in parents and trashed=false", pageSize=200, pageToken=tok,
                                   fields="nextPageToken,files(id,name,mimeType,size,videoMediaMetadata,thumbnailLink)",
                                   supportsAllDrives=True, includeItemsFromAllDrives=True).execute()
                for f in r.get("files", []):
                    if f["mimeType"] == "application/vnd.google-apps.folder":
                        stack.append((f["id"], path + " " + f["name"]))
                    elif f["name"].lower().endswith(VID_EXT) and int(f.get("size", 0)) <= (300 << 20):
                        dur = int((f.get("videoMediaMetadata") or {}).get("durationMillis", 0)) / 1000 or 10
                        words = re.sub(r"[_\-.]", " ", path + " " + os.path.splitext(f["name"])[0]).lower()
                        _OWN.append({"key": "drive-video:" + f["id"], "tags": words + " " + _labels().get(f["id"], ""), "duration": dur, "drive": f["id"],
                                     "own": True, "via": "own", "thumb": f.get("thumbnailLink")})
                tok = r.get("nextPageToken")
                if not tok:
                    break
        log.info("Drive: %d video clips found", len(_OWN))
        _label_new(creds)
    except Exception as e:
        log.warning("Drive clip listing failed: %s", e)
    return _OWN

LABELS = ROOT / "content" / "clip_labels.json"
_LAB = None
def _labels():
    global _LAB
    if _LAB is None:
        try: _LAB = json.loads(LABELS.read_text())
        except Exception: _LAB = {}
    return _LAB

def _label_new(creds, most=40):
    """Phone clips are named like IMG_4521.MOV, so their names say nothing. Gemini looks at each clip's Drive preview image ONCE and
    describes it in keywords (beach, road, car, family, jerk, waterfall...); the words are saved in content/clip_labels.json and used to
    match clips to posts. Up to 40 new clips a run."""
    from . import vision as V
    if not V.ai_on():
        return
    lab = _labels(); todo = [h for h in _OWN if h["drive"] not in lab and h.get("thumb")][:most]
    if not todo:
        return
    try:
        import requests
        from google.auth.transport.requests import Request
        creds.refresh(Request())
    except Exception as e:
        log.warning("clip labels: could not get a Drive token: %s", e); return
    n = 0
    for h in todo:
        try:
            r = requests.get(h["thumb"].replace("=s220", "=s800"), headers={"Authorization": "Bearer " + creds.token}, timeout=30)
            r.raise_for_status()
            txt = V.ask([r.content, "This is a frame from a short video. Describe what it shows in 6 to 12 lowercase keywords separated by spaces "
                         "(the place, the activity, people, food, vehicles, e.g. 'beach sea sand family swimming' or 'car road driving hills'). Keywords only."], 120) or ""
            words = " ".join(w for w in re.findall(r"[a-z]+", txt.lower()) if len(w) > 2)[:200]
            if words:
                lab[h["drive"]] = words; h["tags"] += " " + words; n += 1
        except Exception as e:
            log.warning("clip label failed: %s", e)
    if n:
        try: LABELS.write_text(json.dumps(lab, indent=0))
        except Exception: pass
        log.info("labelled %d Drive clips", n)

def _own(q):
    words = [w for w in re.findall(r"[a-z]{4,}", q.lower()) if w not in ("jamaica", "jamaican", "caribbean")]
    if not words:
        return []
    return [h for h in _own_list() if any(w[:5] in h["tags"] for w in words)]

def _search(q):
    if q not in _CACHE_Q:
        _CACHE_Q[q] = _own(q) + _pexels(q) + _wikimedia(q) + _pixabay(q)
    return _CACHE_Q[q]


# ---------------------------------------------------------------- download + checks

def _download(h, dest):
    if dest.exists() and dest.stat().st_size > 50_000:
        return True
    try:
        if h.get("drive"):
            from googleapiclient.http import MediaIoBaseDownload
            from google.oauth2 import service_account
            from googleapiclient.discovery import build
            from .config import load as _load
            c = _load()["sources"]["drive"]
            creds = service_account.Credentials.from_service_account_info(json.loads(os.environ[c["service_account_env"]]), scopes=["https://www.googleapis.com/auth/drive.readonly"])
            s = build("drive", "v3", credentials=creds, cache_discovery=False)
            tmp = dest.with_suffix(".orig")
            with open(tmp, "wb") as fh:
                dl = MediaIoBaseDownload(fh, s.files().get_media(fileId=h["drive"], supportsAllDrives=True), chunksize=8 << 20)
                done = False
                while not done:
                    _, done = dl.next_chunk()
            # phone clips (mov / HEVC / huge): make a light 1080p H.264 copy the Reel builder can use
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(tmp), "-t", "20", "-vf", "scale='if(gt(iw,ih),-2,1080)':'if(gt(iw,ih),1080,-2)'",
                            "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", str(dest)], timeout=300, check=True)
            tmp.unlink(missing_ok=True)
        else:
            import requests
            from .photos import WikimediaSource
            tmp = dest.with_suffix(".orig") if h.get("convert") else dest
            with requests.get(h["src"], timeout=180, stream=True, headers=WikimediaSource.UA) as r:
                r.raise_for_status()
                with open(tmp, "wb") as f:
                    for chunk in r.iter_content(1 << 16): f.write(chunk)
            if h.get("convert"):                                  # webm / ogv -> H.264 the Reel builder can cut fast
                subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(tmp), "-t", "20", "-vf", "scale='if(gt(iw,ih),-2,1080)':'if(gt(iw,ih),1080,-2)'",
                                "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", str(dest)], timeout=300, check=True)
                tmp.unlink(missing_ok=True)
        return dest.exists()
    except Exception as e:
        log.warning("clip download failed (%s): %s", h["key"], e)
        dest.unlink(missing_ok=True)
        return False

def _frame(path, out, at=1.5):
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", str(at), "-i", str(path), "-frames:v", "1", str(out)], timeout=60)
    return out if Path(out).exists() else None

def find(queries, text, date, want=2, used=(), strict=False):
    """-> list of local mp4 paths (at most `want`) that fit `text`, never used before. Your own Drive clips are tried first.
    strict=True (the words name a place): a web clip must be confirmed as Jamaica."""
    from . import promo as P, vision as V
    from .themes import JUNK, NOT_JAMAICA
    CACHE.mkdir(parents=True, exist_ok=True)
    out = []; seen = set(); ai = V.ai_on()
    variants = []
    for q in queries[:5]:
        base = re.sub(r"\b(jamaica|jamaican)\b", "", q, flags=re.I).strip()
        variants += [base + " Jamaica"] + ([] if (strict or not ai) else [base + " Caribbean"])   # never the subject alone: that is how snow and burgers got in
    hits = []
    for qq in dict.fromkeys(variants):
        hits += [(qq, h) for h in _search(qq)]
    hits.sort(key=lambda x: not x[1]["own"])                  # your own clips first, whatever query found them
    for qq, h in hits:
        if len(out) >= want:
            break
        key = h["key"]
        if key in seen or key in used:
            continue
        seen.add(key)
        tags = h["tags"]
        if P._pick([key], date) is None:                        # used within the no-repeat window
            continue
        if JUNK.search(tags) or h.get("duration", 0) < 3:
            continue
        if not h["own"] and NOT_JAMAICA.search(tags) and "jamaica" not in tags:
            continue
        if not ai:                                              # no AI to look at the clip: its own words must name the subject (and Jamaica, for web clips)
            words = [w for w in re.findall(r"[a-z]{4,}", qq.lower()) if w not in ("jamaica", "jamaican", "caribbean", "tropical", "aerial", "drone")]
            if (not h["own"] and "jamaica" not in tags) or (words and not any(w[:5] in tags for w in words)):
                continue
        dest = CACHE / (hashlib.md5(key.encode()).hexdigest()[:16] + ".mp4")
        if not _download(h, dest):
            continue
        fr = _frame(dest, CACHE / (dest.stem + ".jpg"))
        if not fr:
            continue
        if ai:                                                  # the AI must say yes; no answer = not used
            if not h["own"]:
                if strict and not V.jamaica_gate(str(fr), key):
                    continue
                if not strict and V.shows(str(fr), "a real video frame that could have been filmed in Jamaica or the Caribbean: tropical setting, no snow, no landmarks, signs or flags of another country") is not True:
                    continue
            if V.shows(str(fr), f"what this caption describes: \"{text[:200]}\" (same kind of place, people, food or activity)") is not True:
                continue
        P.note_use(key, date); out.append(dest); KEYS[str(dest)] = key
        ADDED[0] += 1; COUNT[h["via"]] += 1
    return out

def status():
    have = [n for n, k in (("Pexels", "PEXELS_API_KEY"), ("Pixabay", "PIXABAY_API_KEY")) if os.environ.get(k)]
    own = len(_OWN or [])
    return (f"video clips added to Reels {ADDED[0]} (your Drive clips {COUNT['own']}, Pexels {COUNT['pexels']}, Wikimedia {COUNT['wikimedia']}, Pixabay {COUNT['pixabay']})"
            f" · Drive clips found {own} · video libraries on: {', '.join(have + ['Wikimedia'])}")
