"""Royalty-free INSTRUMENTAL music for Reels (no vocals), pulled automatically on GitHub from Openverse (api.openverse.org, no key needed).

Only tracks whose licence allows commercial use are taken: CC0 (no credit needed) and CC BY (credit needed:
the Reel's caption gets a short 'Music:' credit line). Upbeat reggae, dancehall, soca, afrobeat and tropical styles first.
Your own tracks in content/music/ (mp3/m4a) are always used first. Downloads live in cache/music and are re-fetched as needed."""
import os, json, re, random, logging
from pathlib import Path
from .config import ROOT

log = logging.getLogger("music")
OWN = ROOT / "content" / "music"
CACHE = ROOT / "cache" / "music"
META = CACHE / "tracks.json"
QUERIES = ["reggae instrumental", "dancehall riddim instrumental", "soca instrumental", "afrobeat instrumental", "tropical house instrumental",
           "caribbean instrumental", "steel drum instrumental", "dub instrumental", "reggae riddim", "island instrumental", "afro house instrumental", "upbeat summer instrumental"]
INSTRUMENTAL = re.compile(r"instrumental|riddim|\bbeat\b|\bdub\b|no vocals?|without vocals|karaoke|backing track|loop", re.I)
VOCALS = re.compile(r"\b(vocals?|vocal mix|feat\.?|ft\.|featuring|lyrics?|singer|sings|sung|rap|rapper|acapella|a cappella|song with|voice)\b", re.I)
JUNK = re.compile(r"\b(sad|dark|horror|ambient drone|meditation|sleep|noise|field recording|podcast|speech|lecture|interview|choir|funeral|ringtone|sound effect|sfx)\b", re.I)

def _meta():
    try: return json.loads(META.read_text())
    except Exception: return {}

def _save(m):
    CACHE.mkdir(parents=True, exist_ok=True); META.write_text(json.dumps(m, indent=1))

def fetch(want=20):
    """Fill cache/music with up to `want` commercial-use tracks. Safe to call every run (stops when it has enough)."""
    import requests
    m = _meta(); have = [k for k, v in m.items() if (CACHE / v["file"]).exists()]
    if len(have) >= want:
        return len(have)
    fails = 0
    for q in QUERIES:
        if len(have) >= want or fails >= 2:                    # Openverse not answering: carry on without waiting
            break
        try:
            r = requests.get("https://api.openverse.org/v1/audio/", timeout=15, headers={"User-Agent": "arah-autopilot"},
                             params={"q": q, "license_type": "commercial,modification", "category": "music", "page_size": 20})
            r.raise_for_status(); res = r.json().get("results", [])
        except Exception as e:
            fails += 1; log.warning("music search failed (%s): %s", q, e); continue
        for t in res:
            if len(have) >= want:
                break
            lic = (t.get("license") or "").lower()
            if lic not in ("cc0", "by", "pdm"):                     # commercial use, no share-alike / no non-commercial
                continue
            dur = (t.get("duration") or 0) / 1000
            if dur and not (25 <= dur <= 600):
                continue
            title = t.get("title") or ""; tags = " ".join(x.get("name", "") for x in t.get("tags") or [])
            if JUNK.search(title + " " + tags) or t["id"] in m:
                continue
            if not INSTRUMENTAL.search(title + " " + tags + " " + q) or VOCALS.search(title + " " + tags):   # instrumental only
                continue
            if not INSTRUMENTAL.search(title + " " + tags):          # the search said instrumental but the track itself does not: skip to be safe
                continue
            url = t.get("url") or ""
            if not url or not re.search(r"\.(mp3|m4a|ogg|wav)(\?|$)", url, re.I):
                continue
            f = f"{t['id']}{Path(url.split('?')[0]).suffix.lower() or '.mp3'}"
            try:
                with requests.get(url, timeout=120, stream=True) as d:
                    d.raise_for_status(); CACHE.mkdir(parents=True, exist_ok=True)
                    with open(CACHE / f, "wb") as out:
                        for chunk in d.iter_content(1 << 16): out.write(chunk)
                if (CACHE / f).stat().st_size < 200_000:
                    (CACHE / f).unlink(); continue
            except Exception as e:
                log.warning("music download failed: %s", e); continue
            m[t["id"]] = {"file": f, "title": title, "creator": t.get("creator") or "", "license": lic,
                          "source": t.get("foreign_landing_url") or "", "style": q}
            have.append(t["id"]); _save(m)
    return len(have)

def tracks():
    """[(path, credit or None)]: your own tracks first, then the downloaded ones."""
    own = sorted(OWN.glob("*.mp3")) + sorted(OWN.glob("*.m4a")) if OWN.exists() else []
    out = [(p, None) for p in own]
    for k, v in _meta().items():
        p = CACHE / v["file"]
        if p.exists():
            credit = None if v["license"] in ("cc0", "pdm") else f"🎵 Music: {v['title']} by {v['creator']} (CC BY)"
            out.append((p, credit))
    return out

def pick(seed, used_today=()):
    t = [x for x in tracks() if str(x[0]) not in used_today] or tracks()
    return t[seed % len(t)] if t else (None, None)
