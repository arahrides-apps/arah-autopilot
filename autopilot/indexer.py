"""Index new own photos by where they were taken. Reads each photo's GPS point, names the place, and records it so the picker
only uses the photo for that place. Writes content/photo_meta_auto.yaml and a visual check page, docs/photo_index.html.
Photos with no GPS point (screenshots, WhatsApp copies, most .webp) are listed as 'unplaced' and stay unused until you label them."""
import json, logging, html, datetime as dt
from pathlib import Path
from PIL import Image
import yaml
from . import photos as P, gazetteer as G, vision as V
from .config import ROOT, load_yaml

log = logging.getLogger("index")
AUTO = ROOT / "content" / "photo_meta_auto.yaml"
TAGS = ROOT / "content" / "photo_tags_auto.yaml"
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

def _from_label(base, lab, conf, alt):
    f = dict(V.L[lab][1])
    if f.get("kind") == "skip":
        return dict(base, kind="unplaced", about="Looks like a screenshot, document or selfie: not used", series="unplaced", ai=True, label=lab, confidence=conf)
    kind = f.pop("kind"); people = f.pop("people", base["people"])
    return dict(base, kind=kind, people=bool(people), series="own-ai-" + lab.replace(" ", "-"), auto=True, ai=True, label=lab, confidence=conf, runner_up=alt,
                **{k: v for k, v in f.items() if k != "about"}, about=f.get("about", lab) + " (recognised from the picture, %d%% sure) - own photo" % round(conf * 100))

def _recognise(done, pending, pk, manual):
    """Photos with no GPS: say what they show by picture content, and copy the label of a near-identical photo you already labelled."""
    if not V.available():
        log.warning("vision libraries not installed: unplaced photos stay unplaced"); return 0
    paths = [d for _, d in pending]
    refs = None
    try:
        rp, re_ = [], []
        for src in pk.pool:
            for it in src.list():
                m = manual.get(it["id"]) or manual.get(it["name"])
                if m and m.get("kind") == "scenery" and len(rp) < 150:
                    d = pk.cache / src.name / (__import__("hashlib").md5(it["id"].encode()).hexdigest()[:16] + ".jpg")
                    try:
                        if not d.exists(): src.fetch(it, d)
                        rp.append(d); re_.append(m)
                    except Exception:
                        pass
        if rp:
            refs = (V.embed_images(rp), re_)
    except Exception as e:
        log.warning("reference photos skipped: %s", e)
    out = V.classify(paths, refs=refs) or []; n = 0
    for (pid, d), (lab, conf, alt, ref) in zip(pending, out):
        base = done[pid]
        if ref:                                              # near copy of a photo you labelled: same label
            m, sim = ref
            done[pid] = dict(base, kind=m.get("kind", "scenery"), about=m.get("about", "") + " (matches your labelled photo, %d%% alike)" % round(sim * 100),
                             series=m.get("series", "own-matched"), place=m.get("place", ""), people=m.get("people", base["people"]), auto=True, ai=True, label="matched", confidence=round(sim, 2))
            n += 1
        elif lab:
            done[pid] = _from_label(base, lab, conf, alt); n += 1
        else:
            done[pid] = dict(base, label=None, guess=alt, confidence=conf)
    return n

def _retag(pk, manual, done, cap=600):
    """Look at EVERY own photo (JTB, Drive, hand-labelled or not) and record what it shows. The picker adds these words to the photo's label when it
    searches, so a photo labelled only 'Kingston Carnival Dance' also matches 'dance', 'people' or 'street'. Hand labels are never changed.
    Returns the list of photos whose picture seems to disagree with their label."""
    if not V.available():
        return []
    tags = dict(yaml.safe_load(open(TAGS)) or {}) if TAGS.exists() else {}
    todo = []
    for src in pk.pool:
        for it in src.list():
            if it["id"] in tags or len(todo) >= cap:
                continue
            d = pk.cache / src.name / (__import__("hashlib").md5(it["id"].encode()).hexdigest()[:16] + ".jpg")
            try:
                if not d.exists(): src.fetch(it, d)
                todo.append((it, d))
            except Exception as e:
                log.warning("could not fetch %s: %s", it["id"], e)
    for i in range(0, len(todo), 64):
        chunk = todo[i:i + 64]
        for (it, d), (lab, conf, alt, ref) in zip(chunk, V.classify([d for _, d in chunk]) or []):
            tags[it["id"]] = {"name": it["name"], "label": lab, "confidence": conf, "also": alt, "words": V.L[lab][1].get("about", lab) if lab else ""}
    TAGS.write_text("# Made by index-photos: what each photo looks like (picture recognition). Used to widen matching; hand labels are never changed.\n" + yaml.safe_dump(tags, sort_keys=True, allow_unicode=True))
    bad = []
    for pid, t in tags.items():
        m = manual.get(pid) or manual.get(t["name"]) or manual.get(t["name"].split(".")[0])
        if m and t["label"] and t["confidence"] >= 0.7 and t["label"] not in ("people", "road trip", "not usable"):
            words = [w for w in __import__("re").findall(r"[a-z]{4,}", (V.L[t["label"]][1].get("about", t["label"])).lower())][:4]
            if not any(w in (m.get("about", "") + " " + str(m.get("place", ""))).lower() for w in words):
                bad.append((pid, m, t))
    return bad

def run(cfg, picker=None, limit=400):
    pk = picker or P.Picker(cfg, None, dt.date.today(), __import__("random").Random(1))
    done = dict(yaml.safe_load(open(AUTO)) or {}) if AUTO.exists() else {}
    manual = load_yaml("photo_meta.yaml")
    new = 0; pending = []; THUMBS.mkdir(parents=True, exist_ok=True); rows = []
    for src in pk.pool:
        for it in src.list():
            if it["id"] in manual or it["name"] in manual:
                continue
            dest = pk.cache / src.name / (__import__("hashlib").md5(it["id"].encode()).hexdigest()[:16] + ".jpg")
            if it["id"] in done:
                d0 = done[it["id"]]                      # earlier run left it unplaced and never looked at the picture: look now
                if d0.get("kind") == "unplaced" and "label" not in d0 and V.available() and len(pending) < 300:
                    try:
                        if not dest.exists(): src.fetch(it, dest)
                        pending.append((it["id"], dest))
                    except Exception as e:
                        log.warning("could not fetch %s: %s", it["id"], e)
                continue
            if new >= limit:
                break
            try:
                if not dest.exists():
                    src.fetch(it, dest)
                info = {}
                sc = Path(str(dest) + ".exif.json")
                if sc.exists():
                    info = json.loads(sc.read_text())
                done[it["id"]] = _entry(it, dest, info); new += 1
                if done[it["id"]]["kind"] == "unplaced": pending.append((it["id"], dest))
                th = THUMBS / (dest.stem + ".jpg"); im = Image.open(dest); im.thumbnail((360, 360)); im.save(th, quality=80)
            except Exception as e:
                log.warning("could not index %s: %s", it["id"], e)
    # also retry earlier unplaced photos that were never recognised
    try:
        _recognise(done, pending, pk, manual) if pending else None
    except Exception as e:
        log.warning("recognition failed: %s", e)
    AUTO.write_text("# Made by `python -m autopilot index-photos` from each photo's GPS point. Edit freely: change kind/about/people, or delete a line to re-index it.\n" + yaml.safe_dump(done, sort_keys=True, allow_unicode=True))
    try:
        bad = _retag(pk, manual, done)
    except Exception as e:
        log.warning("retag failed: %s", e); bad = []
    _report(done, pk, bad)
    return new, done

def _report(done, pk, bad=()):
    groups = {}
    for pid, m in done.items():
        g = m.get("place") or (("Recognised: " + m["label"]) if m.get("ai") and m.get("label") else None) or {"unplaced": "UNPLACED (no GPS: tell me where these are)", "not-jamaica": "NOT JAMAICA (never used)"}.get(m["kind"], m["kind"])
        groups.setdefault(g, []).append((pid, m))
    out = ["<!doctype html><meta charset=utf-8><meta name=viewport content='width=device-width,initial-scale=1'><title>Photo index</title>",
           "<style>body{font:15px system-ui;margin:16px;background:#fff;color:#111}h2{margin:24px 0 6px}.g{display:flex;flex-wrap:wrap;gap:8px}.c{width:150px;font-size:11px}img{width:150px;height:150px;object-fit:cover;border-radius:6px}</style>",
           "<h1>Photo index</h1><p>Each own photo and the place its GPS point says. Wrong? Edit content/photo_meta_auto.yaml.</p>"]
    for g in sorted(groups, key=lambda k: (k.startswith(("UNPLACED", "NOT")), k)):
        out.append("<h2>%s (%d)</h2><div class=g>" % (html.escape(g), len(groups[g])))
        for pid, m in groups[g]:
            stem = __import__("hashlib").md5(pid.encode()).hexdigest()[:16]
            out.append("<div class=c><img loading=lazy src='media/index/%s.jpg'><br>%s</div>" % (stem, html.escape(pid.split(":")[-1][:14] + (" 👤" if m.get("people") else "") + (" %d%%" % round(m["confidence"] * 100) if m.get("ai") else "") + ((" ?" + m["guess"]) if m.get("guess") else ""))))
        out.append("</div>")
    if bad:
        out.append("<h2>CHECK THESE: the picture may not match its label (%d)</h2><p>Label on the left of the arrow, what the picture looks like on the right. Not changed: fix the label in content/photo_meta.yaml if the picture is right.</p><div class=g>" % len(bad))
        for pid, m, t in bad[:120]:
            stem = __import__("hashlib").md5(pid.encode()).hexdigest()[:16]
            out.append("<div class=c><img loading=lazy src='media/index/%s.jpg'><br>%s<br>&rarr; %s %d%%</div>" % (stem, html.escape(m.get("about", "")[:50]), html.escape(t["label"]), round(t["confidence"] * 100)))
        out.append("</div>")
    (ROOT / "docs" / "photo_index.html").write_text("\n".join(out))
