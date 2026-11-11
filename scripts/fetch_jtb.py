"""Downloads every image from the Jamaica Tourist Board 'Unrestricted use images' library (all pages).
Runs on GitHub (the workflow 'Fetch JTB images'). Output: jtb_out/*.jpg, jtb_out/photo_meta_additions.yaml, jtb_out/REPORT.txt
The Board requires a credit wherever its images are used; the notes file sets that credit so every post carries it."""
import re, sys, time, json, pathlib, urllib.parse
from playwright.sync_api import sync_playwright

BASE = "https://www.jtbonline.org"
LIST = BASE + "/download-category/unrestricted-use-images/"
OUT = pathlib.Path("jtb_out"); OUT.mkdir(exist_ok=True)
PEOPLE = r"yoga|cyclist|jogging|couple|female|male|vendor|group|spa|shopping|craft|exercise|people|man |woman|guest|dancer|family|child|kids|chef|musician|drummer"
log = []

def say(m):
    print(m, flush=True); log.append(m)

def slug_of(url):
    return urllib.parse.urlparse(url).path.rstrip("/").split("/")[-1]

def detail_links(page):
    hrefs = page.eval_on_selector_all("a[href]", "els => els.map(e => e.href)")
    out = []
    for h in hrefs:
        p = urllib.parse.urlparse(h)
        if p.netloc.endswith("jtbonline.org") and re.match(r"^/download/[^/]+/?$", p.path) and h not in out:
            out.append(h)
    return out

def main():
    with sync_playwright() as pw:
        br = pw.chromium.launch()
        ctx = br.new_context(accept_downloads=True, user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124 Safari/537.36")
        page = ctx.new_page()
        details = []
        n = 1
        last = 14
        while n <= last:
            url = LIST if n == 1 else f"{LIST}page/{n}/"
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=60000)
                page.wait_for_timeout(1500)
            except Exception as e:
                say(f"page {n}: could not open ({str(e)[:80]})"); n += 1; continue
            if n == 1:
                nums = [int(x) for x in re.findall(r"/page/(\d+)/", page.content())]
                if nums: last = max(nums + [last])
            found = detail_links(page)
            say(f"page {n}/{last}: {len(found)} images")
            for f in found:
                if f not in details: details.append(f)
            n += 1
        say(f"total image pages: {len(details)}")
        got, failed = [], []
        for i, d in enumerate(details, 1):
            slug = slug_of(d)
            if any(OUT.glob(slug + ".*")):
                got.append(slug); continue
            ok = False
            for attempt in range(2):
                try:
                    page.goto(d, wait_until="domcontentloaded", timeout=60000)
                    page.wait_for_timeout(1200)
                    btn = page.locator("a:has-text('Download'), button:has-text('Download'), input[value*='Download']").first
                    # 1) real browser download
                    try:
                        with page.expect_download(timeout=25000) as dl:
                            btn.click()
                        dest = OUT / (slug + pathlib.Path(dl.value.suggested_filename).suffix.lower().replace(".jpeg", ".jpg"))
                        dl.value.save_as(dest); ok = True
                    except Exception:
                        # 2) look for a file link / image response the click revealed
                        links = page.eval_on_selector_all("a[href]", "els => els.map(e => e.href)")
                        file_links = [l for l in links if re.search(r"\.(jpe?g|png|zip)(\?|$)", l, re.I) and "favicon" not in l and "logo" not in l.lower()]
                        if not file_links:
                            file_links = [l for l in links if re.search(r"wpdmdl|download_id|\?download=", l)]
                        for l in file_links:
                            r = ctx.request.get(l, timeout=60000)
                            ct = r.headers.get("content-type", "")
                            if r.ok and ("image" in ct or "zip" in ct or "octet" in ct):
                                ext = ".png" if "png" in ct else ".zip" if "zip" in ct else ".jpg"
                                (OUT / (slug + ext)).write_bytes(r.body()); ok = True; break
                    if ok: break
                except Exception as e:
                    say(f"  {slug}: attempt {attempt + 1} failed ({str(e)[:80]})")
                    time.sleep(2)
            (got if ok else failed).append(slug)
            if i % 20 == 0: say(f"  ...{i}/{len(details)}")
        br.close()
    # unzip any zips, tidy to jpg
    import zipfile
    for z in list(OUT.glob("*.zip")):
        try:
            with zipfile.ZipFile(z) as zf:
                for nm in zf.namelist():
                    if re.search(r"\.(jpe?g|png)$", nm, re.I):
                        (OUT / (z.stem + "_" + pathlib.Path(nm).name)).write_bytes(zf.read(nm))
            z.unlink()
        except Exception as e:
            say(f"zip {z.name}: {e}")
    from PIL import Image
    meta = []
    for f in sorted(OUT.glob("*")):
        if f.suffix.lower() not in (".jpg", ".jpeg", ".png"): continue
        try:
            im = Image.open(f).convert("RGB"); w, h = im.size
            if f.suffix.lower() != ".jpg":
                new = f.with_suffix(".jpg"); im.save(new, quality=92); f.unlink(); f = new
        except Exception as e:
            say(f"{f.name}: unreadable ({e})"); continue
        stem = f.stem
        title = re.sub(r"[-_]\d+$", "", stem).replace("-", " ").replace("_", " ")
        people = bool(re.search(PEOPLE, title, re.I))
        series = "jtb-" + re.sub(r"\s+", "-", re.sub(r"\d+$", "", title).strip()) 
        orient = "landscape" if w > h * 1.1 else "portrait" if h > w * 1.1 else "square"
        meta.append(f"{stem}:\n  about: 'Jamaica Tourist Board photo: {title}'\n  kind: scenery\n  orientation: {orient}\n"
                    f"  people: {'true' if people else 'false'}\n  plate_visible: false\n  quality: 4\n  series: {series}\n"
                    f"  credit: 'Photo: Jamaica Tourist Board'\n")
    (OUT / "photo_meta_additions.yaml").write_text("".join(meta))
    say(f"downloaded {len(got)} of {len(details)}; failed: {len(failed)} {failed[:20]}")
    (OUT / "REPORT.txt").write_text("\n".join(log))

if __name__ == "__main__":
    main()
