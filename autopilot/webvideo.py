"""Free stock video clips for Reels (Pixabay video library, same PIXABAY_API_KEY as photos; free for commercial use).

For a Reel about Negril, jerk or a waterfall it searches the place first, then the topic, always with 'Jamaica'.
Every clip is checked by Claude on a frame (must be Jamaica and fit the words) and is never used twice (data/clip_use.json)."""
import os, json, re, logging, subprocess, datetime as dt
from pathlib import Path
from .config import ROOT

log = logging.getLogger("webvideo")
CACHE = ROOT / "cache" / "webclips"
_dead = False
ADDED = [0]

_CACHE_Q = {}

def _search(q, n=30):
    """Pixabay video search, cached for the run. On the rate limit (100 a minute) it waits and tries again instead of giving up for the whole run."""
    import requests, time
    key = os.environ.get("PIXABAY_API_KEY")
    if not key:
        return []
    if q in _CACHE_Q:
        return _CACHE_Q[q]
    for attempt in range(3):
        try:
            r = requests.get("https://pixabay.com/api/videos/", timeout=30,
                             params={"key": key, "q": q[:100], "per_page": n, "safesearch": "true", "video_type": "film"})   # real footage only, never animation
            if r.status_code == 429:
                time.sleep(20 * (attempt + 1)); continue
            r.raise_for_status()
            _CACHE_Q[q] = r.json().get("hits", []); return _CACHE_Q[q]
        except Exception as e:
            log.warning("video search failed (%s): %s", q, e); break
    _CACHE_Q[q] = []
    return []

def _frame(path, out, at=1.5):
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", str(at), "-i", str(path), "-frames:v", "1", str(out)], timeout=60)
    return out if Path(out).exists() else None

def find(queries, text, date, want=2, used=(), strict=False):
    """-> list of local mp4 paths (at most `want`) that fit `text`, never used before.
    strict=True (the words name a place): the clip must be Jamaica. Otherwise (a beach, a drive, food, a family) the search widens to
    Caribbean and then the subject alone, and Claude checks the clip could be Jamaica and fits the words."""
    from . import promo as P, vision as V
    from .themes import JUNK, NOT_JAMAICA
    CACHE.mkdir(parents=True, exist_ok=True)
    out = []; seen = set()
    variants = []
    for q in queries[:5]:
        base = re.sub(r"\b(jamaica|jamaican)\b", "", q, flags=re.I).strip()
        from . import vision as _V
        variants += [base + " Jamaica"] + ([] if (strict or not _V.ai_on()) else [base + " Caribbean"])      # never the subject alone: that is how snow and burgers got in
    for qq in list(dict.fromkeys(variants)):
        if len(out) >= want:
            break
        for h in _search(qq):
            if len(out) >= want:
                break
            key = f"pixabay-video:{h['id']}"
            if key in seen or key in used:
                continue
            seen.add(key)
            tags = (h.get("tags") or "").lower()
            if P._pick([key], date) is None:                        # used within the reuse window
                continue
            if JUNK.search(tags) or (NOT_JAMAICA.search(tags) and "jamaica" not in tags) or h.get("duration", 0) < 4:
                continue
            if h.get("type") and h.get("type") != "film":
                continue
            if not V.ai_on():                                       # no AI to look at the clip: only clips tagged Jamaica, and tagged with the subject
                words = [w for w in re.findall(r"[a-z]{4,}", qq.lower()) if w not in ("jamaica", "jamaican", "caribbean", "tropical", "aerial", "drone")]
                if "jamaica" not in tags or (words and not any(w[:5] in tags for w in words)):
                    continue
            v = h.get("videos", {}); src = (v.get("medium") or v.get("large") or v.get("small") or {}).get("url")
            if not src:
                continue
            dest = CACHE / f"{h['id']}.mp4"
            if not dest.exists():
                try:
                    import requests
                    with requests.get(src, timeout=120, stream=True) as r:
                        r.raise_for_status()
                        with open(dest, "wb") as f:
                            for chunk in r.iter_content(1 << 16): f.write(chunk)
                except Exception as e:
                    log.warning("clip download failed: %s", e); continue
            fr = _frame(dest, CACHE / f"{h['id']}.jpg")
            if not fr:
                continue
            if V.ai_on():                                           # the AI must say yes to both; no answer = not used
                if strict and not V.jamaica_gate(str(fr), key):
                    continue
                if not strict and V.shows(str(fr), "a real video frame that could have been filmed in Jamaica or the Caribbean: tropical setting, no snow, no landmarks, signs or flags of another country") is not True:
                    continue
                if V.shows(str(fr), f"what this caption describes: \"{text[:200]}\" (same kind of place, people, food or activity)") is not True:
                    continue
            P.note_use(key, date); out.append(dest); ADDED[0] += 1
    return out
