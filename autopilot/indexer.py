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
    return dict(base, kind=kind, people=bool(people), cats=V.cats_for(lab, None, bool(people)), series="own-ai-" + lab.replace(" ", "-"), auto=True, ai=True, label=lab, confidence=conf, runner_up=alt,
                **{k: v for k, v in f.items() if k != "about"}, about=f.get("about", lab) + " " + " ".join(V.cats_for(lab)) + " (recognised from the picture, %d%% sure) - own photo" % round(conf * 100))

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

def _claude_apply(done, manual, items):
    """items: [(id, dest, name)]. Claude's verdict. Fills photos the other methods could not place, and records its description for every photo."""
    res = V.claude_review([d for _, d, _ in items]) or []
    changed = 0; notes = {}
    for (pid, d, name), r in zip(items, res):
        if not r: continue
        notes[pid] = r
        m = done.get(pid)
        if m is None or manual.get(pid) or manual.get(name) or manual.get(name.split(".")[0]):
            continue                                       # hand labels are never overwritten
        if r.get("jamaica") == "no" or r.get("kind") == "not-usable":
            if m.get("kind") in ("unplaced", "scenery") and not m.get("gps"):
                done[pid] = dict(m, kind="unplaced", about="Claude: not usable (%s)" % r.get("what", ""), series="unplaced", ai=True, label="not usable"); changed += 1
            continue
        if m.get("kind") == "unplaced" and float(r.get("confidence", 0)) >= 0.6:
            k = r.get("kind", "scenery"); k = "car" if k == "car" else "scenery"
            place = (r.get("place") or "").strip()
            done[pid] = dict(m, kind=k, place=place or m.get("place", ""), parish=r.get("parish", ""), people=bool(r.get("people")), cats=V.cats_for(r.get("label"), r.get("categories"), bool(r.get("people"))), auto=True, ai=True, claude=True,
                             label=r.get("label") or "claude", confidence=float(r.get("confidence", 0)), series="own-claude-" + (place or r.get("label") or "photo").lower().replace(" ", "-"),
                             about=("%s - %s %s (Claude reviewed the picture, %d%% sure) - own photo" % (place or "Jamaica", r.get("what", ""), " ".join(V.cats_for(r.get("label"), r.get("categories"))), round(100 * float(r.get("confidence", 0))))).strip(" -"))
            changed += 1
    return changed, notes

def _retag(pk, manual, done, cap=1500):
    """Look at EVERY own photo (JTB, Drive, hand-labelled or not) and record what it shows. The picker adds these words to the photo's label when it
    searches, so a photo labelled only 'Kingston Carnival Dance' also matches 'dance', 'people' or 'street'. Hand labels are never changed.
    Returns the list of photos whose picture seems to disagree with their label."""
    if not V.available():
        return []
    import os
    tags = {} if os.environ.get("INDEX_FORCE") else (dict(yaml.safe_load(open(TAGS)) or {}) if TAGS.exists() else {})
    todo = []
    for src in pk.pool:
        for it in src.list():
            if it["id"] in tags or len(todo) >= cap:
                continue
            d = pk.cache / src.name / (__import__("hashlib").md5(it["id"].encode()).hexdigest()[:16] + ".jpg")
            try:
                if not d.exists(): src.fetch(it, d)
                th = THUMBS / (d.stem + ".jpg")
                if not th.exists():
                    im = Image.open(d); im.thumbnail((360, 360)); im.convert("RGB").save(th, quality=80)
                todo.append((it, d))
            except Exception as e:
                log.warning("could not fetch %s: %s", it["id"], e)
    web = None
    try:
        web = V.web_refs(ROOT / "cache" / "web_refs")
    except Exception as e:
        log.warning("web references skipped: %s", e)
    for i in range(0, len(todo), 64):
        chunk = todo[i:i + 64]
        cls = V.classify([d for _, d in chunk]) or []
        embs = V.embed_images([d for _, d in chunk]) if web else None
        cl_changed, notes = _claude_apply(done, manual, [(it["id"], d, it["name"]) for it, d in chunk])
        for k, ((it, d), (lab, conf, alt, ref)) in enumerate(zip(chunk, cls)):
            wm = V.web_match(embs[k], web) if web is not None else None
            if wm and (lab is None or wm[0] == lab or wm[1] >= 0.9):
                lab, conf = wm[0], max(conf, wm[1])      # looks like a free web photo of that place
            t = {"name": it["name"], "label": lab, "cats": V.cats_for(lab), "confidence": conf, "also": alt, "words": V.L[lab][1].get("about", lab) if lab else "", "web": wm[0] if wm else ""}
            c = notes.get(it["id"])
            if c:
                t["claude"] = c.get("what", ""); t["claude_place"] = c.get("place", ""); t["claude_conf"] = c.get("confidence", 0)
                t["words"] = (c.get("what", "") + " " + c.get("place", "") + " " + t["words"]).strip()
                t["cats"] = V.cats_for(c.get("label") if c.get("label") in V.L else lab, c.get("categories"), bool(c.get("people")))
                if float(c.get("confidence", 0)) >= 0.6 and c.get("label") in V.L:
                    t["label"] = c["label"]; t["confidence"] = max(float(c["confidence"]), t["confidence"] if t["label"] == lab else 0)
            tags[it["id"]] = t
        TAGS.write_text("# Made by index-photos: what each photo looks like. Used to widen matching; hand labels are never changed.\n" + yaml.safe_dump(tags, sort_keys=True, allow_unicode=True))
        AUTO.write_text("# Made by index-photos. Edit freely.\n" + yaml.safe_dump(done, sort_keys=True, allow_unicode=True))
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
    import os
    force = bool(os.environ.get("INDEX_FORCE")); limit = 3000 if force else limit
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
                if d0.get("kind") == "unplaced" and ("label" not in d0 or force) and V.available() and len(pending) < 1500:
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
    try:
        bad = _retag(pk, manual, done)
    except Exception as e:
        log.warning("retag failed: %s", e); bad = []
    AUTO.write_text("# Made by `python -m autopilot index-photos` from each photo's GPS point, picture recognition and Claude's review. Edit freely: change kind/about/people, or delete a line to re-index it.\n" + yaml.safe_dump(done, sort_keys=True, allow_unicode=True))
    try:
        _report(done, pk, bad)
    except Exception as e:
        import traceback; traceback.print_exc(); log.warning("review page failed (results still saved): %s", e)
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
    # every photo by category (people, food, beach, sunset ...): tap a button to filter
    tags = (yaml.safe_load(open(TAGS)) or {}) if TAGS.exists() else {}
    allp = {}
    for pid, t in tags.items():
        allp[pid] = (t.get("name", pid), t.get("cats") or [], t.get("label") or "")
    for pid, m in done.items():
        if m.get("cats"): allp[pid] = (pid.split(":")[-1], m["cats"], m.get("label") or "")
    counts = {c: sum(1 for v in allp.values() if c in v[1]) for c in V.CATS}
    top = ["<h2>Find photos by category</h2><div id=b style='display:flex;flex-wrap:wrap;gap:6px'><button onclick=\"f('')\">All</button>"]
    top += ["<button onclick=\"f('%s')\">%s (%d)</button>" % (c, c, n) for c, n in counts.items() if n]
    top.append("</div><div class=g id=cg style='margin-top:10px'>")
    for pid, (nm, cs, lb) in sorted(allp.items(), key=lambda kv: kv[1][0]):
        stem = __import__("hashlib").md5(pid.encode()).hexdigest()[:16]
        top.append("<div class=c data-c=' %s '><img loading=lazy src='media/index/%s.jpg'><br>%s<br><i>%s</i></div>" % (" ".join(cs), stem, html.escape(nm[:16]), html.escape(", ".join(cs))))
    top.append("</div><script>function f(c){document.querySelectorAll('#cg .c').forEach(function(e){e.style.display=(!c||e.dataset.c.indexOf(' '+c+' ')>=0)?'':'none'})}</script><hr>")
    out[3:3] = top
    (ROOT / "docs" / "photo_index.html").write_text("\n".join(out))
