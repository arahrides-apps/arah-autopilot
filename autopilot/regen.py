"""Redo every post that is not approved yet (and not already published): all of today (earlier slots included, so you can still approve and post them) and the days ahead.
Approved carousels are never touched; approved single-picture posts are rebuilt as carousels. Photos from the thrown-away drafts go back in the pool."""
import datetime as dt, random, logging
from . import config, queue as Q
from .config import now as now_fn
from .ledger import Ledger
from .photos import Picker
from .generate import generate_day
from .render import render_all

log = logging.getLogger("regen")
CONTINUE = [None]                                     # first day not rebuilt when the run clock ran out

def run(cfg, start=None, picker=None, led=None, render=True, wipe=False):
    now = now_fn(cfg); led = led or Ledger(); notes = []
    config.start_clock(cfg)                               # every slow step checks the clock and stops in time to save
    dec = Q.decisions(); pub = Q.published()
    start = dt.date.fromisoformat(start) if start else now.date()
    dropped = kept = 0
    plan = {}                                             # day -> (posts to keep, posts to redo); nothing is deleted until that day is rebuilt
    for off in range(0, cfg["days_ahead"] + 1):
        d = start + dt.timedelta(days=off); day = Q.load_day(str(d))
        if day is None:
            continue
        keep, drop = [], []
        for p in day["posts"]:
            approved = (dec.get(p["id"]) or {}).get("decision") == "approve"
            single = cfg.get("all_carousels", True) and len(p.get("images", [])) == 1 and not p.get("single")     # approved single pictures are rebuilt as carousels and need a new OK
            if wipe:                                             # reset: only posts already on Instagram survive, approved or not
                if p["id"] in pub:
                    keep.append(p); continue
            elif (approved and not single) or p["id"] in pub or (dt.datetime.fromisoformat(p["slot"]) <= now and d < now.date()):   # today's passed, unapproved posts are redrafted too
                keep.append(p); continue
            drop.append(p)
        plan[d] = (keep, drop)
    picker = picker or Picker(cfg, led, now.date(), random.Random())
    for off in range(-30, cfg["days_ahead"] + 1):       # posts kept from before series spacing existed still count toward it
        day = Q.load_day(str(start + dt.timedelta(days=off)))
        for p in (day or {"posts": []})["posts"]:
            ph = p.get("photo")
            if ph and ph.get("source") in ("drive", "local") and not any(e.get("id") == ph["id"] for e in led.data["series"]):
                led.data["series"].append({"s": picker._series(ph["name"]), "date": p["date"], "id": ph["id"]})
    made = []
    for off in range(0, cfg["days_ahead"] + 1):
        d = start + dt.timedelta(days=off)
        if d > now.date() + dt.timedelta(days=cfg["days_ahead"]):
            break                                         # a run that carries on from a later day still stops at the usual last day
        if config.out_of_time():
            notes.append(f"Run check · {d} and later are rebuilt by a follow-up run that starts by itself")
            if made: CONTINUE[0] = str(d)                 # the workflow starts one more run from this day
            break
        keep, drop = plan.get(d, ([], []))
        kept += len(keep)
        skip = {p["slot"][11:16] for p in keep}
        picker.today = d
        new = generate_day(cfg, led, picker, d, now, render, notes, skip=skip) or []
        done = {p["slot"] for p in new}
        fresh = {f for p in new for f in p["images"] + [p.get("reel")] if f}
        late = config.out_of_time()
        left = []
        for p in drop:                                    # clear only the drafts that were actually replaced
            if late and p["slot"] not in done:            # ran out of time before this slot was rebuilt: its current draft stays
                left.append(p); continue
            dropped += 1
            for f in p["images"] + [p.get("reel")]:
                if f and f not in fresh:                  # same post name as the new draft: the file is already the new one
                    (Q.DOCS / f).unlink(missing_ok=True)
            (Q.DOCS / "decisions" / f"{p['id']}.json").unlink(missing_ok=True)
            if p.get("photo"):
                led.release(p["photo"]["id"], p["photo"]["name"], p["date"])
            for x in p.get("photos_extra", []):
                led.release(x["id"], x["name"], p["date"])
        Q.save_day(str(d), sorted(keep + left + new, key=lambda p: p["slot"]))
        if new:
            made.append((str(d), len(new)))
        led.save()                                        # saved day by day: a run stopped part-way keeps everything it finished
        config.write_stats({"run": "redo", "days_done": [m[0] for m in made]})
        try: Q.write_index(sorted(set(notes)), now.isoformat())
        except Exception as e: log.warning("index not written: %s", e)
        if left:                                          # ran out of time part-way through this day: the follow-up run redoes the rest of it
            notes.append(f"Run check · {d} and later are finished by a follow-up run that starts by itself")
            CONTINUE[0] = str(d); break
    notes += picker.notes
    from .generate import SWAPS
    notes.append(picker.health() + (f" · {SWAPS[0]} planned posts became another type (no fitting photo)" if SWAPS[0] else ""))
    try:
        from . import music as _M, webvideo as _WV
        notes.append(f"Run check · {_WV.status()}")
    except Exception:
        pass
    try:
        freed = led.reconcile(now.date())
        if freed: log.info("gave back %d photos that were looked at but not used in any post", freed)
    except Exception as e:
        log.warning("photo give-back failed: %s", e)
    led.prune(now.date()); led.save()
    Q.write_index(sorted(set(notes)), now.isoformat())
    return made, kept, dropped, notes
