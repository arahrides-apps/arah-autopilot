"""Upcoming events are highlighted in the daily schedule."""
import os, sys, shutil, tempfile, datetime as dt
from pathlib import Path
SRC = Path(__file__).resolve().parent.parent
TMP = Path(tempfile.mkdtemp()); shutil.copytree(SRC, TMP/"repo", ignore=shutil.ignore_patterns("cache","__pycache__","media",".git"))
os.environ["AUTOPILOT_ROOT"]=str(TMP/"repo"); os.environ["AUTOPILOT_NOW"]="2026-11-09T06:00:00"; os.environ["MEDIA_BASE_URL"]="https://example.test/docs"
sys.path.insert(0,str(TMP/"repo"))
for f in (TMP/"repo"/"docs"/"queue").glob("*.json"): f.unlink()
from autopilot import config, generate, queue as Q
from autopilot.ledger import Ledger
from autopilot.photos import Picker
import random
cfg=config.load(); cfg["sources"]["drive"]["enabled"]=False
led=Ledger(); now=config.now(cfg); pk=Picker(cfg, led, now.date(), random.Random(1))
seen=set(); n=0
for off in range(0, 40):
    d=now.date()+dt.timedelta(days=off); pk.today=d
    posts=generate.generate_day(cfg, led, pk, d, now, render=False, notes=[])
    ev=[p for p in posts if p.get("event_id")]
    due=generate.upcoming_events(generate.load_yaml("moments.yaml"), d)
    if due: assert ev, f"no event post on {d}"
    assert len(ev) <= 2
    for p in ev:
        assert len(p["images"]) > 1 and p["slot"][11:16] in ("16:00","22:00"); seen.add(p["event_id"]); n+=1
print("events highlighted:", sorted(seen), n); assert len(seen) >= 4
print("EVENTS OK")
