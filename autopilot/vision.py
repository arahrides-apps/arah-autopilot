"""Recognise what an unplaced photo shows (no GPS) by comparing it with word descriptions of Jamaican places, food and scenes
(CLIP zero-shot), and with photos you have already labelled. Needs torch + transformers, which only the Index workflow installs.
Without them every function returns None and the indexer simply leaves the photo unplaced."""
import logging
from pathlib import Path
log = logging.getLogger("vision")

# label -> (what the photo looks like, entry fields). place/parish/coastal make it a place photo; "about" words are what the picker matches on.
# kind "skip" = not usable (screenshots, documents, selfies).
L = {
 "holland bamboo": ("a long tunnel of tall green bamboo arching over a country road", dict(kind="scenery", place="Holland Bamboo", parish="St Elizabeth", coastal=False, about="Holland Bamboo Avenue, Black River road, St Elizabeth - bamboo tunnel")),
 "bob marley": ("a Bob Marley statue, mural, museum or portrait with dreadlocks and reggae imagery", dict(kind="scenery", place="Bob Marley Museum", parish="Kingston", coastal=False, about="Bob Marley Museum, Kingston - reggae culture")),
 "trident castle": ("a white mansion castle with turrets and a green lawn above the sea", dict(kind="scenery", place="Trident Castle", parish="Portland", coastal=True, about="Trident Castle, Port Antonio, Portland - castle")),
 "dunn's river falls": ("a wide terraced waterfall cascading over rocks into the sea with climbers", dict(kind="scenery", place="Dunn's River Falls", parish="St Ann", coastal=True, about="Dunn's River Falls, Ocho Rios, St Ann - waterfall")),
 "waterfall": ("a tropical waterfall in a jungle with a natural pool", dict(kind="scenery", about="Jamaica waterfall river nature")),
 "river rafting": ("bamboo rafts floating on a calm river with a raft captain", dict(kind="scenery", about="Jamaica river rafting Martha Brae Rio Grande river")),
 "blue mountains": ("misty green mountains with coffee farms and winding roads", dict(kind="scenery", about="Jamaica Blue Mountains hills coffee mountain")),
 "sunset": ("a golden orange sunset over the sea with palm trees", dict(kind="scenery", about="Jamaica sunset sea evening beach")),
 "beach": ("a white sand beach with turquoise water and palm trees", dict(kind="scenery", coastal=True, about="Jamaica beach sea sand coast")),
 "negril cliffs": ("rocky cliffs with a lighthouse and cliff jumping into clear blue water", dict(kind="scenery", place="Negril", parish="Westmoreland", coastal=True, about="Negril cliffs West End, Westmoreland - lighthouse cliff")),
 "kingston": ("a city street with colourful murals, buildings and traffic", dict(kind="scenery", about="Jamaica Kingston city street art mural")),
 "jerk chicken": ("jerk chicken grilled over a pimento wood fire with sides", dict(kind="scenery", about="Jamaica jerk chicken food jerk")),
 "jamaican patty": ("a golden Jamaican beef patty pastry in a paper bag or on coco bread", dict(kind="scenery", about="Jamaica patty food beef patty coco bread")),
 "fruit": ("fresh tropical fruit: mangoes, ackee, pineapple, ugli, star apple, bananas at a market stall", dict(kind="scenery", about="Jamaica fruit market mango pineapple ackee food")),
 "food": ("a plate of Jamaican food: rice and peas, oxtail, saltfish, plantain, festival", dict(kind="scenery", about="Jamaica food rice and peas oxtail ackee saltfish")),
 "drinks": ("rum punch, coconut water, Red Stripe beer or a cocktail on a beach", dict(kind="scenery", about="Jamaica drinks rum punch coconut Red Stripe")),
 "road trip": ("a scenic coastal or country road with a car driving", dict(kind="scenery", about="Jamaica road trip drive scenic road")),
 "rental car": ("a rental car, SUV or van parked, close view of the vehicle", dict(kind="car", about="Arah Rides rental vehicle")),
 "airport": ("an airport arrivals hall, a plane or an airport car rental counter", dict(kind="scenery", about="Jamaica airport arrival Montego Bay Kingston")),
 "people": ("a group of happy tourists, friends or a family smiling on holiday in the tropics", dict(kind="scenery", people=True, about="Jamaica people friends family travellers")),
 "market": ("a busy outdoor market with vendors, craft stalls and colourful goods", dict(kind="scenery", about="Jamaica market craft culture")),
 "reggae": ("a live reggae band, drums, rasta colours red gold and green", dict(kind="scenery", about="Jamaica reggae music culture")),
 "sunrise": ("a soft pink and golden sunrise over mountains or the sea early in the morning", dict(kind="scenery", about="Jamaica sunrise morning dawn")),
 "carnival": ("colourful carnival costumes with feathers, beads and a parade of dancers", dict(kind="scenery", people=True, about="Jamaica carnival costume parade")),
 "nightlife": ("a lively night scene: street party, bar, club, dancehall or fireworks with lights after dark", dict(kind="scenery", about="Jamaica nightlife night party dancehall")),
 "attraction": ("a famous tourist attraction: a plantation great house, a zip line, a cave, a blue hole or a historic fort", dict(kind="scenery", about="Jamaica attraction tour great house zipline")),
 "resort": ("a tropical hotel, villa or resort with a pool and palm trees", dict(kind="scenery", about="Jamaica resort villa hotel pool stay")),
 "not usable": ("a screenshot, a document, a logo, text on a plain background or a selfie", dict(kind="skip")),
}
NAMES = list(L)
# the categories used to pick photos for posts
CATS = ["people", "food", "culture", "beach", "nightlife", "carnival", "sunset", "sunrise", "airport", "attractions", "nature", "waterfall", "road", "cars", "city", "music", "accommodation", "drinks"]
LABEL_CATS = {"holland bamboo": ["attractions", "nature", "road"], "bob marley": ["culture", "music", "attractions", "city"], "trident castle": ["attractions", "accommodation"], "dunn's river falls": ["attractions", "waterfall", "nature", "beach"],
              "waterfall": ["waterfall", "nature"], "river rafting": ["attractions", "nature"], "blue mountains": ["nature", "road"], "sunset": ["sunset", "beach"], "sunrise": ["sunrise", "nature"],
              "beach": ["beach"], "negril cliffs": ["attractions", "beach", "nature"], "kingston": ["city", "culture"], "jerk chicken": ["food"], "jamaican patty": ["food"], "fruit": ["food", "culture"],
              "food": ["food"], "drinks": ["drinks", "food"], "road trip": ["road"], "rental car": ["cars"], "airport": ["airport"], "people": ["people"], "market": ["culture", "food", "city"],
              "reggae": ["music", "culture", "nightlife"], "carnival": ["carnival", "culture", "people", "music"], "nightlife": ["nightlife", "music", "people"], "attraction": ["attractions"], "resort": ["accommodation"]}
def cats_for(label, claude_cats=None, people=False):
    c = list(LABEL_CATS.get(label, [])) + [x for x in (claude_cats or []) if x in CATS]
    if people and "people" not in c: c.append("people")
    return sorted(set(c))
_M = {}

def available():
    try:
        import torch, transformers  # noqa
        return True
    except Exception:
        return False

def _model():
    if not _M:
        import torch
        from transformers import CLIPModel, CLIPProcessor
        n = "openai/clip-vit-base-patch32"
        _M.update(m=CLIPModel.from_pretrained(n).eval(), p=CLIPProcessor.from_pretrained(n), t=torch)
    return _M

def _norm(f):
    return f / f.norm(dim=-1, keepdim=True)

def embed_images(paths):
    from PIL import Image
    M = _model(); t = M["t"]; m = M["m"]; out = []
    for i in range(0, len(paths), 16):
        ims = [Image.open(p).convert("RGB") for p in paths[i:i + 16]]
        with t.no_grad():
            px = M["p"](images=ims, return_tensors="pt")["pixel_values"]
            f = m.visual_projection(m.vision_model(pixel_values=px).pooler_output)   # works on every transformers version
        out.append(_norm(f))
    return t.cat(out) if out else None

def embed_labels():
    M = _model(); t = M["t"]; m = M["m"]
    with t.no_grad():
        tk = M["p"](text=["a photo of " + L[n][0] for n in NAMES], return_tensors="pt", padding=True)
        f = m.text_projection(m.text_model(input_ids=tk["input_ids"], attention_mask=tk["attention_mask"]).pooler_output)
    return _norm(f)

def classify(paths, min_prob=0.45, refs=None):
    """-> list of (label or None, confidence, runner_up, ref_name or None) for each path. refs = (embeddings, [entry dicts]) of labelled photos."""
    if not available() or not paths:
        return None
    M = _model(); t = M["t"]
    I = embed_images(paths); T = embed_labels()
    pr = (100 * I @ T.T).softmax(dim=-1)
    res = []
    for k in range(len(paths)):
        top = pr[k].topk(2)
        a, b = top.indices.tolist(); pa, pb = top.values.tolist()
        ref = None
        if refs is not None and len(refs[1]):
            sims = I[k] @ refs[0].T
            v, j = sims.max(0)
            if float(v) >= 0.90:
                ref = (refs[1][int(j)], float(v))
        lab = NAMES[a] if pa >= min_prob and pa - pb >= 0.10 else None
        res.append((lab, round(pa, 2), NAMES[b], ref))
    return res


# ---------------------------------------------------------------- web references: real photos of the same places, from Wikimedia Commons
WEB = {"holland bamboo": "Holland Bamboo Avenue Jamaica", "trident castle": "Trident Castle Port Antonio", "dunn's river falls": "Dunn's River Falls",
       "bob marley": "Bob Marley Museum Kingston", "negril cliffs": "Negril cliffs Rick's Cafe", "blue mountains": "Blue Mountains Jamaica coffee",
       "river rafting": "Martha Brae river rafting", "jamaican patty": "Jamaican patty", "jerk chicken": "jerk chicken Jamaica", "fruit": "Jamaican fruit market ackee mango"}

def web_refs(cache, per=4):
    """Download a few free Commons photos for each place/dish (once) and embed them. -> (embeddings, [label per row]) or None."""
    import requests
    from PIL import Image
    cache = Path(cache); cache.mkdir(parents=True, exist_ok=True); paths, labs = [], []
    for lab, q in WEB.items():
        try:
            r = requests.get("https://commons.wikimedia.org/w/api.php", params={"action": "query", "generator": "search", "gsrsearch": q + " filetype:bitmap", "gsrnamespace": 6, "gsrlimit": per,
                             "prop": "imageinfo", "iiprop": "url", "iiurlwidth": 400, "format": "json"}, timeout=30, headers={"User-Agent": "ArahAutopilot/1.0"}).json()
            for pg in (r.get("query", {}).get("pages", {}) or {}).values():
                u = (pg.get("imageinfo") or [{}])[0].get("thumburl")
                if not u: continue
                f = cache / (lab.replace(" ", "_").replace("'", "") + "_" + str(abs(hash(u)) % 10**8) + ".jpg")
                if not f.exists():
                    f.write_bytes(requests.get(u, timeout=30, headers={"User-Agent": "ArahAutopilot/1.0"}).content)
                try:
                    Image.open(f).verify()
                except Exception:
                    f.unlink(missing_ok=True); continue                    # not a real image (rate-limited reply): skip, retry next run
                paths.append(f); labs.append(lab)
        except Exception as e:
            log.warning("web refs for %s skipped: %s", lab, e)
    if not paths or not available():
        return None
    ok = []
    for p, l in zip(paths, labs):
        try: Image.open(p).convert("RGB"); ok.append((p, l))
        except Exception: pass
    return embed_images([p for p, _ in ok]), [l for _, l in ok]

def web_match(img_emb, refs, min_sim=0.86):
    """Best label whose web reference photo looks (nearly) like this one, with its similarity."""
    if refs is None: return None
    sims = img_emb @ refs[0].T
    v, j = sims.max(0)
    return (refs[1][int(j)], round(float(v), 2)) if float(v) >= min_sim else None


# ---------------------------------------------------------------- which AI looks at the pictures: Gemini (GEMINI_API_KEY) or Claude (ANTHROPIC_API_KEY)
def ai_provider():
    """('gemini', key) or ('anthropic', key) or (None, None). Gemini is used whenever a Gemini key exists (GEMINI_API_KEY, GOOGLE_API_KEY,
    or a Gemini key saved under ANTHROPIC_API_KEY: they start with 'AIza')."""
    import os
    g = (os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY") or "").strip()
    a = (os.environ.get("ANTHROPIC_API_KEY") or "").strip()
    if g:
        return "gemini", g
    if a.startswith("AIza"):
        return "gemini", a
    if a:
        return "anthropic", a
    return None, None

_BROKEN = []
def ai_on():
    """False when no key is set, or when the key failed so often this run that the AI is switched off (see ask)."""
    return ai_provider()[0] is not None and not _BROKEN

def ai_name():
    return {"gemini": "Gemini", "anthropic": "Claude"}.get(ai_provider()[0], "AI")

_GMODEL = []
def ask(parts, max_tokens=600):
    """parts: list of str (text) or bytes (a JPEG). -> the model's reply text. Raises on error; returns None when no key.
    After 15 failures in a row with no answer at all (wrong key, no access), the AI is switched off for the rest of the run,
    so a bad key can never make a run crawl into its time limit again; the run then uses the stricter no-AI photo rules."""
    if _BROKEN:
        raise RuntimeError("AI switched off for this run: " + _BROKEN[0])
    try:
        out = _ask(parts, max_tokens)
        STATS["streak"] = 0
        return out
    except Exception as e:
        STATS["streak"] = STATS.get("streak", 0) + 1
        if not STATS.get("why"): STATS["why"] = str(e)[:160]
        if STATS["streak"] >= 15 and STATS["ok"] == 0:
            _BROKEN.append(STATS["why"]); log.error("AI checks switched off for this run: %s", STATS["why"])
        raise

def _ask(parts, max_tokens=600):
    import os, base64, requests
    prov, key = ai_provider()
    if not prov:
        return None
    if prov == "anthropic":
        content = [{"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": base64.b64encode(x).decode()}} if isinstance(x, bytes)
                   else {"type": "text", "text": x} for x in parts]
        r = requests.post("https://api.anthropic.com/v1/messages", timeout=120,
                          headers={"x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"},
                          json={"model": os.environ.get("CLAUDE_MODEL") or "claude-sonnet-5-5", "max_tokens": max_tokens, "messages": [{"role": "user", "content": content}]})
        if r.status_code >= 400:
            STATS["fail"] += 1
            raise RuntimeError(f"Claude key rejected ({r.status_code}): {r.text[:100]}")
        STATS["ok"] += 1
        return "".join(b.get("text", "") for b in r.json()["content"])
    gparts = [{"inline_data": {"mime_type": "image/jpeg", "data": base64.b64encode(x).decode()}} if isinstance(x, bytes) else {"text": x} for x in parts]
    # Every Gemini model has its own free-tier limit, so when one is used up (429) the next one answers.
    models = [m for m in ([os.environ.get("GEMINI_MODEL")] + GEMINI_MODELS) if m and m not in _GDEAD]
    import time
    for rnd in range(2):
        for m in models:
            if m in _GDEAD:
                continue
            for think in (True, False):
                gen = {"maxOutputTokens": max(max_tokens, 2048), "temperature": 0}   # newer Gemini models think before answering: room for both
                if think:
                    gen["thinkingConfig"] = {"thinkingBudget": 0}          # answer straight away (thinking would eat the reply's tokens)
                try:
                    r = requests.post(f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent", timeout=90,
                                      headers={"x-goog-api-key": key, "content-type": "application/json"},
                                      json={"contents": [{"role": "user", "parts": gparts}], "generationConfig": gen})
                except Exception:
                    STATS["fail"] += 1; break
                if r.status_code == 400 and think and "thinking" in r.text.lower():
                    continue                                              # this model has no thinking setting: ask again without it
                if r.status_code in (404, 403):
                    _GDEAD.add(m); break                                  # model not available for this key: never ask it again this run
                if r.status_code in (429, 500, 503):
                    STATS["limit"] += 1
                    if "PerDay" in r.text or "per day" in r.text.lower():
                        _GDEAD.add(m)                                     # used up for today
                    break                                                 # try the next model
                if r.status_code >= 400:
                    STATS["fail"] += 1
                    if r.status_code in (400, 401) and "key" in r.text.lower():
                        raise RuntimeError(f"Gemini key rejected ({r.status_code}): {r.text[:100]}")
                    break
                c = (r.json().get("candidates") or [{}])[0]
                txt = "".join(x.get("text", "") for x in (c.get("content") or {}).get("parts", []) if not x.get("thought"))
                if not txt.strip():
                    STATS["empty"] = STATS.get("empty", 0) + 1
                    continue                                              # empty reply (thinking used it all up): ask again the other way
                STATS["ok"] += 1
                return txt
        time.sleep(15)                                                    # every model busy: wait a moment, then one more round
    STATS["fail"] += 1
    raise RuntimeError("Gemini did not answer (rate limit or error)")

GEMINI_MODELS = ["gemini-flash-latest", "gemini-2.5-flash", "gemini-flash-lite-latest", "gemini-2.5-flash-lite", "gemini-2.0-flash", "gemini-2.0-flash-lite"]
_GDEAD = set()
STATS = {"ok": 0, "fail": 0, "limit": 0}

def status():
    """One line for the review page: which AI ran, how many checks it answered, and why it stopped if it did."""
    if ai_provider()[0] is None:
        return "AI photo checks OFF: add GEMINI_API_KEY in GitHub Settings → Secrets → Actions"
    s = f"{ai_name()} checks answered {STATS['ok']}"
    if _BROKEN:
        return s + f" · AI SWITCHED OFF this run, key not working ({_BROKEN[0][:90]}): only photos tagged with the subject were used"
    if STATS["fail"] or STATS["limit"]:
        s += f", not answered {STATS['fail']} (busy {STATS['limit']}x): photos it could not check were left out"
    return s

def _jpeg(path, size=768):
    import io
    from PIL import Image
    im = Image.open(path).convert("RGB"); im.thumbnail((size, size)); b = io.BytesIO(); im.save(b, "JPEG", quality=82)
    return b.getvalue()


# ---------------------------------------------------------------- Claude reviews the picture (needs ANTHROPIC_API_KEY; skipped without it)
PLACES = "Kingston, Port Antonio, Ocho Rios, Montego Bay, Negril, Treasure Beach, Mandeville, Blue Mountains, Falmouth, Black River, Holland Bamboo, Trident Castle, Bob Marley Museum, Devon House, Dunn's River Falls, Blue Hole, Reach Falls, Lover's Leap, Rose Hall, Lime Cay"
PROMPT = ("You are indexing photos for a Jamaican car rental company's Instagram. For each numbered photo answer one JSON object. Reply with ONLY a JSON array, one object per photo, in order: "
          '{"n":1,"kind":"scenery|car|food|people|not-usable","label":"one of %s or other","place":"specific Jamaican place or empty","parish":"","what":"max 14 words saying what the photo shows",'
          '"categories":["any of: %s"],"people":true|false,"season":"any|christmas|carnival|summer","jamaica":"yes|likely|no|unsure","confidence":0.0-1.0}. '
          "Name a specific place only if the picture shows it clearly (a sign, a landmark you recognise, a distinctive view such as the bamboo tunnel at Holland Bamboo or the castle at Trident); otherwise leave place empty and say confidence honestly. "
          "Mark not-usable any photo whose main subject is an old, classic, vintage, rusty or wrecked car, a racing or rally car, a race track or a car show: we rent modern everyday cars. "
          "Mark not-usable any black-and-white, sepia, archive or historical photo, or one that clearly looks older than about 2014 (old cars, old clothing, faded film). "
          "Do not identify real people from their faces; statues, murals and signs are fine. Mark screenshots, documents, logos and stock photos of other countries not-usable or jamaica:no. "
          "Likely places in this library: " + PLACES + ".")

def claude_review(paths, model=None, batch=6):
    """-> list of dicts (or None per photo) from the AI (Gemini or Claude), or None when no API key / error."""
    import json
    if not ai_on():
        log.warning("No AI key set (GEMINI_API_KEY or ANTHROPIC_API_KEY): photo review skipped"); return None
    if not paths: return None
    out = []
    for i in range(0, len(paths), batch):
        ch = paths[i:i + batch]; parts = []
        for k, p in enumerate(ch, 1):
            parts += ["Photo %d:" % k, _jpeg(p)]
        parts.append(PROMPT % (", ".join(NAMES), ", ".join(CATS)))
        try:
            txt = ask(parts, 1500) or ""
            import re as _re; arr = json.loads(_re.search(r"\[.*\]", txt, _re.S).group(0))
            by = {int(a.get("n", 0)): a for a in arr if isinstance(a, dict)}
            out += [by.get(k) for k in range(1, len(ch) + 1)]
        except Exception as e:
            log.warning("AI review failed for a batch: %s", e); out += [None] * len(ch)
    return out


_GATE = {}
def jamaica_gate(path, key):
    """Claude looks at a photo from the web and says whether it was taken in Jamaica. True = ok to use. Verdicts are kept in content/web_checked.json so a photo is only ever checked once.
    No API key: returns True (the text rules still apply). Not Jamaica, unsure, or not usable: False."""
    import os, json
    from pathlib import Path
    f = Path(os.environ.get("AUTOPILOT_ROOT") or ".") / "content" / "web_checked.json"
    if not _GATE:
        try: _GATE.update(json.loads(f.read_text()))
        except Exception: pass
    if key in _GATE:
        return _GATE[key]
    if not ai_on():
        return True
    res = claude_review([path], batch=1)
    r = (res or [None])[0]
    if not r:
        return False                                  # the AI could not look at it: do not use it (it is asked again next run)
    ok = r.get("jamaica") in ("yes", "likely") and r.get("kind") != "not-usable"
    _GATE[key] = ok
    try:
        f.parent.mkdir(parents=True, exist_ok=True); f.write_text(json.dumps(_GATE, indent=0))
    except Exception:
        pass
    if not ok: log.info("Claude says not Jamaica / not usable: %s (%s)", key, r.get("what", ""))
    return ok


ART_PROMPT = ("You are the art director of a top marketing agency, checking an Instagram post cover for a Jamaican car rental company (Arah Rides) before it goes out. "
              "The post's headline is: \"%s\". List only real problems, each in a few plain words: "
              "an old, classic, rusty or racing car; a photo not from Jamaica; a photo that does not fit the headline (a beach for an inland town, a different place, food that is not mentioned); "
              "text hard to read; a model year shown; blurry or dark photo; a box or label covering a number plate; anything that would look amateur. "
              "A car of the same body style as the one named is acceptable. Reply with ONLY JSON: {\"ok\": true|false, \"issues\": [\"...\"]}")

def art_check(path, headline, model=None):
    """The AI looks at the finished cover like an art director. -> list of issues ([] = looks good, None = could not check)."""
    import json
    if not ai_on():
        return None
    try:
        txt = ask([_jpeg(path, 900), ART_PROMPT % headline[:160]], 400) or ""
        import re as _re; d = json.loads(_re.search(r"\{.*\}", txt, _re.S).group(0))
        return [] if d.get("ok") else [str(i) for i in d.get("issues", [])][:4]
    except Exception as e:
        log.warning("art check failed: %s", e); return None

def yes_no(txt):
    """Reads a yes/no answer however the model words it: {"yes": true}, ```json ...```, 'Yes.', 'No, it shows...'. None if it cannot tell."""
    import json, re
    t = (txt or "").strip()
    m = re.search(r"\{.*?\}", t, re.S)
    if m:
        try:
            d = json.loads(m.group(0)); v = d.get("yes", d.get("answer", d.get("match")))
            if isinstance(v, bool): return v
            if isinstance(v, str): t = v
        except Exception:
            pass
    m = re.search(r'"yes"\s*:\s*(true|false)', t, re.I)
    if m: return m.group(1).lower() == "true"
    m = re.match(r"\W*(yes|true|no|false)\b", t, re.I)
    if m: return m.group(1).lower() in ("yes", "true")
    return None

_SHOWS = {}
def shows(path, want, model=None):
    """Does this photo clearly show <want>? True / False / None (could not check). Uses Gemini or Claude, whichever key is set.
    Callers treat None as NO for anything from the web: a photo nobody could check is never used."""
    import json
    if not ai_on():
        return None
    import os, hashlib
    from pathlib import Path as _P
    f = _P(os.environ.get("AUTOPILOT_ROOT") or ".") / "content" / "shows_checked.json"     # answers are kept, so the free Gemini limit goes further
    if not _SHOWS:
        try: _SHOWS.update(json.loads(f.read_text()))
        except Exception: _SHOWS["_"] = True
    k = hashlib.md5((_P(path).name + "|" + want).encode()).hexdigest()[:20]
    if k in _SHOWS:
        return _SHOWS[k]
    q = (f"Does this photo clearly show {want}? Judge only what is visible. Be strict, like a picky art director: "
         "answer no when the photo shows a different food (for example a burger or pizza when the words say jerk, patties, shrimp or fish), "
         "a different place or a generic view when the words name a specific place, animals or birds the words do not mention, "
         "snow, autumn leaves, pine forests, deserts or anything that could not be Jamaica, people who do not match (a white family for a Jamaican family, "
         "no child when the words say daughter or son), or anything only loosely related. "
         'Reply with ONLY JSON: {"yes": true|false}')
    try:
        txt = ask([_jpeg(path, 800), q], 100) or ""
        v = yes_no(txt)
        if v is None:
            STATS["unread"] = STATS.get("unread", 0) + 1
            if STATS["unread"] >= 15 and STATS.get("read", 0) == 0 and not _BROKEN:
                _BROKEN.append(f"answers could not be read, e.g. {txt[:60]!r}"); log.error("AI checks switched off: answers unreadable: %r", txt[:200])
            raise ValueError(f"unreadable answer: {txt[:80]!r}")
        STATS["read"] = STATS.get("read", 0) + 1
        _SHOWS[k] = v
        try:
            f.parent.mkdir(parents=True, exist_ok=True); f.write_text(json.dumps(_SHOWS, indent=0))
        except Exception:
            pass
        return v
    except Exception as e:
        log.warning("subject check failed: %s", e); return None
