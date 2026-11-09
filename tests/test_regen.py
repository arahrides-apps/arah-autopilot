"""Offline end-to-end test: fake web photos + a folder of real photos + a fake Instagram API.
Run:  python tests/test_end_to_end.py [path-to-photo-folder]
Nothing here touches the internet, Google Drive or Instagram."""
import os, sys, shutil, tempfile, json, random, datetime as dt
from pathlib import Path
SRC = Path(__file__).resolve().parent.parent
TMP = Path(tempfile.mkdtemp())
shutil.copytree(SRC, TMP / "repo", ignore=shutil.ignore_patterns("cache", "__pycache__", "media", ".git"))
os.environ["AUTOPILOT_ROOT"] = str(TMP / "repo")
os.environ["AUTOPILOT_NOW"] = "2026-10-20T22:00:00"
os.environ["MEDIA_BASE_URL"] = "https://example.test/docs"
sys.path.insert(0, str(TMP / "repo"))
for f in (TMP / "repo" / "docs" / "queue").glob("*.json"): f.unlink()
from PIL import Image, ImageDraw
from autopilot import config, queue as Q, generate, instagram, ledger as L
from autopilot.photos import Picker

cfg = config.load()
# these tests exercise every post type, so they use the busy 15-a-day layout; the live default is 1 a day (see tests/test_daily.py)
cfg["posts_per_day"] = 15; cfg["single_slots"] = []
cfg["slots"] = ["06:30", "07:30", "08:30", "09:30", "10:30", "11:30", "12:30", "13:30", "14:30", "15:30", "16:30", "17:30", "18:30", "19:30", "20:30"]
cfg["pattern"] = ["car_hero", "qa", "experience", "tip", "brand|chat", "carousel|list", "trip", "experience", "tip", "place", "qa|trust|review", "trip", "brand|versus", "place", "list|carousel"]
photos = sys.argv[1] if len(sys.argv) > 1 else "/mnt/user-data/outputs/photos/drive"
cfg["sources"]["local"]["dir"] = photos
cfg["sources"]["drive"]["enabled"] = False

class FakeWeb:
    name = "pexels"
    def search(self, query, rng):
        return [{"id": f"pexels:{abs(hash((query, i))) % 10**6}", "name": f"pexels-{i}-{len(query)}", "w": 1600, "h": 2000,
                 "text": ("%s sunset" % query) if i % 2 == 0 else "tropical beach", "credit": "Photo by Test on Pexels"} for i in range(12)]
    def fetch(self, item, dest):
        r = random.Random(item["id"]); im = Image.new("RGB", (1600, 2000), (r.randrange(60, 200), r.randrange(80, 200), r.randrange(60, 200)))
        d = ImageDraw.Draw(im)
        for _ in range(14):
            x, y = r.randrange(1600), r.randrange(2000); s = r.randrange(150, 700)
            d.ellipse([x, y, x + s, y + s], fill=(r.randrange(256), r.randrange(256), r.randrange(256)))
        Path(dest).parent.mkdir(parents=True, exist_ok=True); im.save(dest, "JPEG")

led = L.Ledger(); led.data["photos"] = {}; led.data["hashes"] = []   # fresh library so own photos are in play
now = config.now(cfg)
pk = Picker(cfg, led, now.date(), random.Random(1), cache=TMP / "cache", web=[FakeWeb()])
made, notes = generate.run(cfg, picker=pk, led=led, days=6)
print("made", made); print("notes", notes)
posts = Q.all_posts()
assert len(posts) >= 60
for p in posts:
    assert p["caption"].count("#") <= 5, p["id"]
    assert len(p["caption"]) <= 2200
    for im in p["images"]:
        assert (Q.DOCS / im).exists(), im
        assert Image.open(Q.DOCS / im).size[0] == 1080
photo_ids = [p["photo"]["id"] for p in posts if "photo" in p]
assert len(photo_ids) == len(set(photo_ids)), "photo reused!"
print("photo posts:", len(photo_ids), "unique:", len(set(photo_ids)))
# regenerate a fresh queue in the future: no photo repeats within 90 days
for f in (Q.DOCS / "queue").glob("*.json"): f.unlink()
os.environ["AUTOPILOT_NOW"] = "2026-10-25T22:00:00"
cfg2 = dict(cfg); pk2 = Picker(cfg, led, dt.date(2026, 10, 25), random.Random(2), cache=TMP / "cache", web=[FakeWeb()])
generate.run(cfg, picker=pk2, led=led, days=1)
ids2 = [p["photo"]["id"] for p in Q.all_posts() if "photo" in p]
assert not (set(ids2) & set(photo_ids)), "photo from first batch reused within 90 days"
print("second batch has no overlap with first: ok")


# ---- series spacing: cars from the same shoot are not used back to back
from autopilot import regen
meta = {k: v for k, v in __import__("yaml").safe_load(open(SRC / "content" / "photo_meta.yaml")).items()}
def series_of(p):
    n = p["photo"]["name"]; m = meta.get(n) or meta.get(n.split(".")[0]) or {}
    return m.get("series") or n
cars = [(p["date"], series_of(p)) for p in Q.all_posts() if p.get("photo") and p["photo"]["source"] == "local"]
print("own-photo series by day:", cars)
assert cars, "no own photos used"
seen = {}
for d, s_ in cars:
    if s_ in seen:
        assert (dt.date.fromisoformat(d) - dt.date.fromisoformat(seen[s_])).days >= cfg["photos"]["series_days"] or "running thin" in " ".join(notes), (s_, d, seen[s_])
    seen[s_] = d
# ---- regenerate: approved posts stay, the rest are redone
allp = Q.all_posts(); keep = [p["id"] for p in allp[:5] + allp[20:23]]
(Q.DOCS / "decisions").mkdir(exist_ok=True)
for i in keep:
    json.dump({"id": i, "decision": "approve"}, open(Q.DOCS / "decisions" / f"{i}.json", "w"))
rej = allp[10]["id"]; json.dump({"id": rej, "decision": "reject"}, open(Q.DOCS / "decisions" / f"{rej}.json", "w"))
before = {p["id"]: p for p in allp}
pk3 = Picker(cfg, led, now.date(), random.Random(9), cache=TMP / "cache", web=[FakeWeb()])
made, kept, dropped, n2 = regen.run(cfg, picker=pk3, led=led)
after = {p["id"]: p for p in Q.all_posts()}
print("regen kept", kept, "dropped", dropped)
assert kept == len(keep) and dropped == len(allp) - len(keep), (kept, dropped)
for i in keep: assert after[i]["caption"] == before[i]["caption"], "approved post changed"
assert set(before) - set(after) <= set(before) - set(keep), "approved post lost"
assert not (Q.DOCS / "decisions" / f"{rej}.json").exists(), "old decision survived"
changed = sum(1 for i, p in after.items() if i in before and i not in keep and p["caption"] != before[i]["caption"])
print("redone posts with new wording/photos:", changed)
ids3 = [p["photo"]["id"] for p in after.values() if "photo" in p]
assert len(ids3) == len(set(ids3)), "photo repeated after regenerate"
print("REGEN OK")
