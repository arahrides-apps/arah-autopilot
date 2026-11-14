"""Story carousels. Every carousel tells ONE story about ONE topic and ends with a reason to book:

    place / experience : hook > what you'll love > getting there by car > make a day of it > book
    trip (day plan)    : hook > stop 1 > stop 2 > stop 3 > how to get there and book
    car                : hook > choose your car > pick your route > pick it up > book
    qa / tip           : hook > the answer / the detail > what it means for your trip > how to book > book
    brand, chat, trust, moment, versus, list : each has its own short arc (see below)

The words come from content/stories.yaml and the bank, never from unrelated posts."""
import re
from string import capwords
from . import templates as T
from . import themes as TH
from .config import load_yaml

NAMES = {"ys falls": "YS Falls", "blue mountains": "Blue Mountains"}
GENERIC_TOKENS = {"falls", "beach", "river", "house", "port", "blue", "gardens", "cove", "mountain", "mountains", "avenue", "bay", "cave", "hole"}

PICKUPS = "Kingston, Norman Manley, Montego Bay offices, MBJ or OCJ."
BOOK3 = "Say Hi to Winston on WhatsApp. Get your quote. Book and pay by Stripe."
CLOSE_PLACE = [("Send this to who is coming with you.", "Save it for your trip, then choose the car you want to drive at arahrides.com. Winston can help on WhatsApp, 24/7."),
               ("Your {p} day starts with the keys.", "Choose the car you want to drive at arahrides.com or say Hi to Winston on WhatsApp. Save this post for your trip."),
               ("Ready to go to {p}?", "Choose your car at arahrides.com. No same-day bookings, so book at least a day ahead."),
               ("Do not just save it. Go.", "Choose the car you want to drive at arahrides.com. Winston can help on WhatsApp, 24/7.")]
CLOSE_THEME = [("Send this to who is coming with you.", "Save it for your trip, then choose the car you want to drive at arahrides.com. Winston can help on WhatsApp, 24/7."),
               ("Your road trip starts with the keys.", "Choose the car you want to drive at arahrides.com or say Hi to Winston on WhatsApp. Save this post for your trip."),
               ("Ready to hit the road?", "Choose your car at arahrides.com. No same-day bookings, so book at least a day ahead."),
               ("Do not just save it. Go.", "Choose the car you want to drive at arahrides.com. Winston can help on WhatsApp, 24/7.")]
CLOSE_GENERAL = [("Save this for your trip.", "Tap the bookmark so you can find it when you plan. Questions? Ask Winston on WhatsApp."),
                 ("Send this to your travel partner.", "Planning together? Share it, then choose your car at arahrides.com."),
                 ("Planning Jamaica?", "Tell Winston your dates and pickup spot on WhatsApp and get a quote."),
                 ("Tag who you are travelling with.", "Then choose the car you want to drive at arahrides.com.")]

def price_slide(b):
    """The 'what will it cost' slide. The figure comes from brand.price_from in config.yaml (taken from Winston's knowledge base);
    leave it blank to show no price. Nothing is invented."""
    pf = (b.cfg["brand"].get("price_from") or "").strip()
    if pf:
        return ("Know the price before you land.", f"{pf[0].upper() + pf[1:]}. Unlimited mileage included. Say Hi to Winston on WhatsApp for your quote, then book and pay online.")
    return ("Know the price before you land.", "Every car on arahrides.com shows its daily rate. Say Hi to Winston on WhatsApp for your quote in minutes, then pay online.")

_S = None
def stories():
    global _S
    if _S is None:
        _S = load_yaml("stories.yaml")
    return _S

def nice(key):
    return NAMES.get(key) or capwords(key)

def find_place(name):
    """The story entry for a place name: exact match, else the longest key inside the name, else the shortest key containing it."""
    P = stories()["places"]; n = (name or "").lower().strip()
    if n in P:
        return n, P[n]
    inside = sorted((k for k in P if k in n), key=len, reverse=True)
    if inside:
        return inside[0], P[inside[0]]
    around = sorted((k for k in P if n and n in k), key=len)
    if around:
        return around[0], P[around[0]]
    return None, None

def about_words(key):
    """Words that must appear in a photo's label for it to be a photo of this place."""
    toks = [t for t in re.findall(r"[a-z]+", key.replace("'s", "")) if len(t) > 3 and t not in GENERIC_TOKENS]
    if toks:
        w = toks[0]
        return [w[:-1] if w.endswith("s") and len(w) > 5 else w]
    return [key]

TYPE_THEMES = {"car_hero": ["road", "group", "couple", "family"], "qa": ["road", "food", "couple"], "tip": ["culture", "food", "family", "river"],
               "brand": ["group", "couple", "road", "family"], "chat": ["couple", "solo", "group"], "trust": ["family", "group", "couple"],
               "moment": ["group", "culture", "family"], "versus": ["road", "couple", "river"], "place": ["couple", "family", "group", "river"],
               "experience": ["food", "river", "group", "culture"]}

def _themed(b, post, typ, n):
    """n different Jamaica photos for slides of a story (road trips, food, river days, couples, families, groups...). Missing ones are simply left as text slides."""
    from . import themes as TH
    order = list(TYPE_THEMES.get(typ, TH.GENERIC_BOOKING)); b.rng.shuffle(order)
    out = []
    for th in order + [t for t in TH.GENERIC_BOOKING if t not in order]:
        if len(out) >= n:
            break
        ph = b.pk.theme_photo(th)
        if ph is None and th in ("road", "river"):          # nothing free and matching: draw the place instead of showing something unrelated
            ph = b.pk.drawn({"road": "Holland Bamboo Avenue road trip", "river": "Jamaica waterfall river"}[th])
            if ph:
                post.setdefault("flags", []).append(ph.flags[0])
                out.append(ph); continue
        if ph:
            b.led.record(ph.keys(), ph.hash, b.today, ph.source, ph.series)
            post.setdefault("photos_extra", []).append({"id": ph.id, "name": ph.name})
            post.setdefault("flags", []).append("Slide photo (%s): %s" % (th, ph.credit or "our own photo"))
            out.append(ph)
    return out

def _slides(b, post, cover, items, closer, own_photos=None, typ=None):
    """items: [(heading, body)] ; closer: (heading, body). Returns the finished pages, 5 slides at most 6."""
    total = len(items) + 2
    out = [(cover, 1350)]
    own_photos = dict(own_photos or {})
    if typ and b.cfg["photos"].get("themed_slides", True):      # photos behind the story slides, not just words
        free = [i for i, (h, _b) in enumerate(items) if i not in own_photos and not h.lower().startswith(("know the price", "price"))]
        want = [i for i in free if i % 2 == 0][:2] + [None]                  # slides 2 and 4, plus the closing slide
        got = _themed(b, post, typ, len(want))
        closer_ph = got.pop() if len(got) == len(want) else None
        for i, ph in zip([w for w in want if w is not None], got):
            own_photos[i] = ph
        if closer_ph is not None:
            closer = tuple(closer) + (closer_ph,)
    for i, (h, body) in enumerate(items):
        ph = own_photos.get(i)
        if ph:
            out.append((T.photoslide(ph.path, i + 2, total, h, body), 1350))
        else:
            out.append((T.slide(i + 2, total, h, body, alt=bool(i % 2)), 1350))
    if len(closer) > 2:
        out.append((T.photoslide(closer[2].path, total, total, closer[0], closer[1], cta=True), 1350))
    else:
        out.append((T.slide(total, total, closer[0], closer[1], alt=bool(len(items) % 2), cta=True), 1350))
    return out

def _photo_for(b, post, key):
    return b.extra_photo(post, about_words(key)) if key else None

def place_story(b, post, pages, kind, e, confirmed, credit):
    key, st = find_place(e["place"]) if confirmed else (None, None)
    pl = e["place"] if confirmed else None
    if not st:
        st = {"do": "Hills, villages and views you cannot see from a resort. Your own car means your own timetable.",
              "drive": "Pick up at Kingston, Norman Manley, Montego Bay offices, MBJ or OCJ and choose a road.",
              "near": "Leave room for roadside stops. Waterfalls, beaches, jerk and coffee are all a drive away."}
        closers = CLOSE_THEME
        theme = True
    else:
        theme = bool(st.get("theme"))
        closers = CLOSE_THEME if theme else CLOSE_PLACE
    c = b.rng.choice(closers)
    closer = (c[0].format(p=(e["place"] if pl else "Jamaica")), c[1])
    items = [("What you will love.", st["do"]), ("Getting there.", st["drive"]), ("Make a day of it.", st["near"]), price_slide(b)]
    photos = {}
    if key and not theme:                                   # a real photo behind each stop slide, a different shot each time
        for i in range(3):
            x = b.story_photo(post, key)
            if x:
                photos[i] = x
    cover = pages[0][0]
    ph = b.last.get("ph")
    if ph is not None and pl and not theme:                 # slide 1 promises a saveable plan, with numbers
        nm = e["place"]
        cover = (T.hero(ph.path, "DISCOVER " + nm.upper(), nm + " in 1 day.", "3 stops. 1 rental car.", "Swipe for the drive, the stops and the price.", at="b") if ph.portrait
                 else T.split(ph.path, "DISCOVER " + nm.upper(), nm + " in 1 day. 3 stops. 1 rental car.", "Swipe for the drive, the stops and the price.", palette="green"))
    out = _slides(b, post, cover, items, closer, photos, typ=kind)
    seo = f"{pl} Jamaica by rental car: how to get there, what to do nearby and how to book." if pl else "Jamaica road trip idea by rental car: where to go, how to get there and how to book."
    text = seo + "\n\n" + post["copy_text"] + f"\n\n{st['do']}\n\nGetting there: {st['drive']}\n\n{st['near']}"
    post["copy_text"] = text
    post["caption"] = b.cap(post, kind, text, None, credit=credit, place=pl)
    return out

def car_story(b, post, pages, big):
    _T = "car_hero"
    ROUTES = ["blue mountains", "port antonio", "negril", "ocho rios", "treasure beach", "dunn's river falls", "ys falls", "reach falls",
              "mayfield falls", "seven mile beach", "martha brae", "port royal", "boston bay", "black river"]
    P = [(k, stories()["places"][k]) for k in ROUTES if k in stories()["places"]]
    k, v = P[b.rng.randrange(len(P))]
    if big:
        items = [("Room for everyone.", "7, 12 and 15 seaters. Family trips, church groups and teams stay together."),
                 ("Plan the route.", f"{nice(k)}: {v['do']}"),
                 ("Book early.", "Big vehicles are limited and December is busy. Reserve yours today.")]
    else:
        items = [("Choose your ride.", "Browse real cars with real photos on arahrides.com and pick the one you want to drive."),
                 ("Pick your route.", f"{nice(k)}: {v['do']}"),
                 ("Pick it up.", f"{PICKUPS} Collect your car and go.")]
    items.append(price_slide(b))
    return _slides(b, post, pages[0][0], items, b.rng.choice(CLOSE_GENERAL), typ=_T)

def qa_story(b, post, pages, e):
    _T = "qa"
    so = stories()["qa_so"].get(e["q"]) or "Ready when you are. Choose your car at arahrides.com."
    items = [("The answer.", e["a"]), ("What that means.", so), ("Book in 3 steps.", BOOK3)]
    return _slides(b, post, pages[0][0], items, b.rng.choice(CLOSE_GENERAL), typ=_T)

def tip_story(b, post, pages, e):
    _T = "tip"
    S = stories()["tip_so"]
    so = S.get(e["h"]) or (S["default_patois"] if e.get("k") == "PATOIS 101" else "Put it to use on your next drive.")
    items = [("The detail.", e["b"]), ("On your trip.", so), ("Book in 3 steps.", BOOK3)]
    return _slides(b, post, pages[0][0], items, b.rng.choice(CLOSE_GENERAL), typ=_T)

def brand_story(b, post, pages, e):
    _T = "brand"
    items = [("Choose your car.", "Browse real cars with real photos on arahrides.com and pick the one you want to drive."),
             ("Pick up where you land.", PICKUPS),
             ("Ask Winston.", "Quote, booking and questions on WhatsApp, 24/7. Pay by Stripe.")]
    return _slides(b, post, pages[0][0], items, b.rng.choice(CLOSE_GENERAL), typ=_T)

def chat_story(b, post, pages, e):
    _T = "chat"
    items = [("Step 1: Say Hi.", "Message Winston on WhatsApp. No app to download."),
             ("Step 2: Get a quote.", "Tell Winston your dates and pickup spot."),
             ("Step 3: Book and pay.", "Pay by Stripe to confirm. Then go see Jamaica.")]
    return _slides(b, post, pages[0][0], items, b.rng.choice(CLOSE_GENERAL), typ=_T)

def trust_story(b, post, pages, e):
    _T = "trust"
    items = [("The team.", e["b"]), ("Real cars.", "Browse real cars with real photos on arahrides.com."),
             ("Say Hi to Winston.", "Questions? Winston answers on WhatsApp, 24/7.")]
    return _slides(b, post, pages[0][0], items, b.rng.choice(CLOSE_GENERAL), typ=_T)

def _event_files(m, pattern):
    from pathlib import Path as _P
    import re as _re
    root = _P(__file__).resolve().parent.parent / "content"
    k = (m.get("k", "") + " " + m.get("h", "")).lower()
    out = []
    for f in sorted(root.glob(pattern)):
        stem = _re.sub(r"_\d+$", "", f.stem.split("_", 1)[1] if pattern.startswith("poster") else f.stem)
        stem = stem.replace("poster_", "").replace("event_", "")
        if stem.replace("_", " ") in k:
            out.append(f)
    return out

def _event_poster(m):
    """content/poster_<event words>[_N].jpg are the event's finished posters (for example poster_jamaica_cup.jpg, poster_mouttet_mile_1.jpg)."""
    return _event_files(m, "poster_*.jpg")

def _event_reel(post, m):
    """content/reels/event_<event words>.mp4 is that event's own video. It goes out as the Reel in the final week before the event and during it."""
    import datetime as _dt
    vids = _event_files(m, "reels/event_*.mp4")
    try:
        left = (_dt.date.fromisoformat(str(m["date"])) - _dt.date.fromisoformat(post["date"])).days
    except Exception:
        return
    if left <= 7:
        post["event_reel_flag"] = True               # no video supplied: still goes out as an animated slideshow Reel
    if left <= 7 and vids:
        post["event_reel_src"] = str(vids[0])

def moment_story(b, post, pages, m):
    _T = "moment"
    posters = _event_poster(m) if m.get("event") else []
    if m.get("event") and len(posters) >= 2:                  # several finished posters: they are the first slides, then how to get there, the price, book
        key, stp = find_place(m.get("place", ""))
        n = len(posters[:3]); total = n + 3
        drive = (stp or {}).get("drive") or PICKUPS
        out = [(T.posterfull(f), 1350) for f in posters[:3]]
        out.append((T.slide(n + 1, total, "Drive there.", drive + " " + m.get("note", ""), alt=False), 1350))
        ph, pb = price_slide(b)
        out.append((T.slide(n + 2, total, ph, pb, alt=True), 1350))
        cl = b.rng.choice(CLOSE_GENERAL)
        out.append((T.slide(total, total, cl[0], cl[1], alt=False, cta=True), 1350))
        post.setdefault("flags", []).append("Slides 1 to %d are the supplied event posters, unchanged" % n)
        _event_reel(post, m)
        return out
    if m.get("event") and len(posters) == 1:
        pages = [(T.posterslide(posters[0], m.get("k", ""), m.get("h", ""), "Pick up at MBJ and drive there your way."), 1350)] + list(pages[1:])
        post.setdefault("flags", []).append("Cover is the supplied event poster")
        _event_reel(post, m)
    if m.get("event"):                                       # an upcoming event: what, when/where, how to drive there, the price, book
        key, stp = find_place(m.get("place", ""))
        items = [("What is on.", m["b"]), ("When and where.", f"{m['badge'].title().replace('–', ' to ')}. {m['where']}."),
                 ("Drive there.", (stp or {}).get("drive") or PICKUPS), price_slide(b)]
        photos = {}
        et = TH.event_theme(m.get("k", ""), m.get("h", ""))
        if et:                                               # a sport or activity: its own photos (e.g. tennis courts), then the place
            for i in (0, 1):
                x = b.pk.theme_photo(et)
                if x:
                    photos[i] = x; post.setdefault("flags", []).append(x.flags[0])
        if key:
            for i in (0, 1):
                if i in photos: continue
                x = b.story_photo(post, key)
                if x: photos[i] = x
        _event_reel(post, m)
        cover = pages[0][0]
        if et:
            c = b.pk.theme_photo(et)
            if c:
                cover = T.ccover(c.path, m.get("k", ""), m.get("h", ""), "Swipe for the details."); post.setdefault("flags", []).append(c.flags[0])
        return _slides(b, post, cover, items, b.rng.choice(CLOSE_GENERAL), photos, typ="moment")
    if m.get("theme"):                                       # a seasonal campaign (Christmas...): its own photos on the cover and slides
        ph = [b.pk.theme_photo(m["theme"]) for _ in range(3)]
        for x in ph:
            if x: post.setdefault("flags", []).append(x.flags[0])
        cover = T.ccover(ph[0].path, m.get("k", ""), m.get("h", ""), "Swipe for the plan.") if ph[0] else pages[0][0]
        its = [(m.get("s1", "Plan your wheels."), m["b"]), ("Pick up where you land.", PICKUPS), price_slide(b)]
        return _slides(b, post, cover, its, b.rng.choice(CLOSE_GENERAL), {0: ph[1], 1: ph[2]} if ph[1] and ph[2] else {}, typ=_T)
    items = [("Plan your wheels.", "Cars are limited around busy dates. Reserve yours at arahrides.com."),
             ("Pick up where you land.", PICKUPS), ("Book in 3 steps.", BOOK3)]
    return _slides(b, post, pages[0][0], items, b.rng.choice(CLOSE_GENERAL), typ=_T)

def versus_story(b, post, pages, e):
    ph = b.cover_photo(post, "", "road")
    cover = T.ccover(ph.path, e["k"], e["h"], "Swipe to compare.") if ph else T.ccover_plain(e["k"], e["h"], "Swipe to compare.")
    items = [("Other companies.", ". ".join(e["them"]) + "."), ("Arah Rides.", ". ".join(e["us"]) + "."),
             ("Choose your car.", "Browse real cars with real photos on arahrides.com.")]
    return _slides(b, post, cover, items, b.rng.choice(CLOSE_GENERAL), typ="versus")

def list_story(b, post, pages, e):
    items = [(x, "") for x in e["items"]][:4]
    ph = b.cover_photo(post, " ".join(e["items"][:2]), "road")
    cover = T.ccover(ph.path, e["k"], e["h"], "Swipe through.") if ph else T.ccover_plain(e["k"], e["h"], "Swipe through.")
    if len(e["items"]) >= 5:                                 # six slides is the limit: the last item carries the button
        out = [(cover, 1350)]
        its = e["items"][:5]
        for i, x in enumerate(its):
            out.append((T.slide(i + 2, 6, x, "", alt=bool(i % 2), cta=(i == len(its) - 1)), 1350))
        return out
    return _slides(b, post, cover, items, b.rng.choice(CLOSE_GENERAL))

def build(b, post, typ, pages):
    kind, e = b.last["kind"], b.last["e"]
    if typ in ("place", "experience"):
        return place_story(b, post, pages, typ, e, b.last["ok"], b.last["credit"])
    if typ == "car_hero":
        return car_story(b, post, pages, b.last.get("big", False))
    if typ == "qa":
        return qa_story(b, post, pages, e)
    if typ == "tip":
        return tip_story(b, post, pages, e)
    if typ == "chat":
        return chat_story(b, post, pages, e)
    if typ == "trust":
        return trust_story(b, post, pages, e)
    if typ == "moment":
        return moment_story(b, post, pages, e)
    if typ == "versus":
        return versus_story(b, post, pages, e)
    if typ == "list":
        return list_story(b, post, pages, e)
    return brand_story(b, post, pages, e)          # brand and anything else
