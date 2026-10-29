"""Files that make up the queue. Everything is plain JSON in docs/ so the review page and GitHub Actions share it."""
import json, glob, os
from pathlib import Path
from .config import ROOT

DOCS = ROOT / "docs"

def day_file(date):
    return DOCS / "queue" / f"{date}.json"

def load_day(date):
    f = day_file(date)
    return json.load(open(f)) if f.exists() else None

def save_day(date, posts):
    f = day_file(date); f.parent.mkdir(parents=True, exist_ok=True)
    json.dump({"date": date, "posts": posts}, open(f, "w"), indent=1, ensure_ascii=False)

def all_posts():
    out = []
    for f in sorted(glob.glob(str(DOCS / "queue" / "*.json"))):
        out += json.load(open(f))["posts"]
    return out

def decisions():
    out = {}
    for f in glob.glob(str(DOCS / "decisions" / "*.json")):
        try:
            d = json.load(open(f)); out[d["id"]] = d
        except Exception:
            pass
    return out

def published():
    f = DOCS / "published.json"
    return json.load(open(f)) if f.exists() else {}

def save_published(p):
    json.dump(p, open(DOCS / "published.json", "w"), indent=1)

def write_index(notes=None, now_iso=""):
    posts = all_posts()
    idx = {"generated": now_iso, "notes": notes or [], "posts": posts}
    json.dump(idx, open(DOCS / "index.json", "w"), indent=1, ensure_ascii=False)
    return idx
