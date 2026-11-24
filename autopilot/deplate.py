"""Removes the 'Arah Rides' box/text that some fleet photos carry where the number plate normally is.

Claude finds the box once per photo (the answer is kept in content/deplate.json), then OpenCV paints it out
from the surrounding bumper. The original photo is never changed: a cleaned copy is saved next to it in the cache.
No AI key (Gemini or Claude), or the AI cannot be reached: the photo is used as it is."""
import os, io, json, base64, logging
from pathlib import Path

log = logging.getLogger("deplate")
_CACHE = {}
PROMPT = ("This is a photo of a rental car. Some of our photos have an added rectangle, box, sticker or label with text "
          "(usually 'Arah Rides' or 'ArahRides.com') placed over the number plate, or added as a watermark. "
          "If there is such an added box or text, reply with ONLY this JSON: {\"boxes\": [[x0, y0, x1, y1], ...]} using fractions of the "
          "image width and height (0 to 1), covering the whole box and its text with a small margin. "
          "A normal number plate with only its registration number is NOT an added box: do not include it. "
          "If there is nothing added, reply {\"boxes\": []}.")

def _file():
    return Path(os.environ.get("AUTOPILOT_ROOT") or ".") / "content" / "deplate.json"

def _load():
    if not _CACHE:
        try: _CACHE.update(json.loads(_file().read_text()))
        except Exception: pass

def _save():
    try:
        _file().parent.mkdir(parents=True, exist_ok=True); _file().write_text(json.dumps(_CACHE, indent=0))
    except Exception:
        pass

def find_boxes(path, model=None):
    from . import vision as V
    if not V.ai_on():
        return None
    try:
        txt = V.ask([V._jpeg(path, 1024), PROMPT], 400) or ""
        import re as _re
        m = _re.search(r"\{.*\}", txt, _re.S)
        boxes = (json.loads(m.group(0)).get("boxes") or []) if m else []
        return [[float(v) for v in bx] for bx in boxes if len(bx) == 4]
    except Exception as e:
        log.warning("deplate: AI check failed for %s: %s", path, e)
        return None

def paint_out(path, boxes, out):
    import cv2, numpy as np
    img = cv2.imread(str(path)); h, w = img.shape[:2]
    mask = np.zeros((h, w), np.uint8)
    for x0, y0, x1, y1 in boxes:
        x0, x1 = sorted((max(0.0, x0), min(1.0, x1))); y0, y1 = sorted((max(0.0, y0), min(1.0, y1)))
        if (x1 - x0) * (y1 - y0) > 0.12:                 # far too big to be a plate box: leave the photo alone
            continue
        pad = int(0.006 * max(w, h)) + 2
        cv2.rectangle(mask, (int(x0 * w) - pad, int(y0 * h) - pad), (int(x1 * w) + pad, int(y1 * h) + pad), 255, -1)
    if not mask.any():
        return None
    res = cv2.inpaint(img, mask, 9, cv2.INPAINT_TELEA)
    k = max(9, (int(0.02 * max(w, h)) // 2) * 2 + 1)
    soft = cv2.GaussianBlur(res, (k, k), 0)                                    # smooth the streaks inside the patch
    feather = cv2.GaussianBlur(cv2.dilate(mask, np.ones((5, 5), np.uint8)), (k, k), 0).astype(np.float32)[..., None] / 255.0
    res = (soft * feather + res * (1 - feather)).astype(np.uint8)
    noise = np.random.default_rng(0).normal(0, 2.0, res.shape).astype(np.float32)   # a little grain so the patch matches the photo
    res = np.clip(res.astype(np.float32) + noise * feather, 0, 255).astype(np.uint8)
    cv2.imwrite(str(out), res, [cv2.IMWRITE_JPEG_QUALITY, 92])
    return out

def clean(path, key):
    """-> path of the photo to use (a cleaned copy when a box was found, otherwise the original path)."""
    _load(); path = Path(path); out = path.with_name(path.stem + "_clean.jpg")
    if key in _CACHE:
        boxes = _CACHE[key]
    else:
        boxes = find_boxes(path)
        if boxes is None:
            return path                                    # could not check: use as is, ask again next run
        _CACHE[key] = boxes; _save()
    if not boxes:
        return path
    if out.exists():
        return out
    try:
        return paint_out(path, boxes, out) or path
    except Exception as e:
        log.warning("deplate: could not paint out %s: %s", path, e); return path
