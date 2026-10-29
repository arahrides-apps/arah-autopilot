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

led = L.Ledger()
now = config.now(cfg)
pk = Picker(cfg, led, now.date(), random.Random(1), cache=TMP / "cache", web=[FakeWeb()])
made, notes = generate.run(cfg, picker=pk, led=led, days=2)
print("made", made); print("notes", notes)
posts = Q.all_posts()
assert len(posts) == 30, len(posts)
for p in posts:
    assert p["caption"].count("#") <= 5, p["id"]
    assert len(p["caption"]) <= 2200
    for im in p["images"]:
        assert (Q.DOCS / im).exists(), im
        assert Image.open(Q.DOCS / im).size[0] == 1080
photo_ids = [p["photo"]["id"] for p in posts if "photo" in p]
assert len(photo_ids) == len(set(photo_ids)), "photo reused!"
print("photo posts:", len(photo_ids), "unique:", len(set(photo_ids)))
# none of the seeded (already used) photos came back
used = {k for k in json.load(open(SRC / "data" / "ledger.json"))["photos"]}
assert not [i for i in photo_ids if i.startswith("local:") and "name:" + i[6:] in used], "reused a seeded photo"
# regenerate a fresh queue in the future: no photo repeats within 90 days
for f in (Q.DOCS / "queue").glob("*.json"): f.unlink()
os.environ["AUTOPILOT_NOW"] = "2026-10-25T22:00:00"
cfg2 = dict(cfg); pk2 = Picker(cfg, led, dt.date(2026, 10, 25), random.Random(2), cache=TMP / "cache", web=[FakeWeb()])
generate.run(cfg, picker=pk2, led=led, days=1)
ids2 = [p["photo"]["id"] for p in Q.all_posts() if "photo" in p]
assert not (set(ids2) & set(photo_ids)), "photo from first batch reused within 90 days"
print("second batch has no overlap with first: ok")

# ---- publishing with a fake Instagram API
os.environ["AUTOPILOT_NOW"] = "2026-10-26T09:05:00"
os.environ["IG_USER_ID"] = "123"; os.environ["IG_ACCESS_TOKEN"] = "tok"
class Resp:
    def __init__(s, j, code=200): s.j, s.status_code, s.text = j, code, json.dumps(j)
    def json(s): return s.j
class FakeSession:
    def __init__(s): s.calls = []; s.n = 0
    def request(s, method, url, data=None, params=None, timeout=0):
        s.calls.append((method, url, data or params)); s.n += 1
        if url.endswith("/media_publish"): return Resp({"id": "M%d" % s.n})
        if url.endswith("/media"): return Resp({"id": "C%d" % s.n})
        if "fields" in (params or {}) and params["fields"] == "status_code": return Resp({"status_code": "FINISHED"})
        return Resp({"permalink": "https://instagram.com/p/x"})
day = sorted({p["date"] for p in Q.all_posts()})[0]
ps = [p for p in Q.all_posts() if p["date"] == day]
fs = FakeSession(); ig = instagram.IG(cfg, fs)
instagram.publish_due(cfg, ig)
assert not any(c[1].endswith("media_publish") for c in fs.calls), "published without approval!"
(Q.DOCS / "decisions").mkdir(exist_ok=True)
for p in ps[:4]:
    json.dump({"id": p["id"], "decision": "approve", "caption": "EDITED " + p["caption"] if p is ps[1] else None}, open(Q.DOCS / "decisions" / (p["id"] + ".json"), "w"))
json.dump({"id": ps[5]["id"], "decision": "reject"}, open(Q.DOCS / "decisions" / (ps[5]["id"] + ".json"), "w"))
out = instagram.publish_due(cfg, ig); print(out)
pubs = [c for c in fs.calls if c[1].endswith("media_publish")]
assert len(pubs) == 1, "one post per run"
assert fs.calls[0][2]["image_url"].startswith("https://example.test/docs/media/"), fs.calls[0]
# later runs post the rest, respecting spacing and the cap
for minute in range(20, 400, 10):
    os.environ["AUTOPILOT_NOW"] = (dt.datetime(2026, 10, 26, 9, 5) + dt.timedelta(minutes=minute)).isoformat()
    instagram.publish_due(cfg, ig)
pub = Q.published()
done = [k for k, v in pub.items() if v["status"] == "published"]
print("published:", len(done)); assert len(done) == 4, done
assert pub[ps[5]["id"]]["status"] == "rejected"
assert all(v["status"] != "published" for k, v in pub.items() if k not in [p["id"] for p in ps[:4]])
edited = [c for c in fs.calls if c[1].endswith("/media") and str(c[2].get("caption", "")).startswith("EDITED")]
assert edited, "edited caption not used"
cfg["posts_per_day"] = 2; cfg["max_posts_per_day_hard_cap"] = 2
print("ALL OK; preview folder:", Q.DOCS / "media")
shutil.copytree(Q.DOCS, SRC.parent / "autopilot_test_output", dirs_exist_ok=True) if os.environ.get("KEEP") else None

# ---- webhook mode (no Meta developer account)
os.environ["POST_WEBHOOK_URL"] = "https://hook.test/abc"
class HookSession:
    def __init__(s): s.sent = []
    def post(s, url, json=None, timeout=0):
        s.sent.append(json); return type("R", (), {"status_code": 200, "text": "Accepted"})()
hs = HookSession(); wp = instagram.WebhookPoster(cfg, hs)
for p in ps[6:8]:
    json_ = {"id": p["id"], "decision": "approve"}
    json.dump(json_, open(Q.DOCS / "decisions" / (p["id"] + ".json"), "w"))
os.environ["AUTOPILOT_NOW"] = "2026-10-26T14:00:00"
Q.save_published({k: v for k, v in Q.published().items() if v["status"] != "published"})
out = instagram.publish_due(cfg, wp); print(out)
assert hs.sent and hs.sent[0]["image_url_1"].startswith("https://example.test/docs/media/") and hs.sent[0]["caption"]
print("WEBHOOK OK")
