"""Redo every post that is not approved yet (and not already published), from now on.
Approved posts are never touched. Photos from the thrown-away drafts go back in the pool."""
import datetime as dt, random, logging
from . import queue as Q
from .config import now as now_fn
from .ledger import Ledger
from .photos import Picker
from .generate import generate_day
from .render import render_all

log = logging.getLogger("regen")

def run(cfg, start=None, picker=None, led=None, render=True):
    now = now_fn(cfg); led = led or Ledger(); notes = []
    dec = Q.decisions(); pub = Q.published()
    start = dt.date.fromisoformat(start) if start else now.date()
    dropped = kept = 0
    for off in range(0, cfg["days_ahead"] + 1):
        d = start + dt.timedelta(days=off); day = Q.load_day(str(d))
        if day is None:
            continue
        keep = []
        for p in day["posts"]:
            approved = (dec.get(p["id"]) or {}).get("decision") == "approve"
            if approved or p["id"] in pub or dt.datetime.fromisoformat(p["slot"]) <= now:
                keep.append(p); kept += 1; continue
            dropped += 1
            for im in p["images"]:
                (Q.DOCS / im).unlink(missing_ok=True)
            (Q.DOCS / "decisions" / f"{p['id']}.json").unlink(missing_ok=True)
            if p.get("photo"):
                led.release(p["photo"]["id"], p["photo"]["name"], p["date"])
        Q.save_day(str(d), keep)
    picker = picker or Picker(cfg, led, now.date(), random.Random())
    for off in range(-30, cfg["days_ahead"] + 1):       # posts kept from before series spacing existed still count toward it
        day = Q.load_day(str(start + dt.timedelta(days=off)))
        for p in (day or {"posts": []})["posts"]:
            ph = p.get("photo")
            if ph and ph.get("source") in ("drive", "local") and not any(e.get("id") == ph["id"] for e in led.data["series"]):
                led.data["series"].append({"s": picker._series(ph["name"]), "date": p["date"], "id": ph["id"]})
    made = []
    for off in range(0, cfg["days_ahead"] + 1):
        d = start + dt.timedelta(days=off); day = Q.load_day(str(d))
        keep = day["posts"] if day else []
        skip = {p["slot"][11:16] for p in keep}
        picker.today = d
        new = generate_day(cfg, led, picker, d, now, render, notes, skip=skip)
        if new:
            Q.save_day(str(d), sorted(keep + new, key=lambda p: p["slot"])); made.append((str(d), len(new)))
    notes += picker.notes
    led.prune(now.date()); led.save()
    Q.write_index(sorted(set(notes)), now.isoformat())
    return made, kept, dropped, notes
