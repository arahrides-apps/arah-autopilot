"""Music for Reels: only your own instrumental tracks in content/music/ (mp3/m4a). Sound is otherwise added in the Instagram app,
where the trending sounds are; the automatic music-site downloader was removed."""
import os, json, re, random, logging
from pathlib import Path
from .config import ROOT

log = logging.getLogger("music")
OWN = ROOT / "content" / "music"
CACHE = ROOT / "cache" / "music"
META = CACHE / "tracks.json"

def _meta():
    try: return json.loads(META.read_text())
    except Exception: return {}

def _save(m):
    CACHE.mkdir(parents=True, exist_ok=True); META.write_text(json.dumps(m, indent=1))


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
