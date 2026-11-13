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


# ---------------------------------------------------------------- Claude reviews the picture (needs ANTHROPIC_API_KEY; skipped without it)
PLACES = "Kingston, Port Antonio, Ocho Rios, Montego Bay, Negril, Treasure Beach, Mandeville, Blue Mountains, Falmouth, Black River, Holland Bamboo, Trident Castle, Bob Marley Museum, Devon House, Dunn's River Falls, Blue Hole, Reach Falls, Lover's Leap, Rose Hall, Lime Cay"
PROMPT = ("You are indexing photos for a Jamaican car rental company's Instagram. For each numbered photo answer one JSON object. Reply with ONLY a JSON array, one object per photo, in order: "
          '{"n":1,"kind":"scenery|car|food|people|not-usable","label":"one of %s or other","place":"specific Jamaican place or empty","parish":"","what":"max 14 words saying what the photo shows",'
          '"categories":["any of: %s"],"people":true|false,"season":"any|christmas|carnival|summer","jamaica":"yes|likely|no|unsure","confidence":0.0-1.0}. '
          "Name a specific place only if the picture shows it clearly (a sign, a landmark you recognise, a distinctive view such as the bamboo tunnel at Holland Bamboo or the castle at Trident); otherwise leave place empty and say confidence honestly. "
          "Do not identify real people from their faces; statues, murals and signs are fine. Mark screenshots, documents, logos and stock photos of other countries not-usable or jamaica:no. "
          "Likely places in this library: " + PLACES + ".")

def claude_review(paths, model=None, batch=6):
    """-> list of dicts (or None per photo) from Claude, or None when no API key / error."""
    import os, io, json, base64, requests
    from PIL import Image
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        log.warning("ANTHROPIC_API_KEY is not set: Claude review skipped (add it under Settings > Secrets and variables > Actions)"); return None
    if not paths: return None
    model = model or os.environ.get("CLAUDE_MODEL") or "claude-sonnet-5-5"
    out = []
    for i in range(0, len(paths), batch):
        ch = paths[i:i + batch]; content = []
        for k, p in enumerate(ch, 1):
            im = Image.open(p).convert("RGB"); im.thumbnail((768, 768)); b = io.BytesIO(); im.save(b, "JPEG", quality=80)
            content += [{"type": "text", "text": "Photo %d:" % k}, {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": base64.b64encode(b.getvalue()).decode()}}]
        content.append({"type": "text", "text": PROMPT % (", ".join(NAMES), ", ".join(CATS))})
        try:
            r = requests.post("https://api.anthropic.com/v1/messages", timeout=120, headers={"x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"},
                              json={"model": model, "max_tokens": 1500, "messages": [{"role": "user", "content": content}]})
            r.raise_for_status()
            txt = "".join(b.get("text", "") for b in r.json()["content"])
            arr = json.loads(txt[txt.index("["): txt.rindex("]") + 1])
            by = {int(a.get("n", 0)): a for a in arr if isinstance(a, dict)}
            out += [by.get(k) for k in range(1, len(ch) + 1)]
        except Exception as e:
            log.warning("Claude review failed for a batch: %s", e); out += [None] * len(ch)
    return out
