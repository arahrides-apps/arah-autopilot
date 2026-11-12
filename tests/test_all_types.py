"""Every post type, every moment, 45 days, no rendering. Offline end-to-end test: fake web photos + a folder of real photos + a fake Instagram API.
Run:  python tests/test_end_to_end.py [path-to-photo-folder]
Nothing here touches the internet, Google Drive or Instagram."""
import os, sys, shutil, tempfile, json, random, datetime as dt
from pathlib import Path
SRC = Path(__file__).resolve().parent.parent
TMP = Path(tempfile.mkdtemp())
shutil.copytree(SRC, TMP / "repo", ignore=shutil.ignore_patterns("cache", "__pycache__", "media", ".git", "reels"))
os.environ["AUTOPILOT_ROOT"] = str(TMP / "repo")
os.environ["AUTOPILOT_NOW"] = "2026-11-03T05:00:00"
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

import collections
cfg["days_ahead"] = 45
made, notes = generate.run(cfg, picker=pk, led=led, days=45, render=False)
types = collections.Counter(); bad = []
for d, n in made:
    for p in Q.load_day(d)["posts"]:
        types[p["type"]] += 1
        if not 4 <= len(p["images"]) <= 6:
            bad.append((p["id"], len(p["images"])))
print("days", len(made), "posts", sum(types.values())); print(dict(types))
assert not bad, bad
assert {"moment", "offer"} <= set(types), types
from autopilot import templates as T
T.configure(cfg)
T.versus("K", "H", ["a", "b"], ["c", "d"]); T.event("K", "H", "B", "BADGE"); T.sticker("a", "b")
print("ALL TYPES OK")
