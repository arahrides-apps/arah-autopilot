"""Artwork for sale promotions: a banner laid over video clips, and the end card with the promo code."""
from pathlib import Path
import html as H
G, Y, C, K = "#0B6B3A", "#E8A93A", "#F1ECE0", "#1A1F1C"

def _base(body, transparent):
    bg = "transparent" if transparent else K
    return f"""<!doctype html><html><head><meta charset=utf-8><style>*{{box-sizing:border-box;margin:0}}
body{{width:1080px;height:1920px;overflow:hidden;background:{bg};font-family:'Poppins','Inter',sans-serif;color:{C};position:relative}}
.abs{{position:absolute}}.tag{{font-weight:800;letter-spacing:6px}}.big{{font-weight:900;line-height:.92}}
.ticket{{position:absolute;left:50%;background:{Y};color:{K};border-radius:26px;display:flex;align-items:center;justify-content:center;flex-direction:column;box-shadow:0 14px 36px rgba(0,0,0,.5)}}
.ticket:before,.ticket:after{{content:"";position:absolute;top:50%;width:56px;height:56px;border-radius:50%;background:{K};transform:translateY(-50%)}}
.ticket:before{{left:-28px}}.ticket:after{{right:-28px}}.dash{{position:absolute;inset:14px;border:4px dashed rgba(26,31,28,.55);border-radius:18px}}
</style></head><body>{body}</body></html>"""

def banner_html(p):
    name, amt, code = H.escape(p["name"]), p["amount"], H.escape(p["code"])
    return _base(f"""
<div class=abs style="left:0;right:0;top:0;height:420px;background:linear-gradient(180deg,rgba(15,20,17,.72),rgba(15,20,17,0))"></div>
<div class=abs style="left:0;right:0;bottom:0;height:760px;background:linear-gradient(0deg,rgba(15,20,17,.92),rgba(15,20,17,.55) 55%,rgba(15,20,17,0))"></div>
<div class="abs" style="left:64px;top:140px;font-weight:800;font-size:34px;display:flex;align-items:center;gap:14px"><div style="width:52px;height:52px;border-radius:50%;background:{Y};color:{K};display:flex;align-items:center;justify-content:center;font-size:30px">A</div>ARAH <span style="font-weight:400">RIDES</span></div>
<div class="abs tag" style="left:0;right:0;top:250px;text-align:center"><span style="background:{Y};color:{K};padding:16px 34px;border-radius:50px;font-size:34px;letter-spacing:4px">{name}</span></div>
<div class="abs" style="left:64px;right:64px;top:1230px;text-align:center"><div class=tag style="font-size:44px;color:{C}">SAVE UP TO</div><div class=big style="font-size:300px;color:{Y};line-height:1">${amt}</div></div>
<div class="abs" style="left:64px;right:64px;top:1630px;text-align:center;font-size:44px;font-weight:700">Code <span style="background:{Y};color:{K};padding:6px 26px;border-radius:14px;font-weight:900;letter-spacing:3px">{code}</span> at checkout</div>
<div class="abs" style="left:64px;right:64px;top:1720px;text-align:center;font-size:30px;font-weight:600;color:{Y}">ArahRides.com</div>""", True)

def end_html(p):
    name, amt, code, terms = H.escape(p["name"]), p["amount"], H.escape(p["code"]), H.escape(p.get("terms", "Conditions apply."))
    return _base(f"""
<div class=abs style="inset:0;background:radial-gradient(circle at 50% 36%,rgba(232,169,58,.22),rgba(11,107,58,.10) 45%,rgba(26,31,28,0) 70%)"></div>
<div class="abs" style="left:64px;top:140px;font-weight:800;font-size:34px;display:flex;align-items:center;gap:14px"><div style="width:52px;height:52px;border-radius:50%;background:{Y};color:{K};display:flex;align-items:center;justify-content:center;font-size:30px">A</div>ARAH <span style="font-weight:400">RIDES</span></div>
<div class="abs big" style="left:0;right:0;top:300px;text-align:center;font-size:130px">{name.replace(' + ', '<br>+ ')}</div>
<div class="abs" style="left:0;right:0;top:700px;text-align:center"><div class=tag style="font-size:50px">SAVE UP TO</div><div class=big style="font-size:300px;color:{Y};line-height:1">${amt}</div></div>
<div class=ticket style="top:1120px;width:820px;height:230px;margin-left:-410px"><div class=dash></div><div class=tag style="font-size:24px;letter-spacing:5px;color:{G}">PROMO CODE AT CHECKOUT</div><div class=big style="font-size:118px;letter-spacing:4px">{code}</div></div>
<div class="abs" style="left:64px;right:64px;top:1390px;text-align:center;font-size:36px;font-weight:600">on your booking at <b style="color:{Y}">ArahRides.com</b></div>
<div class="abs" style="left:64px;right:64px;top:1470px;height:100px;background:{Y};color:{K};border-radius:60px;display:flex;justify-content:space-between;align-items:center;padding:0 44px;font-weight:800;font-size:38px"><span>Book now: arahrides.com</span><span style="font-size:20px;text-align:right;line-height:1.25">WhatsApp Winston<br>wa.me/12013713152</span></div>
<div class="abs" style="left:64px;right:64px;top:1610px;text-align:center;font-size:22px;opacity:.7">{terms}</div>""", False)

def render(p, outdir):
    """Writes banner.png (transparent) and end.png into outdir. Returns (banner, end)."""
    from playwright.sync_api import sync_playwright
    outdir = Path(outdir); outdir.mkdir(parents=True, exist_ok=True)
    b, e = outdir / "banner.png", outdir / "end.png"
    with sync_playwright() as pw:
        br = pw.chromium.launch(); pg = br.new_page(viewport={"width": 1080, "height": 1920})
        pg.set_content(banner_html(p)); pg.wait_for_timeout(250); pg.screenshot(path=str(b), omit_background=True)
        pg.set_content(end_html(p)); pg.wait_for_timeout(250); pg.screenshot(path=str(e))
        br.close()
    return b, e
