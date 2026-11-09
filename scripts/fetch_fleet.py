"""Reads our own marketplace (arahrides.com public listing search, the same one Winston uses) and saves:
  content/fleet.yaml          every listing: make, model, year, type, daily price, page link
  photos/listings/*.jpg       the first photos of each listing, sized up to 1080 px, no faces
  content/photo_meta.yaml     a label for each photo so the autopilot can match it to posts
  data/fleet_report.txt       what worked and what did not (paste this to Claude if anything is missing)
Runs on GitHub (workflow 'Fetch fleet'); needs no password: SearchListing is a public query."""
import io, os, re, sys, time, json, pathlib, yaml, requests
from PIL import Image
ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
SITE = os.environ.get("ARAH_SITE", "https://www.arahrides.com")
API = SITE + "/api/graphql"
H = {"Content-Type": "application/json", "User-Agent": "ArahAutopilot/1.0 (our own marketplace)"}
MAX_PHOTOS_PER_LISTING = 2
MAX_TOTAL = int(os.environ.get("MAX_PHOTOS", "160"))
SESSION = requests.Session()
LOG = []
def say(m):
    print(m, flush=True); LOG.append(str(m))

def gql(q, v=None):
    r = SESSION.post(API, json={"query": q, "variables": v or {}}, headers=H, timeout=30)
    try:
        return r.json()
    except Exception:
        return {"errors": [{"message": "HTTP %s, not JSON: %s" % (r.status_code, r.text[:120])}]}

BASE = "id title make model year carType userId listingData { basePrice currency }"
PHOTO_TRIES = ["coverPhoto listPhotos { id name }", "listPhotos { id name }", "listPhotos { name }", "coverPhoto", "listingPhotos { name }", "photos { name }"]
Q = "query ($p: Int) { SearchListing(currentPage: $p) { count status errorMessage results { %s } } }"

def page(p, extra):
    d = gql(Q % (BASE + " " + extra).strip(), {"p": p})
    s = (d.get("data") or {}).get("SearchListing") or {}
    return s.get("results") or [], d.get("errors")

def pick_photo_selection():
    for extra in PHOTO_TRIES:
        res, err = page(1, extra)
        if res and not err:
            say("photo fields that work: " + extra); return extra, res
        say("photo fields '%s' failed: %s" % (extra, (err or [{}])[0].get("message", "no results"))[:160])
    res, err = page(1, "")
    say("no photo field found; listings only")
    return "", res

def names_of(l):
    out = []
    cp = l.get("coverPhoto")
    lp = l.get("listPhotos") or l.get("listingPhotos") or l.get("photos") or []
    for x in lp:
        n = x.get("name") if isinstance(x, dict) else x
        if n:
            out.append((x.get("id") if isinstance(x, dict) else None, n))
    if cp is not None and out:                       # put the cover photo first
        out.sort(key=lambda t: 0 if str(t[0]) == str(cp) else 1)
    elif isinstance(cp, str) and cp:
        out.insert(0, (None, cp))
    return [n for _, n in out]

PREFIXES = ["x_large_", "large_", "", "x_medium_", "medium_"]
def photo_bytes(name):
    if name.startswith("http"):
        urls = [name]
    else:
        urls = [SITE + "/images/upload/" + p + name for p in PREFIXES]
    for u in urls:
        try:
            r = SESSION.get(u, headers=H, timeout=40)
            if r.status_code == 200 and r.headers.get("content-type", "").startswith("image/") and len(r.content) > 8000:
                return r.content, u
        except requests.RequestException:
            pass
    return None, None

def slug(s):
    return re.sub(r"[^a-z0-9]+", "-", (s or "").lower()).strip("-")

def main():
    extra, first = pick_photo_selection()
    listings, seen = [], set()
    for p in range(1, 60):
        res = first if p == 1 else page(p, extra)[0]
        new = [l for l in res if l["id"] not in seen]
        if not new:
            break
        for l in new:
            seen.add(l["id"]); listings.append(l)
        time.sleep(0.3)
    say("listings found: %d" % len(listings))
    fleet = []
    for l in listings:
        ld = l.get("listingData") or {}
        fleet.append({"id": l["id"], "title": l.get("title"), "make": l.get("make"), "model": l.get("model"), "year": l.get("year"),
                      "type": l.get("carType"), "host": l.get("userId"), "price_per_day": ld.get("basePrice"), "currency": ld.get("currency"),
                      "url": "%s/cars/%s" % (SITE, l["id"])})
    (ROOT / "content").mkdir(exist_ok=True)
    yaml.safe_dump({"fleet": fleet}, open(ROOT / "content" / "fleet.yaml", "w"), sort_keys=False, allow_unicode=True, width=200)
    prices = [float(f["price_per_day"]) for f in fleet if f["price_per_day"] not in (None, "")]
    if prices:
        say("daily prices: lowest %s, highest %s, %d listings priced (currency %s)" % (min(prices), max(prices), len(prices), fleet[0]["currency"]))
    out = ROOT / "photos" / "listings"; out.mkdir(parents=True, exist_ok=True)
    meta_p = ROOT / "content" / "photo_meta.yaml"
    meta = yaml.safe_load(open(meta_p)) or {}
    try:
        from autopilot.photos import has_face
    except Exception:
        has_face = lambda p: None
    got = skipped = 0
    for l in listings:
        for k, name in enumerate(names_of(l)[:MAX_PHOTOS_PER_LISTING]):
            if got >= MAX_TOTAL:
                break
            title = "%s %s %s" % (l.get("year") or "", l.get("make") or "", l.get("model") or "")
            stem = "arah_listing_%s_%d_%s" % (l["id"], k + 1, slug(title))
            dest = out / (stem + ".jpg")
            if dest.exists():
                continue
            data, u = photo_bytes(name)
            if not data:
                skipped += 1; continue
            try:
                im = Image.open(io.BytesIO(data)).convert("RGB")
            except Exception:
                skipped += 1; continue
            if min(im.size) < 600:
                skipped += 1; continue
            s = max(1.0, 1080 / min(im.size))
            if s > 1:
                im = im.resize((round(im.width * s), round(im.height * s)), Image.LANCZOS)
            im.save(dest, "JPEG", quality=88)
            if has_face(str(dest)):
                dest.unlink(); skipped += 1; continue
            ct = (l.get("carType") or "").lower()
            kind = "boat" if re.search(r"boat|yacht", ct) else "car"
            m = {"about": ("%s %s listing photo" % (title.strip(), "from arahrides.com")), "kind": kind, "people": False, "plate_visible": True,
                 "orientation": "portrait" if im.height > im.width else "landscape", "quality": 3 if s > 1.3 else 4,
                 "series": "%s-%s" % (slug(l.get("make")), slug(l.get("model"))) or "listing"}
            if re.search(r"bus|7 seater|van", ct):
                m["tag"] = "big"
            meta[stem] = m; got += 1
        time.sleep(0.2)
    yaml.safe_dump(meta, open(meta_p, "w"), sort_keys=True, allow_unicode=True, width=200)
    say("photos saved: %d, skipped (too small, a face, or not found): %d" % (got, skipped))
    if listings and not got:
        say("NO PHOTOS SAVED: send this report to Claude so the photo web address can be corrected")
    (ROOT / "data").mkdir(exist_ok=True)
    (ROOT / "data" / "fleet_report.txt").write_text("\n".join(LOG) + "\n")

if __name__ == "__main__":
    main()
