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

def _mark():
    from . import templates as T
    hl = T.holiday_src()
    if hl:
        return f'<img class="abs" src="{hl}" style="left:52px;top:110px;width:150px;filter:drop-shadow(0 6px 14px rgba(0,0,0,.35))">'
    return (f'<div class="abs" style="left:64px;top:140px;font-weight:800;font-size:34px;display:flex;align-items:center;gap:14px"><div style="width:52px;height:52px;border-radius:50%;background:{Y};color:{K};'
            f'display:flex;align-items:center;justify-content:center;font-size:30px">A</div>ARAH <span style="font-weight:400">RIDES</span></div>')

def _lights():
    """A string of Christmas lights across the top (holiday window only)."""
    from . import templates as T
    if not T.holiday_logo():
        return ""
    cols = ["#E63946", "#2BB673", "#E8A93A", "#F1ECE0"]
    bulbs = "".join(f'<i style="position:absolute;left:{18 + i * 54}px;top:{26 + (14 if i % 2 else 0)}px;width:22px;height:30px;border-radius:50% 50% 45% 45%;background:{cols[i % 4]};'
                    f'box-shadow:0 0 22px 6px {cols[i % 4]}99"></i>' for i in range(20))
    wire = '<svg class=abs style="left:0;top:0" width="1080" height="80"><path d="M0 28 Q 27 48 54 28 T 108 28 T 162 28 T 216 28 T 270 28 T 324 28 T 378 28 T 432 28 T 486 28 T 540 28 T 594 28 T 648 28 T 702 28 T 756 28 T 810 28 T 864 28 T 918 28 T 972 28 T 1026 28 T 1080 28" stroke="#0d3b24" stroke-width="4" fill="none"/></svg>'
    return f'<div class=abs style="left:0;right:0;top:0;height:90px">{wire}{bulbs}</div>'

def _pay():
    return ('<div class="abs" style="left:64px;right:64px;top:1600px;text-align:center;font-size:27px;font-weight:700;line-height:1.35">'
            f'Pay your way at checkout<br><span style="color:{Y}">Klarna · Affirm · Link · Google Pay · Apple Pay</span></div>')

def banner_html(p):
    name, amt, code = H.escape(p["name"]), p["amount"], H.escape(p["code"])
    return _base(f"""
<div class=abs style="left:0;right:0;top:0;height:420px;background:linear-gradient(180deg,rgba(15,20,17,.72),rgba(15,20,17,0))"></div>
<div class=abs style="left:0;right:0;bottom:0;height:760px;background:linear-gradient(0deg,rgba(15,20,17,.92),rgba(15,20,17,.55) 55%,rgba(15,20,17,0))"></div>
{_mark()}
{_lights()}
<div class="abs tag" style="left:0;right:0;top:250px;text-align:center"><span style="background:{'#C8102E' if _lights() else Y};color:{C if _lights() else K};padding:16px 34px;border-radius:50px;font-size:34px;letter-spacing:4px">{('🎄 HOLIDAY ' if _lights() else '') + name}</span></div>
<div class="abs" style="left:64px;right:64px;top:1230px;text-align:center"><div class=tag style="font-size:44px;color:{C}">SAVE UP TO</div><div class=big style="font-size:300px;color:{Y};line-height:1">${amt}</div></div>
<div class="abs" style="left:64px;right:64px;top:1630px;text-align:center;font-size:44px;font-weight:700">Code <span style="background:{Y};color:{K};padding:6px 26px;border-radius:14px;font-weight:900;letter-spacing:3px">{code}</span> at checkout</div>
<div class="abs" style="left:64px;right:64px;top:1720px;text-align:center;font-size:30px;font-weight:600;color:{Y}">Book in minutes on ArahRides.com</div>""", True)

def end_html(p):
    name, amt, code, terms = H.escape(p["name"]), p["amount"], H.escape(p["code"]), H.escape(p.get("terms", "Conditions apply."))
    return _base(f"""
<div class=abs style="inset:0;background:radial-gradient(circle at 50% 36%,rgba(232,169,58,.22),rgba(11,107,58,.10) 45%,rgba(26,31,28,0) 70%)"></div>
{_lights()}{_mark()}
<div class="abs tag" style="left:0;right:0;top:250px;text-align:center;font-size:40px;color:#E63946">{'🎄 HOLIDAY' if _lights() else ''}</div>
<div class="abs big" style="left:0;right:0;top:300px;text-align:center;font-size:130px">{name.replace(' + ', '<br>+ ')}</div>
<div class="abs" style="left:0;right:0;top:700px;text-align:center"><div class=tag style="font-size:50px">SAVE UP TO</div><div class=big style="font-size:300px;color:{Y};line-height:1">${amt}</div></div>
<div class=ticket style="top:1120px;width:820px;height:230px;margin-left:-410px"><div class=dash></div><div class=tag style="font-size:24px;letter-spacing:5px;color:{G}">PROMO CODE AT CHECKOUT</div><div class=big style="font-size:118px;letter-spacing:4px">{code}</div></div>
<div class="abs" style="left:64px;right:64px;top:1390px;text-align:center;font-size:36px;font-weight:600">on your booking at <b style="color:{Y}">ArahRides.com</b></div>
<div class="abs" style="left:64px;right:64px;top:1470px;height:100px;background:{Y};color:{K};border-radius:60px;display:flex;justify-content:space-between;align-items:center;padding:0 44px;font-weight:800;font-size:38px"><span>Book in minutes: ArahRides.com</span><span style="font-size:20px;text-align:right;line-height:1.25">WhatsApp Winston<br>wa.me/12013713152</span></div>
{_pay()}
<div class="abs" style="left:64px;right:64px;top:1730px;text-align:center;font-size:22px;opacity:.7">{terms}</div>""", False)

def reel_end_html(head, sub=""):
    """The branded last frame of every Reel: logo, the post's offer, how to book, how to pay."""
    from . import templates as T
    pr = None
    try:
        from . import promo as P
        import datetime as _dt
        pr = P.active(T.CURRENT_DATE or _dt.date.today())
    except Exception:
        pass
    code = (f'<div class="abs" style="left:64px;right:64px;top:1020px;text-align:center;font-size:38px;font-weight:700">Code <span style="background:{Y};color:{K};padding:6px 24px;border-radius:14px;font-weight:900;letter-spacing:3px">{H.escape(pr["code"])}</span> · up to ${pr["amount"]} off</div>' if pr else "")
    return _base(f"""
<div class=abs style="inset:0;background:radial-gradient(circle at 50% 30%,rgba(11,107,58,.55),rgba(26,31,28,.86) 70%)"></div>
{_lights()}
<div class=abs style="left:0;right:0;top:170px;display:flex;justify-content:center">{_mark().replace('class="abs" ', '').replace('left:52px;top:110px;', '').replace('left:64px;top:140px;', '').replace('width:150px', 'width:240px')}</div>
<div class="abs big" style="left:70px;right:70px;top:560px;text-align:center;font-size:92px;line-height:1.02;text-wrap:balance">{H.escape(head)}</div>
<div class="abs" style="left:90px;right:90px;top:{"860" if len(head) < 34 else "900"}px;text-align:center;font-size:38px;opacity:.9">{H.escape(sub)}</div>
{code}
<div class="abs" style="left:90px;right:90px;top:1160px;height:120px;background:{Y};color:{K};border-radius:70px;display:flex;align-items:center;justify-content:center;font-weight:900;font-size:46px">Book in minutes · ArahRides.com</div>
<div class="abs" style="left:64px;right:64px;top:1320px;text-align:center;font-size:34px;font-weight:700">💬 WhatsApp Winston 24/7 · wa.me/12013713152</div>
<div class="abs" style="left:64px;right:64px;top:1400px;text-align:center;font-size:30px;opacity:.9">Airport pickup: Montego Bay · Kingston · Ocho Rios</div>
{_pay().replace('top:1600px','top:1500px')}
<div class="abs" style="left:64px;right:64px;top:1660px;text-align:center;font-size:22px;opacity:.65">Check availability and book at www.arahrides.com or with Winston on WhatsApp.</div>""", True)

def render_reel_end(head, sub, out):
    from .render import page
    out = Path(out); out.parent.mkdir(parents=True, exist_ok=True)
    pg = page(1080, 1920)
    try:
        pg.set_content(reel_end_html(head, sub)); pg.wait_for_timeout(250); pg.screenshot(path=str(out), omit_background=True)   # see-through: the opening shot shows behind it, so the Reel loops
    finally:
        pg.close()
    return out

def render(p, outdir):
    """Writes banner.png (transparent) and end.png into outdir. Returns (banner, end)."""
    from .render import page
    outdir = Path(outdir); outdir.mkdir(parents=True, exist_ok=True)
    b, e = outdir / "banner.png", outdir / "end.png"
    pg = page(1080, 1920)
    try:
        pg.set_content(banner_html(p)); pg.wait_for_timeout(250); pg.screenshot(path=str(b), omit_background=True)
        pg.set_content(end_html(p)); pg.wait_for_timeout(250); pg.screenshot(path=str(e))
    finally:
        pg.close()
    return b, e
