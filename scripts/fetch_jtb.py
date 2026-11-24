"""Downloads the Jamaica Tourist Board 'Unrestricted use images' library into photos/jtb/ (the Board asks for a credit,
which every post using one of these photos carries: 'Photo: Jamaica Tourist Board').

Fast and safe to run again:
  - skips every image you already have (photos/jtb, the JTB photos already in Drive / content/photo_meta*.yaml, data/jtb_done.json)
  - downloads 6 at a time over plain HTTP; the slow browser click is only a fallback
  - stops starting new downloads after JTB_MINUTES (default 60) and saves what it has, so it never hits the run limit;
    the next run carries on where this one stopped
  - photos are resized to 2048 px (sharp for Instagram, small for the repo) and labelled in content/photo_meta_jtb.yaml
"""
import os, re, sys, time, json, pathlib, urllib.parse, io
from concurrent.futures import ThreadPoolExecutor, as_completed

ROOT = pathlib.Path(__file__).resolve().parent.parent
BASE = "https://www.jtbonline.org"
LIST = BASE + "/download-category/unrestricted-use-images/"
OUT = ROOT / "photos" / "jtb"
META = ROOT / "content" / "photo_meta_jtb.yaml"
DONE = ROOT / "data" / "jtb_done.json"
REPORT = ROOT / "jtb_report.txt"
START = time.time()
BUDGET = float(os.environ.get("JTB_MINUTES", "60")) * 60
PEOPLE = r"yoga|cyclist|jogging|couple|female|male|vendor|group|spa|shopping|craft|exercise|people|man\b|woman|guest|dancer|family|child|kids|chef|musician|drummer|friends|romance|bride|wedding"
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"
log = []

def say(m):
    print(m, flush=True); log.append(m)

def time_left():
    return BUDGET - (time.time() - START)

def slug_of(url):
    return urllib.parse.urlparse(url).path.rstrip("/").split("/")[-1]

def norm(s):
    """'004_JTB_Spring_2025_Kingston_Palisadoes_Coconut' and 'jtb-spring-2025-kingston-palisadoes-coconut' -> the same key."""
    s = re.sub(r"^\d+[_\-\s]+", "", s.lower())
    s = re.sub(r"\b(jtb|spring|summer|winter|fall|20\d\d|img|dsc|final|copy)\b", " ", re.sub(r"[_\-.]+", " ", s))
    return re.sub(r"[^a-z]", "", s)

def known():
    import yaml
    have = set()
    for f in (ROOT / "content").glob("photo_meta*.yaml"):
        try:
            for k in (yaml.safe_load(f.read_text()) or {}):
                if "jtb" in k.lower() or f.name == "photo_meta_jtb.yaml":
                    have.add(norm(k))
        except Exception:
            pass
    for p in OUT.glob("*.jpg"):
        have.add(norm(p.stem))
    return have

def load_done():
    try: return json.loads(DONE.read_text())
    except Exception: return {}

def save_image(raw, slug):
    from PIL import Image
    im = Image.open(io.BytesIO(raw)).convert("RGB")
    im.thumbnail((2048, 2048))
    w, h = im.size
    if min(w, h) < 700:
        raise ValueError(f"too small ({w}x{h})")
    OUT.mkdir(parents=True, exist_ok=True)
    im.save(OUT / f"{slug}.jpg", quality=86, optimize=True)
    return w, h

def list_details(page):
    details, n, last = [], 1, 14
    while n <= last and time_left() > 60:
        url = LIST if n == 1 else f"{LIST}page/{n}/"
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=45000); page.wait_for_timeout(800)
        except Exception as e:
            say(f"page {n}: could not open ({str(e)[:80]})"); n += 1; continue
        if n == 1:
            nums = [int(x) for x in re.findall(r"/page/(\d+)/", page.content())]
            if nums: last = max(nums + [last])
        hrefs = page.eval_on_selector_all("a[href]", "els => els.map(e => e.href)")
        found = [h for h in dict.fromkeys(hrefs) if urllib.parse.urlparse(h).netloc.endswith("jtbonline.org")
                 and re.match(r"^/download/[^/]+/?$", urllib.parse.urlparse(h).path)]
        say(f"page {n}/{last}: {len(found)} images")
        details += [f for f in found if f not in details]; n += 1
    return details

def http_get(sess, d):
    """Fast path: read the image page, find its download link, fetch the file. -> image bytes or None."""
    r = sess.get(d, timeout=30); r.raise_for_status()
    html = r.text
    cands = re.findall(r"""href=["']([^"']*(?:wpdmdl=\d+[^"']*|\.(?:jpe?g|png)(?:\?[^"']*)?))["']""", html, re.I)
    cands = [urllib.parse.urljoin(d, c.replace("&amp;", "&")) for c in cands if not re.search(r"logo|favicon|icon|thumb|150x150|300x", c, re.I)]
    cands.sort(key=lambda c: 0 if "wpdmdl" in c else 1)
    for c in cands[:4]:
        f = sess.get(c, timeout=60)
        ct = f.headers.get("content-type", "")
        if f.ok and ("image" in ct or "octet" in ct) and len(f.content) > 50_000:
            return f.content
        if f.ok and "zip" in ct:
            import zipfile
            with zipfile.ZipFile(io.BytesIO(f.content)) as z:
                for nm in z.namelist():
                    if re.search(r"\.(jpe?g|png)$", nm, re.I):
                        return z.read(nm)
    return None

def browser_get(page, d):
    """Slow fallback: click the Download button like a person would."""
    page.goto(d, wait_until="domcontentloaded", timeout=45000); page.wait_for_timeout(800)
    btn = page.locator("a:has-text('Download'), button:has-text('Download'), input[value*='Download']").first
    with page.expect_download(timeout=20000) as dl:
        btn.click()
    return pathlib.Path(dl.value.path()).read_bytes()

def meta_entry(slug, w, h):
    title = re.sub(r"[-_]\d+$", "", slug).replace("-", " ").replace("_", " ").strip()
    title = re.sub(r"\bjtb\b", "", title, flags=re.I).strip()
    people = bool(re.search(PEOPLE, title, re.I))
    orient = "landscape" if w > h * 1.1 else "portrait" if h > w * 1.1 else "square"
    return (f"{slug}:\n  about: 'Jamaica Tourist Board photo: {title.replace(chr(39), '')} (Jamaica)'\n  kind: scenery\n  orientation: {orient}\n"
            f"  people: {'true' if people else 'false'}\n  plate_visible: false\n  quality: 4\n  series: {slug}\n"
            f"  credit: 'Photo: Jamaica Tourist Board'\n")

def main():
    import requests
    from playwright.sync_api import sync_playwright
    have, done = known(), load_done()
    new_meta, got, failed, skipped = [], [], [], 0
    with sync_playwright() as pw:
        br = pw.chromium.launch()
        ctx = br.new_context(accept_downloads=True, user_agent=UA)
        page = ctx.new_page()
        details = list_details(page)
        say(f"total image pages: {len(details)}")
        todo = []
        for d in details:
            s = slug_of(d)
            if norm(s) in have or done.get(s) in ("ok", "known", "small"):
                skipped += 1; continue
            todo.append(d)
        say(f"already have {skipped}; to download {len(todo)}")
        sess = requests.Session(); sess.headers["User-Agent"] = UA
        for c in ctx.cookies():
            sess.cookies.set(c["name"], c["value"], domain=c["domain"])
        slow = []
        with ThreadPoolExecutor(6) as ex:
            futs = {ex.submit(http_get, sess, d): d for d in todo}
            for f in as_completed(futs):
                d = futs[f]; s = slug_of(d)
                try:
                    raw = f.result()
                except Exception:
                    raw = None
                if raw is None:
                    slow.append(d); continue
                try:
                    w, h = save_image(raw, s); new_meta.append(meta_entry(s, w, h)); got.append(s); done[s] = "ok"
                except Exception as e:
                    done[s] = "small" if "too small" in str(e) else "bad"; failed.append(s)
                if time_left() < 120:
                    say("time budget reached: stopping new downloads"); ex.shutdown(cancel_futures=True); break
        say(f"fast downloads: {len(got)}; need the browser for {len(slow)}")
        for i, d in enumerate(slow):
            if time_left() < 180:
                say(f"time budget reached: {len(slow) - i} left for the next run"); break
            s = slug_of(d)
            try:
                raw = browser_get(page, d)
                w, h = save_image(raw, s); new_meta.append(meta_entry(s, w, h)); got.append(s); done[s] = "ok"
            except Exception as e:
                failed.append(s); say(f"  {s}: {str(e)[:80]}")
        br.close()
    if new_meta:
        META.parent.mkdir(parents=True, exist_ok=True)
        old = META.read_text() if META.exists() else ""
        META.write_text(old + ("" if old.endswith("\n") or not old else "\n") + "".join(new_meta))
    DONE.parent.mkdir(parents=True, exist_ok=True); DONE.write_text(json.dumps(done, indent=0, sort_keys=True))
    say(f"new photos saved: {len(got)} · already had: {skipped} · failed: {len(failed)} {failed[:15]} · took {int((time.time() - START) / 60)} min")
    REPORT.write_text("\n".join(log))

if __name__ == "__main__":
    main()
