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
 "not usable": ("a screenshot, a document, a logo, text on a plain background or a selfie", dict(kind="skip")),
}
NAMES = list(L)
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

def embed_images(paths):
    from PIL import Image
    M = _model(); t = M["t"]; out = []
    for i in range(0, len(paths), 16):
        ims = [Image.open(p).convert("RGB") for p in paths[i:i + 16]]
        with t.no_grad():
            f = M["m"].get_image_features(**M["p"](images=ims, return_tensors="pt"))
        out.append(f / f.norm(dim=-1, keepdim=True))
    return t.cat(out) if out else None

def embed_labels():
    M = _model(); t = M["t"]
    with t.no_grad():
        f = M["m"].get_text_features(**M["p"](text=["a photo of " + L[n][0] for n in NAMES], return_tensors="pt", padding=True))
    return f / f.norm(dim=-1, keepdim=True)

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
