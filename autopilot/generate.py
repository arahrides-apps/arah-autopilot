"""Builds a day of posts: picks wording and photos, renders images, writes the queue."""
import re, random, datetime as dt, logging, shutil
from pathlib import Path
from . import templates as T, queue as Q
from .config import ROOT, load_yaml, now as now_fn, tz
from .ledger import Ledger
from .photos import Picker, Photo, rule_for
from .render import render_all
from . import story
from .ledger import dhash
import types
from PIL import Image

log = logging.getLogger("generate")
EMOJI = {"trip": "🗺️", "experience": "✨", "car_hero": "🚗", "place": "🌴", "qa": "🤔", "tip": "💡", "brand": "🇯🇲", "engage": "💬", "list": "✅", "chat": "💬", "carousel": "👉", "moment": "🇯🇲", "offer": "🎟️", "trust": "🎥", "versus": "🆚"}
TYPE_TAG = {"experience": "#VisitJamaica", "car_hero": "#RoadTrip", "place": "#VisitJamaica", "qa": "#QandA", "tip": "#TravelTips", "brand": "#Jamaica", "engage": "#JamaicaVibes",
            "list": "#TravelJamaica", "chat": "#Winston", "carousel": "#VisitJamaica", "moment": "#Jamaica", "offer": "#Jamaica", "trust": "#Jamaica", "versus": "#Jamaica"}
FALLBACK = {"car_hero": "brand", "place": "tip", "experience": "tip", "trip": "carousel"}
BGS = ["green", "dark", "gold", "cream"]

def _pick(rng, lst, n=1, avoid=()):
    pool = [t for t in lst if t.lower() not in [x.lower() for x in avoid]]
    rng.shuffle(pool)
    return pool[:n]

def hashtags(cfg, typ, extra=None, loc=None, rng=None):
    """5 tags: 2 'I want to rent' + 1 trip-planning + 1 place + 1 for the kind of post. Never the brand tag (only followers search it)."""
    h = cfg["hashtags"]; rng = rng or random.Random()
    tags = []
    tags += _pick(rng, h["rent"], 2)
    tags += _pick(rng, h["discover"], 1, tags)
    place = extra or (loc or {}).get("tag")
    if place:
        tags.append(place)
    tags += _pick(rng, h["by_type"].get(typ, h["discover"]), 1, tags)
    seen = []; [seen.append(t) for t in tags if t.lower() not in [s.lower() for s in seen]]
    for t in _pick(rng, h["rent"] + h["discover"], 5, seen):        # top up if a tag repeated
        if len(seen) >= min(h["max_total"], 5):
            break
        seen.append(t)
    return " ".join(seen[: min(h["max_total"], 5)])

ENGAGE_LINES = ["Save this for your trip 🔖 and send it to who you're travelling with.",
                "Planning Jamaica? Save this post 🔖 and share it with your travel partner.",
                "Tap the bookmark 🔖 so you can find this when you plan your trip. Tag who's coming with you.",
                "Send this to someone who needs a car in Jamaica 🚗 and save it for later 🔖."]

def caption(cfg, typ, text, extra_tag=None, cta=None, credit=None, loc=None, rng=None):
    b = cfg["brand"]
    if cfg.get("all_carousels", True) and rng is not None:
        text = f"{text}\n\n{rng.choice(ENGAGE_LINES)}"
    if credit:
        text = f"{text}\n\n📷 {credit}"
    cta = cta or f"Book: {b['site']}\nWhatsApp Winston: https://{b['wa_link']}"
    kw = f"\n\n{loc['kw']}" if loc and loc.get("kw") else ""        # plain-words line: Instagram search reads the caption
    return f"{text}{kw}\n\n{cta}\n\n{hashtags(cfg, typ, extra_tag, loc, rng)}"

def credit_for(ph):
    """Photo credit line for the caption: stock sites and named photographers; our own Arah Rides photos need none."""
    if not ph or not ph.credit or ph.credit == "Arah Rides" or (ph.source == "wikimedia" and "by" not in ph.credit.lower().split("(")[-1].split()[:2]):
        return None
    return ph.credit

def tidy(*parts):
    return " ".join(p.strip() for p in parts if p and p.strip())

class DayBuilder:
    def __init__(self, cfg, led, picker, date, rng, moments):
        self.cfg, self.led, self.pk, self.date, self.rng = cfg, led, picker, date, rng
        self.bank = expand_bank(load_yaml("bank.yaml")); self.moments = moments; self.notes = []
        self.today = date; self.led_loc = []; self.used_follow = set()

    def cooldown(self, kind, n):
        """Days before wording repeats: the configured days, but never more than the pool can supply at today's posting rate."""
        want = {"hero": "car_hero", "hero_big": "car_hero"}.get(kind, kind)
        per_day = 0.0
        for slot in self.cfg["pattern"]:
            opts = str(slot).split("|")
            per_day += sum(1 for o in opts if o == want) / len(opts)
        if per_day <= 0:
            return self.cfg["copy_cooldown_days"]
        return max(1, min(self.cfg["copy_cooldown_days"], int(n / per_day)))

    def pick(self, kind):
        lst = self.bank[kind]
        i, cycled = self.led.copy_pick(kind, len(lst), self.today, self.rng, self.cooldown(kind, len(lst)))
        if cycled:
            n = f"Wording for '{kind}' is running low: older posts are being repeated. Ask Claude to add more to content/bank.yaml."
            if n not in self.notes:
                self.notes.append(n)
        self.led.copy_record(kind, i, self.today)
        return lst[i]

    def where(self, place=None):
        """The place tagged on a post: the place it shows (Negril, YS Falls...) if it is a known one, else rotate through the pickup spots."""
        L = self.cfg["locations"]
        key = None
        if place:
            pl = place.lower()
            for k, v in L.items():
                if isinstance(v, dict) and (pl in v["name"].lower() or k.replace("_", " ") in pl):
                    key = k; break
            if not key:
                return {"name": place + ", Jamaica", "id": "", "tag": "#" + re.sub(r"\W", "", place), "kw": f"Car rental for {place}, Jamaica"}
        if not key:
            rot = L["default_rotation"]
            key = rot[(self.date.toordinal() + len(self.led_loc)) % len(rot)]
            self.led_loc.append(key)
        return {**L[key], "key": key}

    def cap(self, post, typ, text, extra_tag=None, cta=None, credit=None, place=None):
        loc = self.where(place)
        tag_loc = loc
        if not loc.get("id"):                 # Instagram only accepts a location with a real ID: use the nearest default spot that has one
            L = self.cfg["locations"]; have = [k for k in L["default_rotation"] if L[k].get("id")]
            if have:
                tag_loc = L[have[(self.date.toordinal() + len(self.led_loc)) % len(have)]]
        post["location"] = {"name": tag_loc["name"], "id": tag_loc.get("id", "")}
        return caption(self.cfg, typ, text, extra_tag, cta, credit, loc, self.rng)

    def photo_flags(self, post, ph):
        post["photo"] = {"id": ph.id, "name": ph.name, "source": ph.source, "credit": ph.credit}
        post["flags"] += ph.flags
        self.led.record(ph.keys(), ph.hash, self.today, ph.source, ph.series)

    # ---- each builder returns (post_fields, [(html,height)])
    def car_hero(self, post):
        ph = e = None
        if self.date.toordinal() % 3 == 0 and self.bank.get("hero_big"):      # every third day: a 7, 12 or 15 seater, if one is in the library
            ph = self.pk.car(tag="big")
            if ph:
                e = self.pick("hero_big")
        if not ph and self.pk.web and self.rng.random() < self.cfg["photos"].get("stock_car_share", 0.25):
            ph = self.pk.car_stock(self.cfg["photos"].get("fleet_models", []))      # a clean stock photo of one of our models
            if ph:
                e = self.pick("hero")
        if not ph:
            for _ in range(8):                      # the picture must fit the words: "drive" copy never gets a beach photo
                e = self.pick("hero")
                ph = self.pk.car(ok=rule_for(" ".join([e["kicker"], e["h1"], e["h2"], e["sub"]])))
                if ph:
                    break
            if not ph:
                ph = self.pk.car()
                if not ph:
                    return None
                e = {"kicker": "SEE BEFORE YOU BOOK", "h1": "Real car.", "h2": "Real photos.", "sub": "Choose the car you want to drive at arahrides.com."}
        self.photo_flags(post, ph)
        self.last = {"kind": "car_hero", "e": e, "big": "BIG" in e["kicker"] or "SEATER" in e["kicker"] or "GROUP" in e["kicker"], "credit": credit_for(ph)}
        pos = "50% 50%"
        if ph.portrait:
            html = T.hero(ph.path, e["kicker"], e["h1"], e["h2"], e["sub"], pos, at=self.rng.choice("bt"))
        else:
            html = T.split(ph.path, e["kicker"], tidy(e["h1"], e["h2"]), e["sub"], pos, self.rng.choice(["green", "cream"]))
        post["copy_text"] = tidy(e["h1"], e["h2"]) + " " + EMOJI["car_hero"] + "\n\n" + e["sub"]
        post["alt"] = "A rental car in Jamaica. " + tidy(e["h1"], e["h2"])
        post["caption"] = self.cap(post, "car_hero", post["copy_text"], credit=credit_for(ph))
        return [(html, 1350)]

    def place(self, post, kind="place"):
        for attempt in range(6):                      # a story needs a photo that really shows the place, so try other places first
            e = self.pick(kind)
            ph = self.pk.scene(e["query"], e["place"], ok=rule_for(" ".join([e.get("place", ""), e.get("h1", ""), e.get("h2", ""), e.get("sub", "")])), words=e.get("also"))
            if not ph:
                return None
            t_ = ph.text.lower()
            if e["place"].lower() in t_ or any(w.lower() in t_ for w in e.get("also", [])) or attempt == 5:
                break
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
        post["alt"] = (("Scenery in " + e["place"] + ", Jamaica") if kind == "place" else "Jamaica: " + e["k"].title()) if ok else "Scenery in Jamaica"
        post["caption"] = self.cap(post, kind, post["copy_text"], None, credit=credit_for(ph), place=e["place"] if ok else None)
        self.last = {"kind": kind, "e": e, "ok": ok, "credit": credit_for(ph)}
        return [(html, 1350)]

    def simple(self, post, kind):
        e = self.pick(kind)
        self.last = {"kind": kind, "e": e}
        if kind == "qa":
            html = T.big("ASK ARAH", e["q"], "Swipe for the answer.", self.rng.choice(["cream", "green", "dark"])); txt = f"{e['q']} {EMOJI['qa']}\n\n{e['a']}\n\nQuestions? Ask Winston on WhatsApp, any time."
            alt = f"Question and answer graphic: {e['q']}"
        elif kind == "tip":
            html = T.big(e["k"], e["h"], "Swipe for the full tip.", self.rng.choice(["cream", "green", "dark"])); txt = f"{e['k'].title()}: {e['h']} {EMOJI['tip']}\n\n{e['b']}"
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
        elif kind == "versus":
            html = T.versus(e["k"], e["h"], e["them"], e["us"]); txt = f"{e['h']} {EMOJI['brand']}\n\nOthers: " + "; ".join(e["them"]) + "\nArah Rides: " + "; ".join(e["us"])
            alt = f"Comparison graphic: {e['h']}"
        elif kind == "trust":
            link = self.cfg["offers"]["smile_jamaica"]["url"]
            html = T.big(e["k"], e["h"], e["b"], "dark", cta="Watch: Smile Jamaica interview"); txt = f"{e['h']} {EMOJI['trust']}\n\n{e['b']}"
            alt = f"Arah Rides on Smile Jamaica: {e['h']}"
            post["copy_text"] = txt; post["alt"] = alt
            post["caption"] = self.cap(post, kind, txt, cta=f"Watch the interview: {link}\nBook: {self.cfg['brand']['site']}")
            return [(html, 1350)]
        elif kind == "chat":
            html = T.chat(e["h"], e["u"], e["b"]); txt = f"{e['h']} {EMOJI['chat']}\n\nWinston is your 24/7 WhatsApp assistant. Quote, book and pay by Stripe. No app."
            alt = f"WhatsApp chat with Winston: {e['u']} / {e['b']}"
        post["copy_text"] = txt; post["alt"] = alt
        post["caption"] = self.cap(post, kind, txt, cta=None)
        return [(html, 1350)]

    def carousel(self, post):
        e = self.pick("carousel"); n = len(e["slides"]) + 1
        q = (e.get("query") or "")
        place = re.sub(r"\bjamaica\b", "", q, flags=re.I).strip().lower()
        if place in ("", "road", "beach", "countryside road", "sunset", "airport", "family beach", "food jerk", "road trip", "airport sunset"):
            place = None
        ph = self.pk.scene(q, place, ok=rule_for(q + " " + e["title"] + " " + e["k"]), strict=True) if q else None
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
        post["caption"] = self.cap(post, "carousel", post["copy_text"], credit=credit_for(ph))
        return pages

    def moment(self, post, m, days_left):
        b = m["b"]; self.last = {"kind": "moment", "e": m}
        kicker = m["k"] + (f" · {days_left} DAYS TO GO" if days_left > 0 else "")
        html = T.event(kicker, m["h"], b, m.get("badge", "")) if m.get("badge") else T.big(kicker, m["h"], b, "gold" if days_left == 0 else "green")
        post["copy_text"] = f"{m['h']} {EMOJI['moment']}\n\n{b}"
        post["alt"] = f"Seasonal graphic: {m['h']}"
        post["caption"] = self.cap(post, "moment", post["copy_text"])
        return [(html, 1350)]

    def offer(self, post, name, o):
        e = self.pick("offer"); self.last_offer = e
        self.vip_used = []
        vp = self.vip_photo()
        html = T.ticket(e["k"], e["h"], e["b"], buy=bool(e.get("buy")), photo=vp.path if vp else None)
        if vp:
            self.vip_used.append(vp)
            post["flags"].append("Lounge photos are from VIP Attractions (our lounge partner). Make sure they are happy for us to use them.")
        link = o.get("buy_url", "")
        post["copy_text"] = f"{e['h']} {EMOJI['offer']}\n\n{e['b']}"
        post["alt"] = "Offer graphic: " + e["h"]
        cta = None
        if e.get("buy") and link:
            cta = f"Buy a lounge pass without renting: {link}\nOr book 7+ days: {self.cfg['brand']['site']}\nWhatsApp Winston: https://{self.cfg['brand']['wa_link']}"
        post["caption"] = self.cap(post, "offer", post["copy_text"], cta=cta, credit="Lounge photos: VIP Attractions (Club Mobay and Club Kingston)" if vp else None)
        return [(html, 1350)]

    def vip_photo(self):
        """A photo of the partner lounges from content/vip/ (you add them). Same 3-month no-reuse rule as every other photo."""
        d = ROOT / "content" / "vip"
        files = sorted(p for p in d.glob("*") if p.suffix.lower() in (".jpg", ".jpeg", ".png")) if d.exists() else []
        self.rng.shuffle(files)
        for f in files:
            keys = ["vip:" + f.name, "name:vip-" + f.stem]
            if f.name in getattr(self, "_vip_today", set()):
                continue
            try:
                im = Image.open(f)
                if min(im.size) < 560:
                    continue
                hv = dhash(f)
            except Exception:
                continue
            if self.led.blocked(keys, hv, self.today, self.cfg):
                continue
            self.led.record(keys, hv, self.today, "vip", "")
            self._vip_today = getattr(self, "_vip_today", set()) | {f.name}
            return types.SimpleNamespace(path=str(f), name=f.name)
        return None

    # ---- every feed post is a story carousel (see story.py): one topic, then a reason to book
    def extra_photo(self, post, words, ok=None):
        """A second photo of the same place from our labelled library (never a web photo), recorded so it is not reused for 3 months."""
        ph = self.pk._own("scenery", None, ok, about=words)
        if ph:
            self.led.record(ph.keys(), ph.hash, self.today, ph.source, ph.series)
            post.setdefault("photos_extra", []).append({"id": ph.id, "name": ph.name})
        return ph

    def trip(self, post):
        """A day plan: three real stops in one area, then how to get there and book."""
        R = story.stories()["regions"]; names = list(R)
        i, _c = self.led.copy_pick("trip", len(names), self.today, self.rng, 3)
        self.led.copy_record("trip", i, self.today)
        reg = R[names[i]]; P = story.stories()["places"]
        stops = [k for k in reg["stops"] if k in P]
        self.rng.shuffle(stops); stops = stops[:3]
        ph = None
        for k in stops:                                   # cover photo: one of the stops, from our own labelled photos, else a checked web photo
            ph = self.pk.scene(story.nice(k) + " Jamaica", story.nice(k), strict=True)
            if ph:
                stops.remove(k); stops.insert(0, k); break
        if ph:
            self.photo_flags(post, ph)
            cover = T.ccover(ph.path, "A DAY PLAN", reg["hook"], reg["sub"])
        else:
            cover = T.ccover_plain("A DAY PLAN", reg["hook"], reg["sub"])
        items = [(f"Stop {n + 1}: {story.nice(k)}", P[k]["do"]) for n, k in enumerate(stops)]
        photos = {}
        for n, k in enumerate(stops[1:], start=1):
            x = self.extra_photo(post, story.about_words(k))
            if x:
                photos[n] = x
        c = ("Getting there.", reg["pickup"] + " Choose the car you want to drive at arahrides.com.")
        pages = story._slides(self, post, cover, items, c, photos)
        post["copy_text"] = f"{reg['hook']} {EMOJI['trip']}\n\n" + "\n".join(f"{n + 1}. {story.nice(k)}: {P[k]['do']}" for n, k in enumerate(stops)) + f"\n\n{reg['pickup']}"
        post["alt"] = f"Day plan: {reg['hook']}"
        post["caption"] = self.cap(post, "trip", post["copy_text"], credit=credit_for(ph), place=story.nice(stops[0]))
        post["story_done"] = True
        return pages

    def expand(self, post, typ, pages, offer=None):
        """Turn a one-picture post into a 5-slide story carousel."""
        total = 5
        if post.get("story_done"):
            out = pages
        elif typ == "offer" and offer:
            e, link = offer
            mid = [("How to get it.", "Book a rental for 7 days or more on arahrides.com."),
                   ("Who gets it.", "1 guest receives a Club Mobay or Club Kingston departure lounge pass. Cannot be combined with other promo codes or discounts. Conditions apply.")]
            mid.insert(1, ("Inside the lounge.", "Free Wi-Fi. Comfortable seating. Food and drink. Private restrooms. Fast track."))
            if e.get("buy"):
                mid[0] = ("Not renting?", "You can buy a departure lounge pass on its own. Details at arahrides.com.")
            slides = mid + [self.rng.choice(story.CLOSE_GENERAL)]
            out = list(pages)
            for i, (h, b) in enumerate(slides):
                ph = self.vip_photo() if i in (0, 2) else None       # lounge photo behind slides 2 and 4 when we have them
                if ph:
                    out.append((T.photoslide(ph.path, len(pages) + i + 1, total, h, b), 1350))
                else:
                    out.append((T.slide(len(pages) + i + 1, total, h, b, alt=bool(i % 2), cta=(i == len(slides) - 1)), 1350))
        else:
            out = story.build(self, post, typ, pages)
        out[0] = (T.swipe(out[0][0]), out[0][1])
        post["alt"] = (post.get("alt") or "") + " (carousel: swipe for more)"
        return out

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
        if mom and typ0 == "tip" and not used_mom:
            typ, used_mom = "moment", True
        elif offer and typ0 in ("brand", "versus") and not used_offer:
            typ, used_offer = "offer", True
        post = {"id": f"{date}_{hhmm.replace(':', '')}_{typ}", "date": str(date), "slot": at.isoformat(), "type": typ, "flags": [], "images": []}
        pages = None; t = typ
        while pages is None:
            if t == "car_hero": pages = b.car_hero(post)
            elif t == "place": pages = b.place(post)
            elif t == "experience": pages = b.place(post, "experience")
            elif t == "carousel": pages = b.carousel(post)
            elif t == "trip": pages = b.trip(post)
            elif t == "moment": pages = b.moment(post, mom, left)
            elif t == "offer": pages = b.offer(post, *offer)
            else: pages = b.simple(post, t)
            if pages is None:
                nt = FALLBACK.get(t)
                b.notes.append(f"No fresh photo for a {t} post on {date}: made a {nt} post instead.")
                t = nt; post["type"] = nt; post["id"] = f"{date}_{hhmm.replace(':', '')}_{nt}"
        if cfg.get("all_carousels", True) and post["type"] != "carousel" and (len(pages) == 1 or post.get("story_done")):
            ol = None
            if post["type"] == "offer":
                ol = (b.last_offer, "")
            pages = b.expand(post, post["type"], pages, ol)
        for i, (html_, h) in enumerate(pages):
            rel = f"media/{date}/{post['id']}_{i + 1}.jpg"
            post["images"].append(rel)
            jobs.append((html_, h, Q.DOCS / rel))
        if len(post["caption"]) > 2200 or post["caption"].count("#") > 5:
            raise ValueError("caption rules broken for " + post["id"])
        post.pop("story_done", None)
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
