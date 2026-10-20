"""HTML for each post design (1080x1350). Brand colours and contact details come from config.yaml."""
import html
from pathlib import Path

E = html.escape
B = {"green": "#0B6B3A", "gold": "#E8A93A", "cream": "#F1ECE0", "dark": "#1A1F1C", "name": "Arah Rides", "handle": "@arahrides",
     "site": "arahrides.com", "wa": "+1 201-371-3152", "wa_link": "wa.me/12013713152", "tag": "Rent Jamaican. Discover the Real Jamaica."}
F = "font-family:Inter,'Helvetica Neue',Arial,'Liberation Sans',sans-serif"
HD = F + ";font-weight:800;letter-spacing:-1px"

def configure(cfg):
    b = cfg["brand"]
    B.update(green=b["green"], gold=b["gold"], cream=b["cream"], dark=b["dark"], name=b["name"], handle=b["handle"],
             site=b["site"], wa=b["whatsapp"], wa_link=b.get("wa_link", "wa.me/12013713152"), tag=b["tagline"])

def c():
    return B["green"], B["gold"], B["cream"], B["dark"]

def fs(t, mx=120):
    n = len(t)
    return mx if n <= 18 else int(mx * .86) if n <= 30 else int(mx * .7) if n <= 48 else int(mx * .58)

def wrap(inner, h, bg, fg):
    return (f'<!doctype html><html><head><meta charset="utf-8"><style>body{{margin:0}}div{{box-sizing:border-box}}</style></head><body>'
            f'<div style="width:1080px;height:{h}px;position:relative;overflow:hidden;background:{bg};color:{fg};{F}">{inner}</div></body></html>')

def top(col, right):
    return (f'<div style="display:flex;justify-content:space-between;align-items:center"><div style="{HD};font-size:40px;color:{col}">{E(B["name"].upper())}</div>'
            f'<div style="font-size:24px;font-weight:700;letter-spacing:3px;color:{col}">{E(right)}</div></div>')

def foot(bg, fg, tagc, cta=None):
    cta = cta or "Book: " + B["site"]
    return (f'<div style="background:{bg};color:{fg};border-radius:24px;padding:26px 34px;display:flex;justify-content:space-between;align-items:center;gap:20px">'
            f'<div style="{HD};font-size:36px">{E(cta)}</div><div style="font-size:24px;font-weight:700;text-align:right;line-height:1.25">WhatsApp Winston<br>{E(B["wa_link"])}</div></div>'
            f'<div style="display:flex;justify-content:space-between;font-size:23px;font-weight:600;color:{tagc}"><span>{E(B["tag"])}</span><span>{E(B["handle"])}</span></div>')

def col(inner, bg, fg, gap=30):
    return wrap(f'<div style="position:absolute;inset:0;padding:72px;display:flex;flex-direction:column;gap:{gap}px">{inner}</div>', 1350, bg, fg)

def img(path, pos="50% 50%"):
    return f'<img src="{Path(path).resolve().as_uri()}" style="position:absolute;inset:0;width:100%;height:100%;object-fit:cover;object-position:{pos}">'

def cta_bar(bg, fg, label=None):
    label = label or "Book: " + B["site"]
    return (f'<div style="display:flex;justify-content:space-between;align-items:center;background:{bg};color:{fg};border-radius:22px;padding:22px 32px">'
            f'<div style="{HD};font-size:34px">{E(label)}</div><div style="font-size:23px;font-weight:700;text-align:right;line-height:1.25">WhatsApp Winston<br>{E(B["wa_link"])}</div></div>')

# ---------------------------------------------------------------- typographic posts
def big(k, h, b, bg="green", cta=None):
    G, Y, C, K = c()
    bgc, fg, ac = {"green": (G, C, Y), "dark": (K, C, Y), "gold": (Y, K, G), "cream": (C, K, G)}[bg]
    deco = (f'<div style="position:absolute;right:-200px;top:-200px;width:620px;height:620px;border-radius:50%;background:{ac};opacity:.16"></div>'
            f'<div style="position:absolute;left:-140px;bottom:260px;width:320px;height:320px;border-radius:50%;background:{ac};opacity:.09"></div>')
    return col(deco + top(ac, B["name"].upper()) + '<div style="flex-grow:1;display:flex;flex-direction:column;justify-content:center;gap:34px">'
               f'<div style="font-size:27px;font-weight:700;letter-spacing:5px;color:{ac}">{E(k)}</div>'
               f'<h1 style="margin:0;{HD};font-size:{fs(h, 134)}px;line-height:1;color:{fg}">{E(h)}</h1>'
               f'<div style="font-size:44px;line-height:1.35">{E(b)}</div></div>' + foot(ac, bgc if bg != "cream" else C, ac, cta), bgc, fg, 34)

def qa(h, a):
    G, Y, C, K = c()
    return col(top(G, "ASK ARAH") + f'<div style="font-size:27px;font-weight:700;letter-spacing:5px;color:{G}">Q&amp;A</div>'
               f'<h1 style="margin:0;{HD};font-size:{fs(h, 104)}px;line-height:1.02;color:{K}">{E(h)}</h1>'
               f'<div style="flex-grow:1;background:{G};color:{C};border-radius:32px;padding:48px;display:flex;flex-direction:column;justify-content:center;gap:16px">'
               f'<div style="font-size:26px;font-weight:700;letter-spacing:4px;color:{Y}">ANSWER</div><div style="font-size:44px;line-height:1.3;font-weight:500">{E(a)}</div></div>'
               + foot(Y, K, G), C, K, 32)

def lst(k, h, items, cta=None):
    G, Y, C, K = c()
    rows = "".join(f'<div style="display:flex;gap:26px;align-items:center;background:{G};color:{C};border-radius:26px;padding:26px 34px">'
                   f'<div style="{HD};font-size:56px;color:{Y};min-width:56px">{i + 1}</div><div style="font-size:{34 if len(items) > 4 else 36}px;line-height:1.25;font-weight:600">{E(x)}</div></div>'
                   for i, x in enumerate(items))
    return col(top(G, B["name"].upper()) + f'<div style="font-size:27px;font-weight:700;letter-spacing:5px;color:{G}">{E(k)}</div>'
               f'<h1 style="margin:0;{HD};font-size:{fs(h, 104)}px;line-height:1.02;color:{K}">{E(h)}</h1>'
               f'<div style="flex-grow:1;display:flex;flex-direction:column;gap:16px;justify-content:center">{rows}</div>' + foot(Y, K, G, cta), C, K, 30)

def chat(h, u, b):
    G, Y, C, K = c()
    return col(top(Y, "MEET WINSTON") + f'<h1 style="margin:0;{HD};font-size:{fs(h, 108)}px;line-height:1;color:{C}">{E(h)}</h1>'
               f'<div style="flex-grow:1;display:flex;flex-direction:column;gap:22px;justify-content:center;background:{C};border-radius:32px;padding:44px">'
               f'<div style="align-self:flex-start;background:{G};color:{C};border-radius:22px;padding:20px 30px;font-size:34px;max-width:700px;line-height:1.3">{E(u)}</div>'
               f'<div style="align-self:flex-end;background:{Y};color:{K};border-radius:22px;padding:20px 30px;font-size:34px;max-width:780px;line-height:1.3">{E(b)}</div></div>'
               f'<div style="font-size:30px;color:{C}">No app to download. Quote and book in WhatsApp. Pay by Stripe.</div>' + foot(Y, K, Y, "Say Hi"), K, C, 30)

def slide(n, t, h, b, alt=False, cta=False):
    G, Y, C, K = c()
    bg, fg, ac = (C, K, G) if alt else (G, C, Y)
    ctab = (f'<div style="background:{ac};color:{C if alt else K};border-radius:24px;padding:28px 34px;{HD};font-size:31px">Book: {E(B["site"])} · {E(B["wa_link"])}</div>' if cta else "")
    deco = (f'<div style="position:absolute;right:-120px;bottom:120px;width:640px;height:640px;border-radius:50%;background:{ac};opacity:.14"></div>'
            f'<div style="position:absolute;right:50px;top:150px;{HD};font-size:360px;line-height:1;color:{ac};opacity:.18">{n - 1 if n > 1 else n}</div>')
    return col(deco + top(ac, f"{n}/{t}") + '<div style="flex-grow:1;display:flex;flex-direction:column;justify-content:center;gap:34px">'
               f'<h1 style="margin:0;{HD};font-size:{fs(h, 124)}px;line-height:1;color:{fg}">{E(h)}</h1>'
               f'<div style="font-size:46px;line-height:1.3">{E(b)}</div></div>{ctab}'
               f'<div style="display:flex;justify-content:space-between;font-size:23px;font-weight:600;color:{ac}"><span>{E(B["tag"])}</span><span>{E(B["handle"])}</span></div>', bg, fg, 28)

# ---------------------------------------------------------------- photo posts
def sticker(a, b, left=False, y="top:150px", rot=-9, s=250):
    G, Y, C, K = c()
    x = "left:56px" if left else "right:56px"
    return (f'<div style="position:absolute;{x};{y};width:{s}px;height:{s}px;border-radius:50%;background:{Y};color:{K};display:flex;flex-direction:column;align-items:center;justify-content:center;'
            f'transform:rotate({rot}deg);box-shadow:0 10px 30px rgba(0,0,0,.35);border:6px solid {C}"><div style="{HD};font-size:{int(s * .42)}px;line-height:1">{E(a)}</div>'
            f'<div style="font-size:{int(s * .1)}px;font-weight:800;letter-spacing:3px">{E(b)}</div></div>')

def hero(path, k, h1, h2, sub, pos="50% 50%", at="b", cta=None, st=None):
    G, Y, C, K = c()
    g = ("linear-gradient(180deg,rgba(26,31,28,.55) 0%,rgba(26,31,28,0) 28%,rgba(26,31,28,0) 38%,rgba(26,31,28,.88) 100%)" if at == "b" else
         "linear-gradient(180deg,rgba(26,31,28,.9) 0%,rgba(26,31,28,.55) 45%,rgba(26,31,28,.15) 62%,rgba(26,31,28,.6) 100%)")
    right = 330 if (st and at == "t") else 64
    size = min(fs(h1 + h2, 118), 96) if (st and at == "t") else fs(h1 + h2, 118)
    box = (f'<div style="position:absolute;left:64px;right:{right}px;{"bottom:64px" if at == "b" else "top:140px"};display:flex;flex-direction:column;gap:18px">'
           f'<div style="font-size:26px;font-weight:800;letter-spacing:5px;color:{Y}">{E(k)}</div>'
           f'<h1 style="margin:0;{HD};font-size:{size}px;line-height:.98;color:{C}">{E(h1)} <span style="color:{Y}">{E(h2)}</span></h1>'
           f'<div style="font-size:34px;line-height:1.3;color:{C}">{E(sub)}</div>' + (cta_bar(Y, K, cta) if at == "b" else "") + "</div>")
    foot_ = "" if at == "b" else f'<div style="position:absolute;left:64px;right:64px;bottom:60px">{cta_bar(Y, K, cta)}</div>'
    return wrap(img(path, pos) + f'<div style="position:absolute;inset:0;background:{g}"></div>'
                f'<div style="position:absolute;left:64px;top:60px;{HD};font-size:40px;color:{C}">{E(B["name"].upper())}</div>' + box + foot_ + (sticker(*st) if st else ""), 1350, K, C)

def split(path, k, h, sub, pos="50% 50%", palette="green", cta=None):
    G, Y, C, K = c()
    bg, fg, ac, fb = (G, C, Y, K) if palette == "green" else (C, K, G, C)
    return wrap(f'<div style="position:absolute;left:0;right:0;top:0;height:760px;overflow:hidden">{img(path, pos)}'
                f'<div style="position:absolute;left:56px;top:56px;{HD};font-size:40px;color:{C};text-shadow:0 2px 12px rgba(0,0,0,.5)">{E(B["name"].upper())}</div></div>'
                f'<div style="position:absolute;left:0;right:0;top:700px;height:60px;background:{bg};border-radius:60px 60px 0 0"></div>'
                f'<div style="position:absolute;left:64px;right:64px;top:790px;bottom:56px;display:flex;flex-direction:column;gap:18px">'
                f'<div style="font-size:26px;font-weight:800;letter-spacing:5px;color:{ac}">{E(k)}</div>'
                f'<h1 style="margin:0;{HD};font-size:{fs(h, 100)}px;line-height:1;color:{fg}">{E(h)}</h1>'
                f'<div style="flex-grow:1;font-size:32px;line-height:1.3">{E(sub)}</div>{cta_bar(ac, fb, cta)}</div>', 1350, bg, fg)

def ccover(path, k, h, s, pos="50% 50%"):
    G, Y, C, K = c()
    return wrap(img(path, pos) + '<div style="position:absolute;inset:0;background:linear-gradient(180deg,rgba(26,31,28,.5),rgba(26,31,28,0) 30%,rgba(26,31,28,.1) 45%,rgba(26,31,28,.9))"></div>'
                f'<div style="position:absolute;left:64px;right:64px;top:60px;display:flex;justify-content:space-between"><div style="{HD};font-size:40px;color:{C}">{E(B["name"].upper())}</div>'
                f'<div style="background:{Y};color:{K};font-size:24px;font-weight:800;letter-spacing:3px;padding:12px 26px;border-radius:40px">SWIPE →</div></div>'
                f'<div style="position:absolute;left:64px;right:64px;bottom:90px;display:flex;flex-direction:column;gap:20px"><div style="font-size:26px;font-weight:800;letter-spacing:5px;color:{Y}">{E(k)}</div>'
                f'<h1 style="margin:0;{HD};font-size:{fs(h, 128)}px;line-height:.98;color:{C}">{E(h)}</h1><div style="font-size:34px;color:{C}">{E(s)}</div></div>', 1350, K, C)

def ccover_plain(k, h, s):
    G, Y, C, K = c()
    return col(top(Y, "SWIPE →") + f'<div style="flex-grow:1"></div><div style="font-size:27px;font-weight:700;letter-spacing:5px;color:{Y}">{E(k)}</div>'
               f'<h1 style="margin:0;{HD};font-size:{fs(h, 134)}px;line-height:1;color:{C}">{E(h)}</h1><div style="font-size:38px;color:{C};padding-bottom:60px">{E(s)}</div>', G, C, 30)
