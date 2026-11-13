"""Index new own photos by where they were taken. Reads each photo's GPS point, names the place, and records it so the picker
only uses the photo for that place. Writes content/photo_meta_auto.yaml and a visual check page, docs/photo_index.html.
Photos with no GPS point (screenshots, WhatsApp copies, most .webp) are listed as 'unplaced' and stay unused until you label them."""
import json, logging, html, datetime as dt
from pathlib import Path
from PIL import Image
import yaml
from . import photos as P, gazetteer as G
from .config import ROOT, load_yaml

log = logging.getLogger("index")
AUTO = ROOT / "content" / "photo_meta_auto.yaml"
THUMBS = ROOT / "docs" / "media" / "index"

def _entry(item, dest, info):
    w, h = Image.open(dest).size
    base = {"orientation": "landscape" if w >= h else "portrait", "plate_visible": False, "credit": "", "people": bool(P.has_face(dest)), "quality": 4 if min(w, h) >= 1200 else 3}
    if "lat" not in info:
        return dict(base, kind="unplaced", about="No GPS point in this photo", series="unplaced")
    lat, lon = info["lat"], info["lon"]
    if not G.in_jamaica(lat, lon):
        return dict(base, kind="not-jamaica", about="GPS point outside Jamaica (%.3f, %.3f)" % (lat, lon), series="not-jamaica")
    n = G.nearest(lat, lon)
    if not n:
        return dict(base, kind="unplaced", about="In Jamaica but not near a known place (%.3f, %.3f)" % (lat, lon), series="unplaced", gps=[lat, lon])
    name, parish, coastal, d = n
    day = (info.get("date") or "").replace("-", "")
    return dict(base, kind="scenery", about="%s, %s (placed by GPS, %s km away) - own photo" % (name, parish, d), series="own-%s-%s" % (name.lower().replace(" ", "-").replace(",", ""), day[:6]),
                gps=[lat, lon], place=name, parish=parish, coastal=coastal, auto=True)

def run(cfg, picker=None, limit=400):
    pk = picker or P.Picker(cfg, None, dt.date.today(), __import__("random").Random(1))
    done = dict(yaml.safe_load(open(AUTO)) or {}) if AUTO.exists() else {}
    manual = load_yaml("photo_meta.yaml")
    new = 0; THUMBS.mkdir(parents=True, exist_ok=True); rows = []
    for src in pk.pool:
        for it in src.list():
            if it["id"] in done or it["id"] in manual or it["name"] in manual:
                continue
            if new >= limit:
                break
            dest = pk.cache / src.name / (__import__("hashlib").md5(it["id"].encode()).hexdigest()[:16] + ".jpg")
            try:
                if not dest.exists():
                    src.fetch(it, dest)
                info = {}
                sc = Path(str(dest) + ".exif.json")
                if sc.exists():
                    info = json.loads(sc.read_text())
                done[it["id"]] = _entry(it, dest, info); new += 1
                th = THUMBS / (dest.stem + ".jpg"); im = Image.open(dest); im.thumbnail((360, 360)); im.save(th, quality=80)
            except Exception as e:
                log.warning("could not index %s: %s", it["id"], e)
    AUTO.write_text("# Made by `python -m autopilot index-photos` from each photo's GPS point. Edit freely: change kind/about/people, or delete a line to re-index it.\n" + yaml.safe_dump(done, sort_keys=True, allow_unicode=True))
    _report(done, pk)
    return new, done

def _report(done, pk):
    groups = {}
    for pid, m in done.items():
        g = m.get("place") or {"unplaced": "UNPLACED (no GPS: tell me where these are)", "not-jamaica": "NOT JAMAICA (never used)"}.get(m["kind"], m["kind"])
        groups.setdefault(g, []).append((pid, m))
    out = ["<!doctype html><meta charset=utf-8><meta name=viewport content='width=device-width,initial-scale=1'><title>Photo index</title>",
           "<style>body{font:15px system-ui;margin:16px;background:#fff;color:#111}h2{margin:24px 0 6px}.g{display:flex;flex-wrap:wrap;gap:8px}.c{width:150px;font-size:11px}img{width:150px;height:150px;object-fit:cover;border-radius:6px}</style>",
           "<h1>Photo index</h1><p>Each own photo and the place its GPS point says. Wrong? Edit content/photo_meta_auto.yaml.</p>"]
    for g in sorted(groups, key=lambda k: (k.startswith(("UNPLACED", "NOT")), k)):
        out.append("<h2>%s (%d)</h2><div class=g>" % (html.escape(g), len(groups[g])))
        for pid, m in groups[g]:
            stem = __import__("hashlib").md5(pid.encode()).hexdigest()[:16]
            out.append("<div class=c><img loading=lazy src='media/index/%s.jpg'><br>%s</div>" % (stem, html.escape(pid.split(":")[-1][:14] + (" 👤" if m.get("people") else ""))))
        out.append("</div>")
    (ROOT / "docs" / "photo_index.html").write_text("\n".join(out))
