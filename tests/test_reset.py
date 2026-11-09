"""Reset: approved-but-unpublished posts are wiped, published ones survive, 12/day redrafted from tonight."""
import os, sys, shutil, tempfile, json, datetime as dt
from pathlib import Path
SRC = Path(__file__).resolve().parent.parent
TMP = Path(tempfile.mkdtemp())
shutil.copytree(SRC, TMP/"repo", ignore=shutil.ignore_patterns("cache","__pycache__","media",".git"))
os.environ["AUTOPILOT_ROOT"]=str(TMP/"repo"); os.environ["AUTOPILOT_NOW"]="2026-11-08T20:31:00"
os.environ["MEDIA_BASE_URL"]="https://example.test/docs"; sys.path.insert(0,str(TMP/"repo"))
for f in (TMP/"repo"/"docs"/"queue").glob("*.json"): f.unlink()
from autopilot import config, queue as Q, regen, generate
cfg=config.load(); cfg["sources"]["drive"]["enabled"]=False
generate.run(cfg, render=False)
posts=Q.all_posts(); assert posts
(Q.DOCS/"decisions").mkdir(parents=True,exist_ok=True)
for p in posts[:3]: (Q.DOCS/"decisions"/f"{p['id']}.json").write_text(json.dumps({"decision":"approve"}))
regen.run(cfg, render=False, wipe=True)
new=Q.all_posts()
assert not any(d.get("decision")=="approve" for d in Q.decisions().values()), "approvals survived"
now=config.now(cfg)
assert all(dt.datetime.fromisoformat(p["slot"])>now for p in new), "stale slot"
first=min(p["slot"] for p in new); print("first slot", first, "posts", len(new))
assert first[11:16]=="22:00"
print("OK")
