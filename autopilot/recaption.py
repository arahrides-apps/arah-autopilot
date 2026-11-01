"""Gives every post that has not gone out yet the new caption ending: a plain-words search line, 5 fresh hashtags and a tagged location.
The wording of the post is kept. Approved posts keep their approval. Posts already published are never touched."""
import re, random, logging
from . import queue as Q
from .config import now as now_fn
from .generate import hashtags

log = logging.getLogger("recaption")

def _loc(cfg, post, rng):
    L = cfg["locations"]; place = None
    m = re.match(r"Scenery in (.+?), Jamaica", post.get("alt", "") or "")
    if m:
        place = m.group(1)
    if place:
        pl = place.lower()
        for k, v in L.items():
            if isinstance(v, dict) and (pl in v["name"].lower() or k.replace("_", " ") in pl):
                return {**v, "key": k}
        return {"name": place + ", Jamaica", "id": "", "tag": "#" + re.sub(r"\W", "", place), "kw": f"Car rental for {place}, Jamaica"}
    key = rng.choice(L["default_rotation"])
    return {**L[key], "key": key}

def _body(caption):
    """Strip the old hashtag line and any old search line; keep the text and the booking lines."""
    parts = caption.rstrip().split("\n\n")
    if parts and parts[-1].strip() and all(t.startswith("#") for t in parts[-1].split()):
        parts = parts[:-1]
    kws = ("Car rental in ", "Car rental at ", "Car rental for ")
    parts = [p for p in parts if not p.startswith(kws)]
    return parts

def _rewrite(cfg, post, caption, rng):
    loc = _loc(cfg, post, rng)
    parts = _body(caption)
    # put the search line just before the booking lines (the paragraph starting "Book:" / "Watch the interview")
    at = next((i for i, p in enumerate(parts) if p.startswith(("Book:", "Watch the interview"))), len(parts))
    if loc.get("kw"):
        parts.insert(at, loc["kw"])
    typ = post["type"]
    parts.append(hashtags(cfg, typ, None if not (post.get("alt") or "").startswith("Scenery in") else loc.get("tag"), loc, rng))
    return "\n\n".join(parts), loc

def run(cfg):
    now = now_fn(cfg); pub = Q.published(); dec = Q.decisions(); rng = random.Random(); n = 0
    import glob, json
    for f in sorted(glob.glob(str(Q.DOCS / "queue" / "*.json"))):
        day = json.load(open(f)); changed = False
        for p in day["posts"]:
            if (pub.get(p["id"]) or {}).get("status") in ("published", "skipped", "rejected"):
                continue
            cap, loc = _rewrite(cfg, p, p["caption"], rng)
            p["caption"] = cap; p["location"] = {"name": loc["name"], "id": loc.get("id", "")}; changed = True; n += 1
            d = dec.get(p["id"])
            if d and d.get("caption"):               # a caption edited on the review page: keep the edits, swap the ending
                dcap, _ = _rewrite(cfg, p, d["caption"], rng)
                d["caption"] = dcap
                json.dump(d, open(Q.DOCS / "decisions" / f"{p['id']}.json", "w"), indent=1, ensure_ascii=False)
        if changed:
            json.dump(day, open(f, "w"), indent=1, ensure_ascii=False)
    Q.write_index([], now.isoformat())
    return n
