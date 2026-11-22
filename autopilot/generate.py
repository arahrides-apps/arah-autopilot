"""Builds a day of posts: picks wording and photos, renders images, writes the queue."""
import re, random, datetime as dt, logging, shutil
from pathlib import Path
from . import templates as T, queue as Q
from .config import ROOT, load_yaml, now as now_fn, tz
from .ledger import Ledger
from .photos import Picker, Photo, rule_for
from .render import render_all
from . import story
from . import promo as promo_mod
from . import themes as TH
from .ledger import dhash
import types
from PIL import Image

log = logging.getLogger("generate")
EMOJI = {"review": "⭐", "trip": "🗺️", "experience": "✨", "car_hero": "🚗", "place": "🌴", "qa": "🤔", "tip": "💡", "brand": "🇯🇲", "engage": "💬", "list": "✅", "chat": "💬", "carousel": "👉", "moment": "🇯🇲", "offer": "🎟️", "trust": "🎥", "versus": "🆚", "journey": "🧳", "spotlight": "📍", "deal": "🚗", "deposits": "🔑"}
TYPE_TAG = {"experience": "#VisitJamaica", "car_hero": "#RoadTrip", "place": "#VisitJamaica", "qa": "#QandA", "tip": "#TravelTips", "brand": "#Jamaica", "engage": "#JamaicaVibes",
            "list": "#TravelJamaica", "chat": "#Winston", "carousel": "#VisitJamaica", "moment": "#Jamaica", "offer": "#Jamaica", "trust": "#Jamaica", "versus": "#Jamaica", "journey": "#JamaicaTravel", "spotlight": "#VisitJamaica", "deal": "#JamaicaCarRental", "deposits": "#JamaicaCarRental"}
FALLBACK = {"deal": "car_hero", "deposits": "carousel", "journey": "place", "spotlight": "place", "review": "trust", "car_hero": "brand", "place": "tip", "experience": "tip", "trip": "carousel"}
BGS = ["green", "dark", "gold", "cream"]

def _pick(rng, lst, n=1, avoid=()):
    pool = [t for t in lst if t.lower() not in [x.lower() for x in avoid]]
    rng.shuffle(pool)
    return pool[:n]

def hashtags(cfg, typ, extra=None, loc=None, rng=None):
    """5 tags (the most Instagram allows): the place's own tag, a tag for its region, 1 'I want to rent' tag, 1 brand/core tag,
    and 1 for the kind of post. Tags rotate within each group so the account never repeats the same set."""
    h = cfg["hashtags"]; rng = rng or random.Random(); loc = loc or {}
    tags = []
    pk = loc.get("pkey"); reg = loc.get("region")
    if pk and h.get("place_tags", {}).get(pk):
        tags.append(h["place_tags"][pk])
    tags += _pick(rng, h.get("region", {}).get(reg, []), 2 if len(tags) == 0 else 1, tags)
    if extra:
        tags.append(extra)
    elif loc.get("tag") and loc["tag"].lower() not in [x.lower() for x in tags]:
        tags.append(loc["tag"])
    tags += _pick(rng, h["rent"], 1, tags)
    tags += _pick(rng, h.get("core", []), 1, tags)
    tags += _pick(rng, h["by_type"].get(typ, h["discover"]), 1, tags)
    seen = []; [seen.append(x) for x in tags if x.lower() not in [s.lower() for s in seen]]
    for x in _pick(rng, h["discover"] + h["rent"], 5, seen):        # top up if a group was empty or a tag repeated
        if len(seen) >= min(h["max_total"], 5):
            break
        seen.append(x)
    return " ".join(seen[: min(h["max_total"], 5)])

ENGAGE_LINES = ["Which stop would you hit first? Tell us below 👇 Then save this 🔖 and send it to who you're bringing to Jamaica.",
                "Planning Jamaica? Save this post 🔖 and send it to your travel partner. Where is your first stop? 👇",
                "Tap the bookmark 🔖 so you can find this when you plan your trip. Tag who's coming with you and tell us your pick 👇",
                "Send this to someone who needs a car in Jamaica 🚗 and save it for later 🔖. What would you add to the list? 👇"]

def caption(cfg, typ, text, extra_tag=None, cta=None, credit=None, loc=None, rng=None):
    b = cfg["brand"]
    if cfg.get("all_carousels", True) and rng is not None:
        text = f"{text}\n\n{rng.choice(ENGAGE_LINES)}"
    if credit:
        text = f"{text}\n\n📷 {credit}"
    cta = cta or (f"Book in minutes, your way:\n💻 Online: {b['site']}\n💬 WhatsApp Winston, 24/7: https://{b['wa_link']} (quote, book and pay in one chat)")
    cta += "\n\n📍 Car rental in Jamaica · Airport pickup at Montego Bay (MBJ), Kingston (KIN) and Ocho Rios"          # the words people type into Instagram search
    cta += "\n\nAvailability changes daily. Check availability and book your vehicle at www.arahrides.com or with Winston on WhatsApp."
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
        story._S = None
        if lounge_paused(cfg, date):                         # the lounge pass offer is paused (see offers.lounge_pass.pause_until in config.yaml)
            self.bank = strip_lounge(self.bank); story._S = strip_lounge(load_yaml("stories.yaml"))
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
                if isinstance(v, dict) and k != "default_rotation" and (pl in v["name"].lower() or k.replace("_", " ") in pl or any(m in pl for m in v.get("match", []))):
                    key = k; break
            if not key:
                return {"name": place + ", Jamaica", "id": "", "tag": "#" + re.sub(r"\W", "", place), "kw": f"Car rental for {place}, Jamaica"}
        if not key:
            rot = L["default_rotation"]
            key = rot[(self.date.toordinal() + len(self.led_loc)) % len(rot)]
            self.led_loc.append(key)
        return {**L[key], "key": key}

    def cap(self, post, typ, text, extra_tag=None, cta=None, credit=None, place=None):
        loc = dict(self.where(place))
        pkey, pst = story.find_place(place) if place else (None, None)
        if pkey:
            loc["pkey"], loc["region"] = pkey, pst.get("region")
        tag_loc = loc
        if not loc.get("id"):                 # Instagram only accepts a location with a real ID: use the nearest default spot that has one
            L = self.cfg["locations"]; have = [k for k in L["default_rotation"] if L[k].get("id")]
            if have:
                tag_loc = L[have[(self.date.toordinal() + len(self.led_loc)) % len(have)]]
        post["location"] = {"name": tag_loc["name"], "id": tag_loc.get("id", "")}
        pr = promo_mod.active(self.date)
        if pr and pr.get("caption_line", True) and pr["code"].lower() not in text.lower():       # the sale is on: every caption carries the code
            end = dt.date.fromisoformat(str(pr["end"])); left = (end - self.date).days
            when = "Last day!" if left <= 0 else ("Ends tomorrow." if left == 1 else f"Ends {end.strftime('%b')} {end.day}.")
            text = f"{text}\n\n🔥 {pr['name'].title()}: up to US${pr['amount']} off with code {pr['code']} at checkout. {when} {pr.get('terms', '')}".rstrip()
        return caption(self.cfg, typ, text, extra_tag, cta, credit, loc, self.rng)

    def cover_photo(self, post, text="", theme="road", place=None):
        """Every cover must be a real Jamaica photo that fits the post. Own labelled photos and checked web photos, from the most specific
        match to a general Jamaica topic; None only if the library and web are both empty."""
        ph = None
        if place or text:
            ph = self.pk.scene((text or place) + " Jamaica", place, strict=True)
        for th in (theme, "road", "food", "family", "couple", "group"):
            if ph: break
            try: ph = self.pk.theme_photo(th)
            except KeyError: ph = None
        if ph:
            self.photo_flags(post, ph)
        else:
            post["flags"].append("NO COVER PHOTO FOUND: add photos to the library, this cover is text only")
        return ph

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
        if not ph and self.pk.web and self.cfg["photos"].get("stock_composites", False) and self.rng.random() < self.cfg["photos"].get("stock_car_share", 0.25):
            ph = self.pk.car_stock(self.cfg["photos"].get("fleet_models", []))      # a clean stock photo of one of our models...
            if ph:
                comp, bg = self.pk.composite_car(ph)                                 # ...placed on a real Jamaica background
                if comp:
                    self.led.record(bg.keys(), bg.hash, self.today, bg.source, bg.series)
                    post.setdefault("photos_extra", []).append({"id": bg.id, "name": bg.name})
                    ph = comp; e = self.pick("hero")
                else:
                    ph = None
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
        ph = None
        for attempt in range(8):                      # a story needs a photo that really shows the place, so try other places first
            e = self.pick(kind)
            ph = self.pk.scene(e["query"], e["place"], ok=rule_for(" ".join([e.get("place", ""), e.get("h1", ""), e.get("h2", ""), e.get("sub", "")])), words=e.get("also"))
            if not ph:
                continue
            t_ = ph.text.lower()
            if e["place"].lower() in t_ or any(w.lower() in t_ for w in e.get("also", [])) or attempt == 7:
                break
        if ph is None:
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
        post["alt"] = (("Scenery in " + e["place"] + ", Jamaica") if kind == "place" else "Jamaica: " + e["k"].title()) if ok else "Scenery in Jamaica"
        post["caption"] = self.cap(post, kind, post["copy_text"], None, credit=credit_for(ph), place=e["place"] if ok else None)
        self.last = {"kind": kind, "e": e, "ok": ok, "credit": credit_for(ph), "ph": ph}
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
            return [(self.photo_cover(post, kind, e, html), 1350)]
        elif kind == "chat":
            html = T.chat(e["h"], e["u"], e["b"]); txt = f"{e['h']} {EMOJI['chat']}\n\nWinston is your 24/7 WhatsApp assistant. Quote, book and pay by Stripe. No app."
            alt = f"WhatsApp chat with Winston: {e['u']} / {e['b']}"
        post["copy_text"] = txt; post["alt"] = alt
        post["caption"] = self.cap(post, kind, txt, cta=None)
        return [(self.photo_cover(post, kind, e, html), 1350)]

    def photo_cover(self, post, kind, e, html):
        """Q&A, tips, lists, chats and brand posts open on a real Jamaica photo that matches the words, not a plain text card."""
        g = e.get
        k, h, sub = {"qa": ("ASK ARAH", g("q"), "Swipe for the answer."), "tip": (g("k"), g("h"), "Swipe for the full tip."),
                     "engage": ("YOUR TURN", g("h"), g("b")), "list": (g("k"), g("h"), "Swipe through."), "versus": (g("k"), g("h"), "Swipe to compare."),
                     "chat": ("ASK WINSTON", g("h"), f"\u201c{g('u')}\u201d")}.get(kind, (g("k"), g("h"), g("b")))
        words = " ".join(str(x) for x in (h, sub, g("a"), g("b"), " ".join(g("items") or [])) if x)
        ph = None
        for q in TH.slide_queries(words)[:3]:
            ph = self.pk.scene(q, None, words=[w for w in q.lower().split() if len(w) > 4 and w not in ("jamaica", "jamaican")][:2])
            if ph and not story._fits(post, ph, f"{h} {sub}"):          # the cover must show what the headline talks about
                ph = None
            if ph: break
        if not ph:
            ph = self.cover_photo(post, "", self.rng.choice(story.TYPE_THEMES.get(kind, ["road", "couple", "family", "group"])))
        else:
            self.photo_flags(post, ph)
        return T.ccover(ph.path, k or "ARAH RIDES", h or "", sub or "") if ph else html

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
            ph = self.cover_photo(post, e["title"], "road")
            cover = T.ccover(ph.path, e["k"], e["title"], e["sub"]) if ph else T.ccover_plain(e["k"], e["title"], e["sub"])
        pages = [(cover, 1350)]
        for i, (h, b) in enumerate(e["slides"]):
            last = i == len(e["slides"]) - 1
            sp = None
            if not last:                                   # a photo of the place or thing each slide names (Doctor's Cave Beach, Mayfield Falls...)
                pk_, _st = story.find_place(h)
                sp = self.pk.scene(story.nice(pk_) + " Jamaica", story.nice(pk_), strict=True) if pk_ else None
                sp = sp or story._matched(self, post, f"{h} {b}")
            sp = sp or (self.pk.theme_photo(self.rng.choice(["road", "couple", "family", "group"])) if last else None)
            pages.append(((T.photoslide(sp.path, i + 2, n, h, b, cta=last) if sp else T.slide(i + 2, n, h, b, alt=bool(i % 2), cta=last)), 1350))
        body = "\n".join(f"• {h}: {b}" for h, b in e["slides"])
        post["copy_text"] = f"{e['title']} {EMOJI['carousel']}\n\n{e['sub']}\n\n{body}"
        post["alt"] = f"Carousel: {e['title']}"
        post["caption"] = self.cap(post, "carousel", post["copy_text"], credit=credit_for(ph))
        return pages

    def moment(self, post, m, days_left):
        b = m["b"]; self.last = {"kind": "moment", "e": m}
        when = "HAPPENING NOW" if days_left < 0 else ("TODAY" if days_left == 0 else f"{days_left} DAYS TO GO" if days_left > 1 else "TOMORROW")
        kicker = m["k"] + (f" · {when}" if (days_left > 0 or m.get("event")) else "")
        html = T.event(kicker, m["h"], b, m.get("badge", "")) if m.get("badge") else T.big(kicker, m["h"], b, "gold" if days_left == 0 else "green")
        post["copy_text"] = f"{m['h']} {EMOJI['moment']}\n\n{b}"
        if m.get("event"):
            post["copy_text"] += f"\n\n📅 {m['badge'].title().replace('–', ' to ')}\n📍 {m['where']}\n\nRent a car and get there your way. Choose the car you want to drive at {self.cfg['brand']['site']}."
            post["event_id"] = m["k"]
        post["alt"] = f"Event graphic: {m['h']}" if m.get("event") else f"Seasonal graphic: {m['h']}"
        post["caption"] = self.cap(post, "moment", post["copy_text"], place=m.get("loc"))
        return [(html, 1350)]

    # ---- Fleet campaign (content/campaign_fleet.yaml): cars from the lowest price up, and the lowest security deposits ----
    # how each model is named in fleet photo files and labels (honda-fit-silver, mazda2-red, haval-black...)
    CAR_ALIASES = {"mazda demio": ["demio", "mazda2", "mazda 2"], "honda hr-v": ["hrv", "hr-v", "vezel"], "honda cr-v": ["crv", "cr-v"],
                   "gwm haval h6": ["haval"], "gwm haval gt": ["haval"], "mg zs": ["mg-", "mg zs", " mg "], "jetour t2": ["jetour"],
                   "toyota c-hr": ["c-hr", "chr"], "nissan x-trail": ["xtrail", "x-trail"], "foton view cs2 (15 seater)": ["foton"],
                   "subaru legacy b4": ["legacy"], "subaru g4": ["g4", "impreza g4"], "honda stepwgn": ["stepwgn"], "toyota hiace": ["hiace"]}
    CAR_NOT = {"toyota corolla": ["cross", "axio", "touring"], "toyota yaris": ["cross"], "toyota corolla axio": ["cross"], "toyota corolla touring": ["cross"], "toyota axio": [], "honda fit": ["outfit"]}

    def _car_words(self, model):
        m = model.lower()
        if m in self.CAR_ALIASES:
            return self.CAR_ALIASES[m]
        base = re.sub(r"^(toyota|honda|nissan|suzuki|mazda|kia|hyundai|subaru|bmw|volkswagen|gwm|mg)\s+", "", m)
        return [m, m.replace(" ", "-"), base.replace(" ", "-") if " " in base else base]

    def camp_car_photo(self, model, category=None, exterior=True):
        """A real fleet photo (photos/cars, photos/listings, Drive): this model first, then a car of the same body style. Never web stock photos.
        Returns (photo, similar): similar=True when it shows another model of the same body style."""
        ph = self.pk._own("car", None, None, about=self._car_words(model), about_not=self.CAR_NOT.get(model.lower()), exterior=exterior)
        if ph:
            return ph, False
        if category:
            cars = load_yaml("campaign_fleet.yaml")["cars"]
            order = [c["model"] for c in cars]; at = order.index(model) if model in order else len(order)
            same = [c["model"] for c in cars if c["category"] == category and c["model"] != model]
            # borrow from models already featured first, so a model coming up soon keeps its own photos
            ph = None
            # never borrow a car of another body style whose name contains a same-style name (Corolla Cross is an SUV, Corolla is a sedan)
            others = [w for c in cars if c["category"] != category for w in self._car_words(c["model"])]
            for group in ([m for m in same if order.index(m) < at], [m for m in same if order.index(m) > at]):
                words = [w for mm in group for w in self._car_words(mm)]
                bad = [o for o in others if any(w in o for w in words)] + [x for mm in group for x in self.CAR_NOT.get(mm.lower(), [])]
                ph = self.pk._own("car", None, None, about=words, about_not=bad or None, exterior=exterior) if words else None
                if ph:
                    break
            if ph:
                ph.flags.append(f"Similar {category.lower()} shown for the {model} (same body style, from our fleet photos)")
                return ph, True
        return None, False

    def deal(self, post, k):
        """One car per post, in order from the cheapest daily rate up (then the lowest deposit). A car with no photo is passed to the next one."""
        C = load_yaml("campaign_fleet.yaml"); cars = C["cars"]; c0 = C["campaign"]
        day = (self.date - dt.date.fromisoformat(str(c0["start"]))).days
        n = len(c0.get("deal_slots", [0, 5])); start = (day * n + k) % len(cars)
        done = self.__dict__.setdefault("_deal_done", set())
        for j in range(len(cars)):
            e = cars[(start + j) % len(cars)]
            if e["model"] in done:
                continue
            ph, stock = self.camp_car_photo(e["model"], e["category"])
            if not ph:
                self.notes.append(f"No fleet photo of a {e['model']} or another {e['category'].lower()} left for the {self.date} deal post: run 'Fetch fleet' or add car photos to Drive. Showed the next car instead.")
                continue
            done.add(e["model"]); self.photo_flags(post, ph)
            pr = promo_mod.active(self.date)
            code = f" Code {pr['code']}: up to US${pr['amount']} off." if pr else ""
            tail = ("\n\nDecember dates are filling fast. Lock in your car now." +
                    "\nBase daily rate; holiday and date-specific prices can differ. Your quote shows the full price before you pay.")
            if not stock:                                   # we have a photo of this very model: the post is about this car
                self.last = {"kind": "deal", "e": dict(e, stock=False)}
                post["copy_text"] = (f"{e['model']} from US${e['price']} a day {EMOJI['deal']}\n\nSecurity deposit: US${e['deposit_at_price']}." +
                                     (f" Some units have a deposit of just US${e['low_deposit']}." if e["low_deposit"] < e["deposit_at_price"] else "") +
                                     f"\n{e['category']}. Choose the car you want to drive at arahrides.com, or ask Winston on WhatsApp." + tail)
                post["alt"] = f"{e['model']} rental car in Jamaica"
                post["caption"] = self.cap(post, "deal", post["copy_text"])
                return [(T.ccover(ph.path, f"FROM US${e['price']}/DAY", e["model"], f"Deposit US${e['deposit_at_price']}." + code), 1350)]
            # no photo of this model: the post is about the body style (the photo shows one of our cars of that style), never a wrong model name on a photo
            group = [c for c in cars if c["category"] == e["category"]]
            names = [e["model"]] + [c["model"] for c in sorted(group, key=lambda c: c["price"]) if c["model"] != e["model"]][:2]
            style = {"Hatchback": "Hatchbacks", "Sedan": "Sedans", "SUV": "SUVs", "7 Seater": "7-seaters", "Luxury Vehicles": "Luxury cars", "Mini Bus": "Minibuses"}.get(e["category"], e["category"])
            lo_dep = min(c["low_deposit"] for c in group)
            self.last = {"kind": "deal", "e": dict(e, stock=True, style=style, names=names)}
            post["copy_text"] = (f"{style} from US${e['price']} a day {EMOJI['deal']}\n\n" + ", ".join(names) + " and more." +
                                 f"\nDeposits from US${lo_dep}. Choose the car you want to drive at arahrides.com, or ask Winston on WhatsApp." + tail)
            post["alt"] = f"{style} for rent in Jamaica"
            post["caption"] = self.cap(post, "deal", post["copy_text"])
            return [(T.ccover(ph.path, f"FROM US${e['price']}/DAY", style, ", ".join(names[:2]) + " and more." + code), 1350)]
        return None

    def deposits(self, post):
        """Low security deposits: a short list of models, lowest deposit first, rotating through the list day by day."""
        C = load_yaml("campaign_fleet.yaml"); c0 = C["campaign"]
        low = sorted([c for c in C["cars"] if c["low_deposit"] <= c0.get("deposit_max", 150)], key=lambda c: (c["low_deposit"], c["price_at_low_deposit"]))
        if not low:
            return None
        day = (self.date - dt.date.fromisoformat(str(c0["start"]))).days // 2
        pick = [low[(day * 4 + i) % len(low)] for i in range(min(4, len(low)))]
        shots = []
        for c in pick:
            ph, stock = self.camp_car_photo(c["model"], c["category"])
            shots.append((c, None if stock else ph, stock, ph))          # a slide that names a model only shows that model
        cov = next((x for x in shots if x[1]), None) or next(((c, p4, st) for c, _p, st, p4 in shots if p4), None)
        shots = [x[:3] for x in shots]
        if not cov:
            return None
        self.photo_flags(post, cov[1])
        self.last = {"kind": "deposits", "e": {"cars": shots}}
        lo = min(c["low_deposit"] for c in pick)
        post["copy_text"] = (f"Low deposit cars in Jamaica {EMOJI['deposits']}\n\n" + "\n".join(f"• {c['model']}: deposit US${c['low_deposit']}, from US${c['price_at_low_deposit']} a day" for c in pick) +
                             "\n\nDecember dates are filling fast. Lock in your car now.\nThe deposit is released after you return the car, under the rental terms. Base daily rates; holiday dates can differ." +
                             ("\nVehicles shown may differ from the one you rent." if any(x[2] for x in shots) else ""))
        post["alt"] = "Low security deposit rental cars in Jamaica"
        post["caption"] = self.cap(post, "deposits", post["copy_text"])
        pr = promo_mod.active(self.date)
        return [(T.ccover(cov[1].path, "LOW DEPOSIT CARS", f"Deposits from US${lo}.", (f"Plus code {pr['code']}: up to US${pr['amount']} off. " if pr else "") + "Swipe for the cars."), 1350)]

    SPOT_HEAD = {"beach": "{n}. Your next swim.", "waterfall": "{n}. Worth the drive.", "river": "{n}. Cool water, slow day.", "cave": "Go underground at {n}.",
                 "mountain": "{n}. The view is the reward.", "heritage": "{n}. Jamaica's story, up close.", "garden": "Slow down at {n}.", "food": "{n}. Come hungry.",
                 "lighthouse": "{n}. End-of-the-road views.", "adventure": "{n}. Make a day of it."}

    def spotlight(self, post):
        """One named Jamaica attraction from content/attractions.yaml, shown with a real photo of that place. A place with no photo is passed over."""
        A = load_yaml("attractions.yaml")["attractions"]
        want_food = self.date.toordinal() % 3 == 0          # every third day the place spotlight is a food stop (jerk, pepper shrimp, fried fish...)
        for _ in range(4):
            for _t in range(40):
                i, _c = self.led.copy_pick("poi", len(A), self.today, self.rng, 365)
                if not want_food or A[i]["cat"] == "food":
                    break
            e = A[i]; n = e["name"]
            words = [w for w in re.findall(r"[a-z']+", n.lower()) if len(w) > 3 and w not in ("beach", "river", "falls", "great", "house", "park", "gardens", "botanical", "historic", "district")][:2] or [n.lower()]
            ph = self.pk.scene(f"{n} Jamaica", n, strict=True, words=words)
            if not ph and e.get("photo"):                # food stop: a real photo of the dish it is known for
                ph = self.pk.scene(e["photo"], None, words=[w for w in e["photo"].lower().split() if len(w) > 4 and w not in ("jamaica", "jamaican")][:2])
            self.led.copy_record("poi", i, self.today)              # tried today: a place without a photo is not retried for a year
            if not ph:
                continue
            self.photo_flags(post, ph)
            head = self.SPOT_HEAD.get(e["cat"], "{n}. Go see it.").format(n=n)
            kick = ("HIDDEN GEM" if e.get("tier") == "gem" else "MUST SEE") + " · " + e["parish"].upper()
            self.last = {"kind": "spotlight", "e": dict(e, head=head, kick=kick)}
            loc = n if self.where(n).get("id") else e["airport"].split(" or ")[0]
            post["copy_text"] = f"{head} {EMOJI['spotlight']}\n\n{n}, {e['parish']}." + (f" {e['about']}." if e.get("about") else "") + (f"\nWhat to order: {e['eat']}." if e.get("eat") else "") + f"\nPick up your car at {e['airport']} and drive there on your own time."
            post["alt"] = f"{n}, {e['parish']}, Jamaica"
            post["caption"] = self.cap(post, "spotlight", post["copy_text"], place=loc)
            post["story_done"] = False
            return [(T.ccover(ph.path, kick, head, "Places to see with your Arah rental. Swipe →"), 1350)]
        return None

    def journey(self, post):
        """A short human story (fly down, book a car, visit grandma...) told as a swipeable post with a real Jamaica photo on every slide."""
        js = load_yaml("journeys.yaml")["journeys"]
        xmas = (self.date.month == 12) or (self.date.month == 11 and self.date.day >= 15)
        for _ in range(12):                       # Christmas stories only from mid-November to December
            i, _c = self.led.copy_pick("journey", len(js), self.today, self.rng, 20)
            if (js[i].get("theme") == "xmas" or "CHRISTMAS" in js[i]["k"]) == xmas or not (js[i].get("theme") == "xmas" or "CHRISTMAS" in js[i]["k"]):
                if not xmas and (js[i].get("theme") == "xmas" or "CHRISTMAS" in js[i]["k"]):
                    continue
                break
        self.led.copy_record("journey", i, self.today)
        j = js[i]; self.last = {"kind": "journey", "e": j}
        post["copy_text"] = f"{j['h']} {EMOJI['journey']}\n\n" + "\n".join(f"{h} {t}" for h, t in j["beats"])
        post["alt"] = f"Story: {j['h']}"
        post["caption"] = self.cap(post, "journey", post["copy_text"], place=j.get("loc"))
        return [(T.big(j["k"], j["h"], "Swipe for the story.", "green"), 1350)]

    def offer(self, post, name, o):
        e = self.pick("offer"); self.last_offer = e
        self.vip_used = []
        vp = self.vip_photo()
        names = list(T.LOUNGE_DESIGNS)                       # five different looks; never the same one twice in a row
        last = self.led.data.get("lounge_design")
        names = [n for n in names if n != last] or names
        design = self.rng.choice(names); self.led.data["lounge_design"] = design; self.last_design = design
        html = T.LOUNGE_DESIGNS[design](e["k"], e["h"], e["b"], buy=bool(e.get("buy")), photo=vp.path if vp else None)
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

    def story_photo(self, post, key):
        """Another real photo of the same place for a slide: our own labelled photos first, then a strictly checked web photo."""
        ph = self.extra_photo(post, story.about_words(key))
        if ph or not self.pk.web:
            return ph
        ph = self.pk.scene(story.nice(key) + " Jamaica", story.nice(key), strict=True)
        if ph:
            self.led.record(ph.keys(), ph.hash, self.today, ph.source, ph.series)
            post.setdefault("flags", []).append("Slide photo from %s (licence-free): %s" % (ph.source, ph.credit or "no credit needed"))
            return ph
        ph = self.pk.drawn(story.nice(key))
        if ph:
            post.setdefault("flags", []).append(ph.flags[0])
        return ph

    def review(self, post):
        """Real renter reviews from arahrides.com, one per slide, on a cover with a real photo of the car; then how to book."""
        sets = story.load_yaml("reviews.yaml")["sets"]
        i, _c = self.led.copy_pick("review", len(sets), self.today, self.rng, 3)
        self.led.copy_record("review", i, self.today)
        s = sets[i]; Q_ = s["quotes"]
        ph = None
        if s.get("photo"):
            ph = self.pk._own("car", None, None, about=s["photo"].split("|"))
        if ph:
            self.photo_flags(post, ph)
        else:
            ph = self.cover_photo(post, "car rental road trip", "road")
        stars = min(q["stars"] for q in Q_)
        sub = "5-star reviews from real bookings on Arah Rides." if stars == 5 else "Real reviews from real bookings on Arah Rides."
        h2 = s["title"] if "Toyota" in s["title"] else "Renters tell it best."
        cover = (T.hero(ph.path, "WHAT RENTERS SAY", "Real reviews.", h2, sub, at="b") if ph else T.ccover_plain("WHAT RENTERS SAY", "Real reviews. " + h2, sub))
        items = [("★" * q["stars"] + " " + q["vehicle"], "“%s”  — %s" % (q["q"], q["name"])) for q in Q_]
        c = self.rng.choice(story.CLOSE_GENERAL)
        pages = story._slides(self, post, cover, items, ("Your turn.", "Choose the car you want to drive at arahrides.com. Say Hi to Winston on WhatsApp for your quote, then pay by Stripe."))
        text = (f"{s['seo']} {EMOJI['review']}\n\n" +
                "\n".join("“%s” — %s, %s" % (q["q"], q["name"], q["vehicle"]) for q in Q_) +
                "\n\nReviews left on arahrides.com by real renters. Rented with us before? Tell us how it went 👇")
        post["copy_text"] = text
        post["alt"] = f"Renter reviews of the {s['title']} on Arah Rides"
        post["caption"] = self.cap(post, "review", text, credit=None, place=None)
        post["story_done"] = True
        return pages

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
            ph = self.cover_photo(post, reg["hook"], "road")
            cover = T.ccover(ph.path, "A DAY PLAN", reg["hook"], reg["sub"]) if ph else T.ccover_plain("A DAY PLAN", reg["hook"], reg["sub"])
        items = [(f"Stop {n + 1}: {story.nice(k)}", P[k]["do"]) for n, k in enumerate(stops)]
        photos = {}
        for n, k in enumerate(stops[1:], start=1):
            x = self.story_photo(post, k)
            if x:
                photos[n] = x
        items.append(story.price_slide(self))
        c = ("Send this to who is coming with you.", reg["pickup"] + " Save it, then choose the car you want to drive at arahrides.com.")
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
            sets = [[("How to get it.", "Book a rental for 7 days or more on arahrides.com."), ("Inside the lounge.", "Free Wi-Fi. Comfortable seating. Food and drink. Private restrooms. Fast track."),
                     ("Who gets it.", "1 guest receives a Club Mobay or Club Kingston departure lounge pass. Cannot be combined with other promo codes or discounts. Conditions apply.")],
                    [("Step 1: pick your car.", "Choose the car you want to drive on arahrides.com."), ("Step 2: keep it 7 days.", "Rent for 7 days or more and the pass is added for 1 guest."),
                     ("Step 3: fly out relaxed.", "Club Mobay at Montego Bay or Club Kingston. Wi-Fi, seating, food and drink. Conditions apply.")],
                    [("A week of Jamaica.", "Beaches, waterfalls, jerk stops and mountain roads, on your schedule."), ("Then the lounge.", "Your last hour is calm: Wi-Fi, comfy seats, food and drink, fast track."),
                     ("The fine print.", "1 guest. Not combinable with other promo codes or discounts. Conditions apply.")],
                    [("Why rent 7+ days?", "You see more of the island and the lounge pass for 1 guest comes with it."), ("What you get.", "Club Mobay or Club Kingston. Free Wi-Fi, private restrooms, food and drink."),
                     ("Good to know.", "Not combinable with other promo codes or discounts. Conditions apply.")]]
            mid = list(sets[(self.today.toordinal() + self.rng.randrange(len(sets))) % len(sets)]) if hasattr(self, "today") else list(sets[0])
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

LOUNGE = re.compile(r"lounge|departure pass|club mobay|club kingston|vip attractions", re.I)

def lounge_paused(cfg, date):
    o = (cfg.get("offers") or {}).get("lounge_pass") or {}
    return (not o.get("enabled")) or str(date) < str(o.get("pause_until", "0000-00-00"))

def strip_lounge(x):
    """Takes every mention of the lounge pass out of the wording pools (used while the offer is paused). A pool that would end up empty is left alone."""
    hit = lambda v: bool(LOUNGE.search(str(v)))
    if isinstance(x, list):
        keep = [strip_lounge(i) for i in x if not hit(i)]
        return keep if keep else x
    if isinstance(x, dict):
        return {k: strip_lounge(v) for k, v in x.items() if not hit(k) and not (isinstance(v, str) and hit(v))}
    return x

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
        if m.get("event"):
            continue                                      # events have their own slots (upcoming_events)
        d = dt.date.fromisoformat(str(m["date"])); left = (d - date).days
        if 0 <= left <= m.get("lead_days", 0):
            if m.get("needs_offer"):
                o = cfg["offers"].get(m["needs_offer"], {})
                if not (o.get("enabled") and o.get("text")):
                    continue
                m = dict(m, b=o["text"])
            return m, left
    return None, 0

def upcoming_events(moments, date):
    """Events starting soon or happening now: [(event, days_until_start)], soonest first. Ongoing events show days_until_start < 0."""
    out = []
    for m in moments:
        if not m.get("event"):
            continue
        start = dt.date.fromisoformat(str(m["date"])); end = dt.date.fromisoformat(str(m.get("end", m["date"]))); left = (start - date).days
        if date <= end and left <= m.get("lead_days", 21):
            out.append((m, left))
    return sorted(out, key=lambda x: (max(x[1], 0), x[0]["date"]))

def generate_day(cfg, led, picker, date, now, render=True, notes=None, skip=()):
    rng = random.Random(f"{date}-{now.timestamp() // 60}")
    b = DayBuilder(cfg, led, picker, date, rng, load_yaml("moments.yaml"))
    mom, left = active_moment(cfg, b.moments, date)
    offer = next(((k, v) for k, v in cfg["offers"].items() if k == "lounge_pass" and v.get("enabled") and v.get("text") and not lounge_paused(cfg, date)), None)
    zone = tz(cfg); posts = []; jobs = []
    pattern = cfg["pattern"][: cfg["posts_per_day"]]
    used_mom = used_offer = False
    try:
        _cf = load_yaml("campaign_fleet.yaml"); camp = _cf["campaign"] if date >= dt.date.fromisoformat(str(_cf["campaign"]["start"])) and (not _cf["campaign"].get("end") or date <= dt.date.fromisoformat(str(_cf["campaign"]["end"]))) else None
    except Exception:
        camp = None
    deal_k = 0
    promo = promo_mod.active(date); pslots = (promo or {}).get('slots', [5]); is_promo = False
    events = upcoming_events(b.moments, date); ev_slots = cfg.get("event_slots", [8, 11]); cur = (mom, left)
    for idx, typ0 in enumerate(pattern):
        if "|" in typ0:
            opts = typ0.split("|"); typ0 = opts[(date.toordinal() + idx) % len(opts)]
        hhmm = cfg["slots"][idx]
        at = dt.datetime.combine(date, dt.time.fromisoformat(hhmm), zone)
        past = at <= now
        if hhmm in skip or (past and not (cfg.get("draft_past_slots_today", True) and date == now.date())):
            continue
        typ = typ0; cur = (mom, left); is_promo = False
        if camp and idx in camp.get("deal_slots", []):
            typ = "deal"; deal_k = camp["deal_slots"].index(idx)
        elif camp and idx == camp.get("deposit_slot") and date.toordinal() % 2 == 0:
            typ = "deposits"
        elif promo and idx in pslots:
            cur = (promo_mod.moment(promo, pslots.index(idx), date), 0); typ = "moment"; is_promo = True
        elif events and idx in ev_slots and date.weekday() in cfg.get("event_days", range(7)) and (ev_slots.index(idx) == 0 or len(events) > 1):
            k = ev_slots.index(idx); cur = events[(date.toordinal() + k) % len(events)]; typ = "moment"
        elif mom and typ0 == "tip" and not used_mom:
            typ, used_mom = "moment", True
        elif offer and typ0 in ("brand", "versus") and not used_offer:
            typ, used_offer = "offer", True
        post = {"id": f"{date}_{hhmm.replace(':', '')}_{typ}", "date": str(date), "slot": at.isoformat(), "type": typ, "flags": [], "images": []}
        if past:
            post["flags"].append(f"Its {hhmm} time has passed: approve it and it posts today, one late post every 30 minutes or so.")
        if is_promo: post["promo"] = promo["code"]
        if typ == "deal": post["_deal_k"] = deal_k
        b.pk.picked = []
        pages = None; t = typ
        while pages is None:
            if t == "car_hero": pages = b.car_hero(post)
            elif t == "place": pages = b.place(post)
            elif t == "experience": pages = b.place(post, "experience")
            elif t == "carousel": pages = b.carousel(post)
            elif t == "trip": pages = b.trip(post)
            elif t == "review": pages = b.review(post)
            elif t == "moment": pages = b.moment(post, *cur)
            elif t == "journey": pages = b.journey(post)
            elif t == "spotlight": pages = b.spotlight(post)
            elif t == "deal": pages = b.deal(post, post.get("_deal_k", 0))
            elif t == "deposits": pages = b.deposits(post)
            elif t == "offer": pages = b.offer(post, *offer)
            else: pages = b.simple(post, t)
            if pages is None:
                nt = FALLBACK.get(t)
                b.notes.append(f"No fresh photo for a {t} post on {date}: made a {nt} post instead.")
                t = nt; post["type"] = nt; post["id"] = f"{date}_{hhmm.replace(':', '')}_{nt}"
        if idx in cfg.get("single_slots", []) and len(pages) == 1 and date.toordinal() % 5 < cfg.get("single_days_per_5", 5):
            post["single"] = True                       # a deliberate single-picture post (about 20% of the day), not turned into a carousel
        elif cfg.get("all_carousels", True) and post["type"] != "carousel" and (len(pages) == 1 or post.get("story_done")):
            ol = None
            if post["type"] == "offer":
                ol = (b.last_offer, "")
            pages = b.expand(post, post["type"], pages, ol)
        post["raw"] = list(dict.fromkeys(str(x) for x in b.pk.picked))
        if not pages or '<img src="file:' not in pages[0][0]:
            if not cfg["photos"].get("allow_text_cover", False):        # every post opens on a real photo; no fresh photo = no post (never a text card cover)
                b.notes.append(f"Skipped the {hhmm} post on {date}: no fresh Jamaica photo for its cover. Add photos to Drive or check the Unsplash/Pexels/Pixabay keys.")
                continue
        nph = sum('<img src="file:' in h_ for h_, _ in pages)
        if nph < len(pages):
            post.setdefault("flags", []).append(f"{nph} of {len(pages)} slides have photos")
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
        from . import reel
        rn = reel.add_reels(cfg, posts, date)
        b.notes += rn
        if cfg.get("art_director", True):            # Claude checks every finished cover like an agency art director; problems show on the review card
            from . import vision as V
            for p in posts:
                if not p.get("images"):
                    continue
                head = re.split(r"[\U0001F300-\U0001FAFF\u2600-\u27BF]|\n", p.get("copy_text") or p.get("alt") or "")[0].strip()
                iss = V.art_check(Q.DOCS / p["images"][0], head)
                if iss:
                    p["flags"].insert(0, "⚠ Art director check: " + "; ".join(iss) + ". Look closely before approving.")
                elif iss == []:
                    p["flags"].append("Art director check: cover looks good")
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
