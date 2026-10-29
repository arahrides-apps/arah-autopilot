"""Builds a day of posts: picks wording and photos, renders images, writes the queue."""
import re, random, datetime as dt, logging, shutil
from pathlib import Path
from . import templates as T, queue as Q
from .config import ROOT, load_yaml, now as now_fn, tz
from .ledger import Ledger
from .photos import Picker, Photo
from .render import render_all

log = logging.getLogger("generate")
EMOJI = {"experience": "✨", "car_hero": "🚗", "place": "🌴", "qa": "🤔", "tip": "💡", "brand": "🇯🇲", "engage": "💬", "list": "✅", "chat": "💬", "carousel": "👉", "moment": "🇯🇲", "offer": "🎟️"}
TYPE_TAG = {"experience": "#VisitJamaica", "car_hero": "#RoadTrip", "place": "#VisitJamaica", "qa": "#QandA", "tip": "#TravelTips", "brand": "#Jamaica", "engage": "#JamaicaVibes",
            "list": "#TravelJamaica", "chat": "#Winston", "carousel": "#VisitJamaica", "moment": "#Jamaica", "offer": "#Jamaica"}
FALLBACK = {"car_hero": "brand", "place": "tip", "experience": "tip"}
BGS = ["green", "dark", "gold", "cream"]

def hashtags(cfg, typ, extra=None):
    h = cfg["hashtags"]; tags = list(h["always"]); tags.append(TYPE_TAG.get(typ, "#Jamaica"))
    if extra:
        tags.append(extra)
    seen = []; [seen.append(t) for t in tags if t.lower() not in [s.lower() for s in seen]]
    return " ".join(seen[: min(h["max_total"], 5)])

def caption(cfg, typ, text, extra_tag=None, cta=None):
    b = cfg["brand"]
    cta = cta or f"Book: {b['site']}\nWhatsApp Winston: https://{b['wa_link']}"
    return f"{text}\n\n{cta}\n\n{hashtags(cfg, typ, extra_tag)}"

def tidy(*parts):
    return " ".join(p.strip() for p in parts if p and p.strip())

class DayBuilder:
    def __init__(self, cfg, led, picker, date, rng, moments):
        self.cfg, self.led, self.pk, self.date, self.rng = cfg, led, picker, date, rng
        self.bank = expand_bank(load_yaml("bank.yaml")); self.moments = moments; self.notes = []
        self.today = date

    def pick(self, kind):
        lst = self.bank[kind]
        i, cycled = self.led.copy_pick(kind, len(lst), self.today, self.rng, self.cfg["copy_cooldown_days"])
        if cycled:
            n = f"Wording for '{kind}' is running low: older posts are being repeated. Ask Claude to add more to content/bank.yaml."
            if n not in self.notes:
                self.notes.append(n)
        self.led.copy_record(kind, i, self.today)
        return lst[i]

    def photo_flags(self, post, ph):
        post["photo"] = {"id": ph.id, "name": ph.name, "source": ph.source, "credit": ph.credit}
        post["flags"] += ph.flags
        self.led.record(ph.keys(), ph.hash, self.today, ph.source, ph.series)

    # ---- each builder returns (post_fields, [(html,height)])
    def car_hero(self, post):
        ph = self.pk.car()
        if not ph:
            return None
        e = self.pick("hero"); self.photo_flags(post, ph)
        pos = "50% 50%"
        if ph.portrait:
            html = T.hero(ph.path, e["kicker"], e["h1"], e["h2"], e["sub"], pos, at=self.rng.choice("bt"))
        else:
            html = T.split(ph.path, e["kicker"], tidy(e["h1"], e["h2"]), e["sub"], pos, self.rng.choice(["green", "cream"]))
        post["copy_text"] = tidy(e["h1"], e["h2"]) + " " + EMOJI["car_hero"] + "\n\n" + e["sub"]
        post["alt"] = "A rental car in Jamaica. " + tidy(e["h1"], e["h2"])
        post["caption"] = caption(self.cfg, "car_hero", post["copy_text"])
        return [(html, 1350)]

    def place(self, post, kind="place"):
        e = self.pick(kind)
        ph = self.pk.scene(e["query"], e["place"])
        if not ph:
            return None
        self.photo_flags(post, ph)
        txt = ph.text.lower()
        ok = e["place"].lower() in txt or any(w.lower() in txt for w in e.get("also", []))
        pool = self.bank["neutral_exp" if kind == "experience" else "neutral"]
        n = pool[self.rng.randrange(len(pool))]
        use = e if ok else n
        if kind == "experience":
            k = e["k"] if ok else "BEYOND THE RESORT"
        else:
            k = ("DISCOVER " + e["place"].upper()) if ok else "DISCOVER THE REAL JAMAICA"
        if ph.portrait:
            html = T.hero(ph.path, k, use["h1"], use["h2"], use["sub"], at="b")
        else:
            html = T.split(ph.path, k, tidy(use["h1"], use["h2"]), use["sub"], palette=self.rng.choice(["green", "cream"]))
        if not ok:
            post["flags"].append("Place/experience name left out because the photo does not confirm it. Add it only if you know it is right.")
        hook = "" if kind == "place" else "\n\nRent a car and go see it for yourself."
        post["copy_text"] = tidy(use["h1"], use["h2"]) + " " + EMOJI[kind] + "\n\n" + use["sub"] + hook
        post["alt"] = ("Scenery in " + e["place"] + ", Jamaica") if ok else "Scenery in Jamaica"
        post["caption"] = caption(self.cfg, kind, post["copy_text"], "#" + re.sub(r"\W", "", e["place"]) if ok else None)
        return [(html, 1350)]

    def simple(self, post, kind):
        e = self.pick(kind)
        if kind == "qa":
            html = T.qa(e["q"], e["a"]); txt = f"{e['q']} {EMOJI['qa']}\n\n{e['a']}\n\nQuestions? Ask Winston on WhatsApp, any time."
            alt = f"Question and answer graphic: {e['q']}"
        elif kind == "tip":
            html = T.big(e["k"], e["h"], e["b"], self.rng.choice(["cream", "green", "dark"])); txt = f"{e['k'].title()}: {e['h']} {EMOJI['tip']}\n\n{e['b']}"
            alt = f"Tip graphic: {e['h']}"
        elif kind == "brand":
            html = T.big(e["k"], e["h"], e["b"], self.rng.choice(["green", "dark"])); txt = f"{e['h']} {EMOJI['brand']}\n\n{e['b']}"
            alt = f"Arah Rides graphic: {e['h']}"
        elif kind == "engage":
            html = T.big("YOUR TURN", e["h"], e["b"], self.rng.choice(["gold", "dark", "green"])); txt = f"{e['h']} {EMOJI['engage']}\n\n{e['b']}"
            alt = f"Question for followers: {e['h']}"
        elif kind == "list":
            html = T.lst(e["k"], e["h"], e["items"], e.get("cta")); txt = f"{e['h']} {EMOJI['list']}\n\n" + "\n".join(f"{i + 1}) {x}" for i, x in enumerate(e["items"]))
            alt = f"List graphic: {e['h']}"
        elif kind == "chat":
            html = T.chat(e["h"], e["u"], e["b"]); txt = f"{e['h']} {EMOJI['chat']}\n\nWinston is your 24/7 WhatsApp assistant. Quote, book and pay by Stripe. No app."
            alt = f"WhatsApp chat with Winston: {e['u']} / {e['b']}"
        post["copy_text"] = txt; post["alt"] = alt
        post["caption"] = caption(self.cfg, kind, txt, cta=None)
        return [(html, 1350)]

    def carousel(self, post):
        e = self.pick("carousel"); n = len(e["slides"]) + 1
        ph = self.pk.scene(e["query"]) if e.get("query") else None
        if ph:
            self.photo_flags(post, ph)
            cover = T.ccover(ph.path, e["k"], e["title"], e["sub"])
        else:
            cover = T.ccover_plain(e["k"], e["title"], e["sub"])
        pages = [(cover, 1350)]
        for i, (h, b) in enumerate(e["slides"]):
            pages.append((T.slide(i + 2, n, h, b, alt=bool(i % 2), cta=(i == len(e["slides"]) - 1)), 1350))
        body = "\n".join(f"• {h}: {b}" for h, b in e["slides"])
        post["copy_text"] = f"{e['title']} {EMOJI['carousel']}\n\n{e['sub']}\n\n{body}"
        post["alt"] = f"Carousel: {e['title']}"
        post["caption"] = caption(self.cfg, "carousel", post["copy_text"])
        return pages

    def moment(self, post, m, days_left):
        b = m["b"]
        kicker = m["k"] + (f" · {days_left} DAYS TO GO" if days_left > 0 else "")
        html = T.big(kicker, m["h"], b, "gold" if days_left == 0 else "green")
        post["copy_text"] = f"{m['h']} {EMOJI['moment']}\n\n{b}"
        post["alt"] = f"Seasonal graphic: {m['h']}"
        post["caption"] = caption(self.cfg, "moment", post["copy_text"])
        return [(html, 1350)]

    def offer(self, post, name, o):
        html = T.big(name.replace("_", " ").upper(), "Offer", o["text"], "gold")
        post["copy_text"] = o["text"]; post["alt"] = "Offer graphic"
        post["caption"] = caption(self.cfg, "offer", post["copy_text"])
        return [(html, 1350)]

def expand_bank(b):
    for a, c in b.get("this_or_that", []):
        b["engage"].append({"h": f"{a} or {c}?", "b": "Comment your pick."})
    for p in b.get("parishes", []):
        b["engage"].append({"h": f"Driven through {p}?", "b": "Tell us your favourite stop there."})
    for w, m in b.get("patois", []):
        b["tip"].append({"k": "PATOIS 101", "h": w + ".", "b": "It means: " + m})
    return b

def active_moment(cfg, moments, date):
    for m in moments:
        d = dt.date.fromisoformat(str(m["date"])); left = (d - date).days
        if 0 <= left <= m.get("lead_days", 0):
            if m.get("needs_offer"):
                o = cfg["offers"].get(m["needs_offer"], {})
                if not (o.get("enabled") and o.get("text")):
                    continue
                m = dict(m, b=o["text"])
            return m, left
    return None, 0

def generate_day(cfg, led, picker, date, now, render=True, notes=None, skip=()):
    rng = random.Random(f"{date}-{now.timestamp() // 60}")
    b = DayBuilder(cfg, led, picker, date, rng, load_yaml("moments.yaml"))
    mom, left = active_moment(cfg, b.moments, date)
    offer = next(((k, v) for k, v in cfg["offers"].items() if k == "lounge_pass" and v.get("enabled") and v.get("text")), None)
    zone = tz(cfg); posts = []; jobs = []
    pattern = cfg["pattern"][: cfg["posts_per_day"]]
    used_mom = used_offer = False
    for idx, typ0 in enumerate(pattern):
        if "|" in typ0:
            opts = typ0.split("|"); typ0 = opts[(date.toordinal() + idx) % len(opts)]
        hhmm = cfg["slots"][idx]
        at = dt.datetime.combine(date, dt.time.fromisoformat(hhmm), zone)
        if at <= now or hhmm in skip:
            continue
        typ = typ0
        if mom and typ0 == "engage" and not used_mom:
            typ, used_mom = "moment", True
        elif offer and typ0 == "brand" and not used_offer:
            typ, used_offer = "offer", True
        post = {"id": f"{date}_{hhmm.replace(':', '')}_{typ}", "date": str(date), "slot": at.isoformat(), "type": typ, "flags": [], "images": []}
        pages = None; t = typ
        while pages is None:
            if t == "car_hero": pages = b.car_hero(post)
            elif t == "place": pages = b.place(post)
            elif t == "experience": pages = b.place(post, "experience")
            elif t == "carousel": pages = b.carousel(post)
            elif t == "moment": pages = b.moment(post, mom, left)
            elif t == "offer": pages = b.offer(post, *offer)
            else: pages = b.simple(post, t)
            if pages is None:
                nt = FALLBACK.get(t)
                b.notes.append(f"No fresh photo for a {t} post on {date}: made a {nt} post instead.")
                t = nt; post["type"] = nt; post["id"] = f"{date}_{hhmm.replace(':', '')}_{nt}"
        for i, (html_, h) in enumerate(pages):
            rel = f"media/{date}/{post['id']}_{i + 1}.jpg"
            post["images"].append(rel)
            jobs.append((html_, h, Q.DOCS / rel))
        if len(post["caption"]) > 2200 or post["caption"].count("#") > 5:
            raise ValueError("caption rules broken for " + post["id"])
        post["status"] = "pending"
        posts.append(post)
    if render and jobs:
        render_all(jobs)
    if notes is not None:
        notes += b.notes
    return posts

def run(cfg, picker=None, led=None, render=True, days=None):
    now = now_fn(cfg); led = led or Ledger(); notes = []
    picker = picker or Picker(cfg, led, now.date(), random.Random())
    made = []
    for off in range(0, (days if days is not None else cfg["days_ahead"]) + 1):
        d = now.date() + dt.timedelta(days=off)
        if Q.load_day(str(d)) is not None:
            continue
        picker.today = d; led_today = d
        posts = generate_day(cfg, led, picker, d, now, render, notes)
        if posts:
            Q.save_day(str(d), posts); made.append((str(d), len(posts)))
    notes += picker.notes
    led.prune(now.date()); led.save()
    Q.write_index(sorted(set(notes)), now.isoformat())
    return made, notes
