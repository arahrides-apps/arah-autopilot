"""HTML for each post design (1080x1350). Brand colours and contact details come from config.yaml.
v2: premium look. Wordmark badge, Jamaican-flag stripe, pill buttons, highlighted headlines, boarding-pass offer card, versus and event posters."""
import html, math
from pathlib import Path

E = html.escape
B = {"green": "#0B6B3A", "gold": "#E8A93A", "cream": "#F1ECE0", "dark": "#1A1F1C", "name": "Arah Rides", "handle": "@arahrides",
     "site": "arahrides.com", "wa": "+1 201-371-3152", "wa_link": "wa.me/12013713152", "tag": "Rent Jamaican. Discover the Real Jamaica."}
F = "font-family:Inter,'Helvetica Neue',Arial,'Liberation Sans',sans-serif"
HD = F + ";font-weight:800;letter-spacing:-1.5px"
WA = ('<svg viewBox="0 0 24 24" width="44" height="44"><circle cx="12" cy="12" r="12" fill="#25D366"/>'
      '<path fill="#fff" d="M12 4.6a7.4 7.4 0 0 0-6.4 11.1L4.6 19.4l3.8-1a7.4 7.4 0 1 0 3.6-13.8zm3.9 10.2c-.2.5-1 .9-1.4 1-.4 0-.8.2-2.7-.6-2.3-.9-3.7-3.2-3.8-3.4-.1-.1-.9-1.2-.9-2.3s.6-1.6.8-1.9c.2-.2.4-.3.6-.3h.4c.1 0 .3 0 .5.4l.7 1.7c.1.1.1.3 0 .4l-.3.5-.3.3c-.1.1-.2.3-.1.5.5.8 1.1 1.5 1.9 2 .3.2.6.3.9.5.2.1.4.1.5-.1l.7-.8c.2-.2.3-.2.5-.1l1.6.8c.2.1.3.2.4.3 0 .2 0 .7-.2 1.2z"/></svg>')

def configure(cfg):
    b = cfg["brand"]
    B.update(green=b["green"], gold=b["gold"], cream=b["cream"], dark=b["dark"], name=b["name"], handle=b["handle"],
             site=b["site"], wa=b["whatsapp"], wa_link=b.get("wa_link", "wa.me/12013713152"), tag=b["tagline"])

def c():
    return B["green"], B["gold"], B["cream"], B["dark"]

def fs(t, mx=120):
    n = len(t)
    return mx if n <= 18 else int(mx * .88) if n <= 30 else int(mx * .72) if n <= 48 else int(mx * .6)

def hl(text, ac, frac=.4):
    """Headline with the closing words in the accent colour."""
    w = text.split()
    if len(w) <= 1:
        return f'<span style="color:{ac}">{E(text)}</span>'
    k = max(1, round(len(w) * frac)) if len(w) > 3 else 1
    return E(" ".join(w[:-k])) + f' <span style="color:{ac}">{E(" ".join(w[-k:]))}</span>'

STRIPE = ('<div style="position:absolute;left:0;right:0;bottom:0;height:16px;display:flex;z-index:9"><i style="flex:1;background:#111"></i>'
          '<i style="flex:1;background:#E8A93A"></i><i style="flex:1;background:#0B6B3A"></i></div>')

def wrap(inner, h, bg, fg):
    return (f'<!doctype html><html><head><meta charset="utf-8"><style>body{{margin:0}}div{{box-sizing:border-box}}</style></head><body>'
            f'<div style="width:1080px;height:{h}px;position:relative;overflow:hidden;background:{bg};color:{fg};{F}">{inner}{STRIPE}</div></body></html>')

def mark(col, right=None, ring=None, badge=None):
    G, Y, C, K = c()
    bdg, bfg = (badge, Y) if badge else (Y, K)
    pill = (f'<div style="font-size:20px;font-weight:800;letter-spacing:3.5px;color:{col};border:2px solid {ring or col};border-radius:40px;padding:10px 22px">{E(right)}</div>' if right else "")
    return (f'<div style="display:flex;justify-content:space-between;align-items:center"><div style="display:flex;align-items:center;gap:14px">'
            f'<div style="width:50px;height:50px;border-radius:50%;background:{bdg};color:{bfg};display:flex;align-items:center;justify-content:center;{HD};font-size:30px;letter-spacing:0">A</div>'
            f'<div style="{HD};font-size:36px;color:{col};letter-spacing:-.5px">ARAH<span style="font-weight:500;opacity:.9"> RIDES</span></div></div>{pill}</div>')

def top(col, right):
    return mark(col, right)

def foot(bg, fg, tagc, cta=None):
    cta = cta or "Book now: " + B["site"]
    return (f'<div style="background:{bg};color:{fg};border-radius:70px;padding:20px 28px 20px 46px;display:flex;justify-content:space-between;align-items:center;gap:20px;box-shadow:0 14px 30px rgba(0,0,0,.25)">'
            f'<div style="{HD};font-size:36px;letter-spacing:-.8px">{E(cta)}</div>'
            f'<div style="display:flex;align-items:center;gap:14px"><div style="font-size:22px;font-weight:800;text-align:right;line-height:1.2">WhatsApp Winston<br><span style="font-weight:600">{E(B["wa_link"])}</span></div>{WA}</div></div>'
            f'<div style="display:flex;justify-content:space-between;font-size:22px;font-weight:600;color:{tagc};padding:0 12px 14px"><span>{E(B["tag"])}</span><span>{E(B["handle"])}</span></div>')

def col(inner, bg, fg, gap=30, deco=""):
    dark = bg != B["cream"]
    pat = f'repeating-linear-gradient(135deg,{"rgba(255,255,255,.04)" if dark else "rgba(0,0,0,.035)"} 0 2px,transparent 2px 28px)'
    return wrap(f'<div style="position:absolute;inset:0;background:{pat}"></div>{deco}'
                f'<div style="position:absolute;inset:0;padding:64px 68px 40px;display:flex;flex-direction:column;gap:{gap}px">{inner}</div>', 1350, bg, fg)

def img(path, pos="50% 50%"):
    return (f'<img src="{Path(path).resolve().as_uri()}" style="position:absolute;inset:0;width:100%;height:100%;object-fit:cover;object-position:{pos};filter:saturate(1.14) contrast(1.06)">')

def cta_bar(bg, fg, label=None):
    label = label or "Book now: " + B["site"]
    return (f'<div style="display:flex;justify-content:space-between;align-items:center;background:{bg};color:{fg};border-radius:70px;padding:16px 24px 16px 42px;box-shadow:0 14px 30px rgba(0,0,0,.3)">'
            f'<div style="{HD};font-size:34px;letter-spacing:-.8px">{E(label)}</div>'
            f'<div style="display:flex;align-items:center;gap:12px"><div style="font-size:21px;font-weight:800;text-align:right;line-height:1.2">WhatsApp Winston<br><span style="font-weight:600">{E(B["wa_link"])}</span></div>{WA}</div></div>')

def chip(t, bg, fg):
    return f'<div style="align-self:flex-start;background:{bg};color:{fg};font-size:24px;font-weight:800;letter-spacing:4px;padding:12px 26px;border-radius:40px">{E(t)}</div>'

def rings(ac, op=.16):
    return (f'<div style="position:absolute;right:-230px;top:-230px;width:700px;height:700px;border-radius:50%;border:70px solid {ac};opacity:{op}"></div>'
            f'<div style="position:absolute;left:-190px;bottom:230px;width:420px;height:420px;border-radius:50%;background:{ac};opacity:{op * .6}"></div>')

# ---------------------------------------------------------------- typographic posts
def big(k, h, b, bg="green", cta=None):
    G, Y, C, K = c()
    bgc, fg, ac = {"green": (G, C, Y), "dark": (K, C, Y), "gold": (Y, K, G), "cream": (C, K, G)}[bg]
    chipbg, chipfg = (K, Y) if bg == "gold" else (ac, K if ac == Y else C)
    return col(mark(ac if bg != "gold" else K, None, None, K if bg == "gold" else None) + '<div style="flex-grow:1;display:flex;flex-direction:column;justify-content:center;gap:36px">'
               + chip(k, chipbg, chipfg) +
               f'<h1 style="margin:0;{HD};font-size:{fs(h, 140)}px;line-height:.98;color:{fg}">{hl(h, ac if bg != "gold" else G)}</h1>'
               f'<div style="width:120px;height:10px;border-radius:6px;background:{ac}"></div>'
               f'<div style="font-size:42px;line-height:1.35;font-weight:500">{E(b)}</div></div>' + foot(ac if bg != "gold" else K, bgc if bg in ("green", "dark") else (Y if bg == "gold" else C), ac if bg != "gold" else K, cta),
               bgc, fg, 30, rings(ac if bg != "gold" else G))

def qa(h, a):
    G, Y, C, K = c()
    return col(mark(G, "ASK ARAH") +
               f'<div style="display:flex;gap:22px;align-items:flex-start;margin-top:10px"><div style="min-width:86px;height:86px;border-radius:50%;background:{G};color:{Y};{HD};font-size:54px;display:flex;align-items:center;justify-content:center;letter-spacing:0">Q</div>'
               f'<h1 style="margin:0;{HD};font-size:{fs(h, 100)}px;line-height:1.02;color:{K}">{hl(h, G)}</h1></div>'
               f'<div style="flex-grow:1;background:{G};color:{C};border-radius:40px;padding:50px 54px;display:flex;flex-direction:column;justify-content:center;gap:18px;position:relative;box-shadow:0 20px 40px rgba(11,107,58,.3)">'
               f'<div style="position:absolute;left:50px;top:-18px;width:36px;height:36px;background:{G};transform:rotate(45deg)"></div>'
               f'<div style="display:flex;align-items:center;gap:14px;font-size:24px;font-weight:800;letter-spacing:4px;color:{Y}"><div style="width:44px;height:6px;background:{Y};border-radius:4px"></div>THE ANSWER</div>'
               f'<div style="font-size:44px;line-height:1.3;font-weight:500">{E(a)}</div></div>'
               + foot(Y, K, G), C, K, 30, rings(G, .08))

def lst(k, h, items, cta=None):
    G, Y, C, K = c()
    rows = "".join(f'<div style="display:flex;gap:26px;align-items:center;background:#fff;color:{K};border-radius:34px;padding:22px 30px;box-shadow:0 10px 24px rgba(0,0,0,.10);border-left:12px solid {Y}">'
                   f'<div style="min-width:70px;height:70px;border-radius:50%;background:{G};color:{Y};{HD};font-size:40px;display:flex;align-items:center;justify-content:center;letter-spacing:0">{i + 1}</div>'
                   f'<div style="font-size:{34 if len(items) > 4 else 37}px;line-height:1.22;font-weight:700">{E(x)}</div></div>'
                   for i, x in enumerate(items))
    return col(mark(G, B["name"].upper() if False else None) + chip(k, G, Y) +
               f'<h1 style="margin:0;{HD};font-size:{fs(h, 108)}px;line-height:1;color:{K}">{hl(h, G)}</h1>'
               f'<div style="flex-grow:1;display:flex;flex-direction:column;gap:16px;justify-content:center">{rows}</div>' + foot(Y, K, G, cta), C, K, 26, rings(G, .07))

def chat(h, u, b):
    G, Y, C, K = c()
    return col(mark(Y, "MEET WINSTON") + f'<h1 style="margin:0;{HD};font-size:{fs(h, 112)}px;line-height:1;color:{C}">{hl(h, Y)}</h1>'
               f'<div style="flex-grow:1;display:flex;flex-direction:column;gap:22px;justify-content:center;background:#E7DFD0;border-radius:40px;padding:44px">'
               f'<div style="align-self:flex-start;background:#fff;color:{K};border-radius:28px 28px 28px 6px;padding:22px 32px;font-size:36px;max-width:720px;line-height:1.3;box-shadow:0 6px 14px rgba(0,0,0,.12)">{E(u)}</div>'
               f'<div style="align-self:flex-end;background:#DCF8C6;color:{K};border-radius:28px 28px 6px 28px;padding:22px 32px;font-size:36px;max-width:800px;line-height:1.3;box-shadow:0 6px 14px rgba(0,0,0,.12)">{E(b)}</div></div>'
               f'<div style="font-size:30px;color:{C};font-weight:600">No app to download. Quote and book in WhatsApp. Pay by Stripe.</div>' + foot(Y, K, Y, "Say Hi to Winston"), K, C, 28, rings(Y, .1))

def slide(n, t, h, b, alt=False, cta=False):
    G, Y, C, K = c()
    bg, fg, ac = (C, K, G) if alt else (G, C, Y)
    ctab = (f'<div style="background:{ac};color:{C if alt else K};border-radius:70px;padding:28px 40px;{HD};font-size:32px;text-align:center">Book now: {E(B["site"])}</div>' if cta else "")
    deco = (rings(ac, .12) + f'<div style="position:absolute;right:50px;top:170px;{HD};font-size:380px;line-height:1;color:{ac};opacity:.16">{n - 1 if n > 1 else n}</div>')
    return col(mark(ac, f"{n}/{t}") + '<div style="flex-grow:1;display:flex;flex-direction:column;justify-content:center;gap:34px">'
               f'<h1 style="margin:0;{HD};font-size:{fs(h, 128)}px;line-height:.98;color:{fg}">{hl(h, ac)}</h1>'
               f'<div style="width:120px;height:10px;border-radius:6px;background:{ac}"></div>'
               f'<div style="font-size:46px;line-height:1.3">{E(b)}</div></div>{ctab}'
               f'<div style="display:flex;justify-content:space-between;font-size:22px;font-weight:600;color:{ac};padding-bottom:14px"><span>{E(B["tag"])}</span><span>{E(B["handle"])}</span></div>', bg, fg, 28, deco)

# ---------------------------------------------------------------- feature posters
def ticket(k, h, b, buy=False):
    """Boarding-pass style card for the lounge pass offer."""
    G, Y, C, K = c()
    bars = "".join(f'<i style="display:block;width:{2 + (i * 7) % 5}px;height:54px;background:{K};margin-right:{3 + (i * 3) % 4}px"></i>' for i in range(34))
    plane = f'<svg viewBox="0 0 24 24" width="54" height="54"><path fill="{G}" d="M21 16v-2l-8-5V3.5a1.5 1.5 0 0 0-3 0V9l-8 5v2l8-2.5V19l-2 1.5V22l3.5-1 3.5 1v-1.5L13 19v-5.5z"/></svg>'
    card = (f'<div style="background:{C};color:{K};border-radius:36px;position:relative;box-shadow:0 30px 60px rgba(0,0,0,.45);overflow:hidden">'
            f'<div style="background:{Y};padding:22px 40px;display:flex;justify-content:space-between;align-items:center"><div style="{HD};font-size:34px;letter-spacing:-.5px">DEPARTURE LOUNGE PASS</div>{plane}</div>'
            f'<div style="padding:40px 40px 32px;display:flex;flex-direction:column;gap:24px">'
            f'<div style="display:flex;gap:18px">'
            f'<div style="flex:1;border:3px solid {G};border-radius:22px;padding:24px 26px"><div style="font-size:21px;font-weight:800;letter-spacing:3px;color:{G}">AIRPORT</div><div style="{HD};font-size:46px;letter-spacing:-.5px">Club Mobay</div></div>'
            f'<div style="flex:1;border:3px solid {G};border-radius:22px;padding:24px 26px"><div style="font-size:21px;font-weight:800;letter-spacing:3px;color:{G}">OR</div><div style="{HD};font-size:46px;letter-spacing:-.5px">Club Kingston</div></div></div>'
            f'<div style="display:flex;gap:18px"><div style="flex:1;background:{G};color:{C};border-radius:22px;padding:24px 26px"><div style="font-size:21px;font-weight:800;letter-spacing:3px;color:{Y}">GUESTS</div><div style="{HD};font-size:46px;letter-spacing:-.5px">1 guest</div></div>'
            f'<div style="flex:1;background:{G};color:{C};border-radius:22px;padding:24px 26px"><div style="font-size:21px;font-weight:800;letter-spacing:3px;color:{Y}">WITH</div><div style="{HD};font-size:46px;letter-spacing:-.5px">7+ day rental</div></div></div></div>'
            f'<div style="border-top:4px dashed {K};opacity:.35;margin:0 24px"></div>'
            f'<div style="padding:18px 40px 26px;display:flex;justify-content:space-between;align-items:center;gap:20px"><div style="display:flex">{bars}</div>'
            f'<div style="font-size:21px;font-weight:700;line-height:1.25;text-align:right;max-width:330px">Not combinable with other promo codes or discounts. Conditions apply.</div></div></div>')
    return col(mark(Y, "LOUNGE PASS") + chip(k, Y, K) +
               f'<h1 style="margin:0;{HD};font-size:{fs(h, 100)}px;line-height:1;color:{C}">{hl(h, Y)}</h1>' + card +
               f'<div style="flex-grow:1"></div>' + foot(Y, K, Y, "Book 7+ days: " + B["site"] if not buy else "Book now: " + B["site"]), G, C, 26, rings(Y, .14))

def versus(k, h, them, us):
    G, Y, C, K = c()
    no = f'<svg viewBox="0 0 24 24" width="48" height="48" style="flex:none"><circle cx="12" cy="12" r="12" fill="#B33A3A"/><path d="M8 8l8 8M16 8l-8 8" stroke="#fff" stroke-width="2.6" stroke-linecap="round"/></svg>'
    yes = f'<svg viewBox="0 0 24 24" width="48" height="48" style="flex:none"><circle cx="12" cy="12" r="12" fill="{G}"/><path d="M7 12.5l3.2 3.2L17 9" stroke="#fff" stroke-width="2.8" stroke-linecap="round" fill="none"/></svg>'
    def rows(items, ic, col_):
        return "".join(f'<div style="display:flex;gap:16px;align-items:flex-start;font-size:40px;line-height:1.2;font-weight:700;color:{col_}">{ic}<div>{E(x)}</div></div>' for x in items)
    left = (f'<div style="flex:1;background:#2A302C;border-radius:36px;padding:38px 34px;display:flex;flex-direction:column;gap:40px"><div style="font-size:22px;font-weight:800;letter-spacing:3.5px;color:#9AA39D">BIG RENTAL COMPANIES</div>{rows(them, no, "#C9D0CB")}</div>')
    right = (f'<div style="flex:1;background:{Y};color:{K};border-radius:36px;padding:38px 34px;display:flex;flex-direction:column;gap:40px;box-shadow:0 20px 44px rgba(232,169,58,.35)"><div style="font-size:22px;font-weight:800;letter-spacing:3.5px;color:{G}">ARAH RIDES</div>{rows(us, yes, K)}</div>')
    return col(mark(Y, "BOOK THE CAR YOU SEE") + chip(k, Y, K) + f'<h1 style="margin:0;{HD};font-size:{fs(h, 104)}px;line-height:1;color:{C}">{hl(h, Y)}</h1>'
               f'<div style="flex-grow:1;display:flex;gap:20px">{left}{right}</div>' + foot(Y, K, Y), K, C, 28, rings(Y, .08))

def event(k, h, b, badge="", cta=None):
    G, Y, C, K = c()
    parts = badge.split(" ", 1) if badge else ["", ""]
    mon, day = (parts + [""])[:2]
    date = (f'<div style="width:300px;background:{C};color:{K};border-radius:34px;overflow:hidden;text-align:center;box-shadow:0 24px 48px rgba(0,0,0,.4);transform:rotate(-4deg)">'
            f'<div style="background:{Y};{HD};font-size:46px;padding:14px;letter-spacing:4px">{E(mon)}</div>'
            f'<div style="{HD};font-size:{86 if len(day) < 6 else 62}px;padding:26px 10px 30px;line-height:1">{E(day)}</div></div>') if badge else ""
    return col(mark(Y, "HAPPENING IN JAMAICA") + '<div style="flex-grow:1;display:flex;flex-direction:column;justify-content:center;gap:34px">'
               f'<div style="display:flex;justify-content:space-between;align-items:center;gap:30px"><div style="display:flex;flex-direction:column;gap:26px;flex:1">{chip(k, Y, K)}</div>{date}</div>'
               f'<h1 style="margin:0;{HD};font-size:{fs(h, 128)}px;line-height:.98;color:{C}">{hl(h, Y)}</h1>'
               f'<div style="width:120px;height:10px;border-radius:6px;background:{Y}"></div>'
               f'<div style="font-size:42px;line-height:1.35;font-weight:500">{E(b)}</div></div>' + foot(Y, K, Y, cta), G, C, 28, rings(Y, .16))

# ---------------------------------------------------------------- photo posts
def sticker(a, b, left=False, y="top:150px", rot=-9, s=250):
    G, Y, C, K = c()
    x = "left:56px" if left else "right:56px"
    return (f'<div style="position:absolute;{x};{y};width:{s}px;height:{s}px;border-radius:50%;background:{Y};color:{K};display:flex;flex-direction:column;align-items:center;justify-content:center;'
            f'transform:rotate({rot}deg);box-shadow:0 10px 30px rgba(0,0,0,.35);border:6px solid {C}"><div style="{HD};font-size:{int(s * .42)}px;line-height:1">{E(a)}</div>'
            f'<div style="font-size:{int(s * .1)}px;font-weight:800;letter-spacing:3px">{E(b)}</div></div>')

def hero(path, k, h1, h2, sub, pos="50% 50%", at="b", cta=None, st=None):
    G, Y, C, K = c()
    g = ("linear-gradient(180deg,rgba(15,20,17,.6) 0%,rgba(15,20,17,0) 24%,rgba(15,20,17,.30) 40%,rgba(15,20,17,.80) 62%,rgba(15,20,17,.95) 100%)" if at == "b" else
         "linear-gradient(180deg,rgba(15,20,17,.92) 0%,rgba(15,20,17,.6) 45%,rgba(15,20,17,.15) 62%,rgba(15,20,17,.65) 100%)")
    right = 330 if (st and at == "t") else 64
    size = min(fs(h1 + h2, 124), 100) if (st and at == "t") else fs(h1 + h2, 124)
    box = (f'<div style="position:absolute;left:64px;right:{right}px;{"bottom:56px" if at == "b" else "top:150px"};display:flex;flex-direction:column;gap:20px">'
           + chip(k, Y, K) +
           f'<h1 style="margin:0;{HD};font-size:{size}px;line-height:.96;color:{C};text-shadow:0 4px 24px rgba(0,0,0,.4)">{E(h1)} <span style="color:{Y}">{E(h2)}</span></h1>'
           f'<div style="width:110px;height:9px;border-radius:6px;background:{Y}"></div>'
           f'<div style="font-size:34px;line-height:1.3;color:{C};margin-bottom:6px">{E(sub)}</div>' + (cta_bar(Y, K, cta) if at == "b" else "") + "</div>")
    foot_ = "" if at == "b" else f'<div style="position:absolute;left:64px;right:64px;bottom:60px">{cta_bar(Y, K, cta)}</div>'
    return wrap(img(path, pos) + f'<div style="position:absolute;inset:0;background:{g}"></div>'
                f'<div style="position:absolute;left:64px;right:64px;top:56px">{mark(C, "RENT JAMAICAN", "rgba(241,236,224,.6)")}</div>' + box + foot_ + (sticker(*st) if st else ""), 1350, K, C)

def split(path, k, h, sub, pos="50% 50%", palette="green", cta=None):
    G, Y, C, K = c()
    bg, fg, ac, fb = (G, C, Y, K) if palette == "green" else (C, K, G, C)
    return wrap(f'<div style="position:absolute;left:0;right:0;top:0;height:760px;overflow:hidden">{img(path, pos)}'
                f'<div style="position:absolute;inset:0;background:linear-gradient(180deg,rgba(15,20,17,.55),rgba(15,20,17,0) 30%)"></div>'
                f'<div style="position:absolute;left:56px;right:56px;top:50px">{mark(C, "RENT JAMAICAN", "rgba(241,236,224,.6)")}</div></div>'
                f'<div style="position:absolute;left:0;right:0;top:700px;height:70px;background:{bg};border-radius:70px 70px 0 0"></div>'
                f'<div style="position:absolute;left:64px;right:64px;top:800px;bottom:50px;display:flex;flex-direction:column;gap:18px">'
                + chip(k, ac, fb if palette == "green" else C) +
                f'<h1 style="margin:0;{HD};font-size:{fs(h, 98)}px;line-height:1;color:{fg}">{hl(h, ac, .35)}</h1>'
                f'<div style="flex-grow:1;font-size:32px;line-height:1.3">{E(sub)}</div>{cta_bar(ac, fb if palette == "green" else C, cta)}</div>', 1350, bg, fg)

def ccover(path, k, h, s, pos="50% 50%"):
    G, Y, C, K = c()
    return wrap(img(path, pos) + '<div style="position:absolute;inset:0;background:linear-gradient(180deg,rgba(15,20,17,.55),rgba(15,20,17,0) 28%,rgba(15,20,17,.25) 44%,rgba(15,20,17,.93))"></div>'
                f'<div style="position:absolute;left:64px;right:64px;top:56px;display:flex;justify-content:space-between;align-items:center">{mark(C)}'
                f'<div style="background:{Y};color:{K};font-size:24px;font-weight:800;letter-spacing:3px;padding:14px 28px;border-radius:40px">SWIPE →</div></div>'
                f'<div style="position:absolute;left:64px;right:64px;bottom:90px;display:flex;flex-direction:column;gap:20px">{chip(k, Y, K)}'
                f'<h1 style="margin:0;{HD};font-size:{fs(h, 132)}px;line-height:.96;color:{C}">{hl(h, Y)}</h1><div style="font-size:34px;color:{C}">{E(s)}</div></div>', 1350, K, C)

def ccover_plain(k, h, s):
    G, Y, C, K = c()
    return col(mark(Y, "SWIPE →") + f'<div style="flex-grow:1"></div>{chip(k, Y, K)}'
               f'<h1 style="margin:0;{HD};font-size:{fs(h, 140)}px;line-height:.98;color:{C}">{hl(h, Y)}</h1><div style="font-size:38px;color:{C};padding-bottom:60px">{E(s)}</div>', G, C, 30, rings(Y, .14))
