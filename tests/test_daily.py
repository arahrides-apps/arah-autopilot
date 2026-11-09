"""The live default (12 posts a day, one every 2 hours from midnight Jamaica time, 10 carousels and 2 single pictures) over 45 days, no rendering. Offline end-to-end test: fake web photos + a folder of real photos + a fake Instagram API.
Run:  python tests/test_end_to_end.py [path-to-photo-folder]
Nothing here touches the internet, Google Drive or Instagram."""
import os, sys, shutil, tempfile, json, random, datetime as dt
from pathlib import Path
SRC = Path(__file__).resolve().parent.parent
TMP = Path(tempfile.mkdtemp())
shutil.copytree(SRC, TMP / "repo", ignore=shutil.ignore_patterns("cache", "__pycache__", "media", ".git"))
os.environ["AUTOPILOT_ROOT"] = str(TMP / "repo")
os.environ["AUTOPILOT_NOW"] = "2026-11-03T05:00:00"
os.environ["MEDIA_BASE_URL"] = "https://example.test/docs"
sys.path.insert(0, str(TMP / "repo"))
for f in (TMP / "repo" / "docs" / "queue").glob("*.json"): f.unlink()
from PIL import Image, ImageDraw
from autopilot import config, queue as Q, generate, instagram, ledger as L
from autopilot.photos import Picker

cfg = config.load()
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
types = collections.Counter(); bad = []; six = 0; multi = total = 0
for d, n in made:
    posts = Q.load_day(d)["posts"]
    assert len(posts) <= 12, (d, len(posts))
    for p in posts:
        types[p["type"]] += 1
        assert int(p["slot"][11:13]) % 2 == 0 and p["slot"][14:16] == "00", p["slot"]
        multi += len(p["images"]) > 1; total += 1
        if p.get("single"):
            assert len(p["images"]) == 1
        elif not 4 <= len(p["images"]) <= 6:
            bad.append((p["id"], len(p["images"])))
        if p["type"] in ("place", "experience", "trip"):
            six += len(p["images"]) == 6
        assert p["caption"].count("#") <= 5, p["caption"]
print("days", len(made), "posts", sum(types.values())); print(dict(types), "six-slide story posts:", six)
print("carousel share: %.0f%%" % (100 * multi / total))
assert 0.75 <= multi / total <= 0.9, multi / total
assert not bad, bad
assert {"place", "trip", "experience", "car_hero", "review"} <= set(types), types
assert six >= 100, six
print("DAILY OK")
