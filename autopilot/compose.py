"""Put a clean stock photo of a car model on a real Jamaican background photo.
Cut-out: rembg when installed (best), otherwise OpenCV GrabCut. A cut-out that looks wrong is rejected (the caller then uses one of our own car photos)."""
import numpy as np, cv2
from PIL import Image, ImageFilter, ImageEnhance

W, H = 1080, 1350

def _grabcut(im):
    a = np.array(im.convert("RGB")); h, w = a.shape[:2]
    sc = 640 / max(h, w); small = cv2.resize(a, (int(w * sc), int(h * sc))) if sc < 1 else a
    sh, sw = small.shape[:2]; mask = np.zeros((sh, sw), np.uint8)
    rect = (int(sw * .03), int(sh * .12), int(sw * .94), int(sh * .80))
    bg, fg = np.zeros((1, 65)), np.zeros((1, 65))
    cv2.grabCut(small, mask, rect, bg, fg, 4, cv2.GC_INIT_WITH_RECT)
    m = np.where((mask == 1) | (mask == 3), 255, 0).astype(np.uint8)
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8))
    n, lab, stats, _ = cv2.connectedComponentsWithStats(m)
    if n > 1:                                                           # keep the biggest blob: the car
        k = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA])); m = np.where(lab == k, 255, 0).astype(np.uint8)
    m = cv2.resize(m, (w, h), interpolation=cv2.INTER_LINEAR)
    return Image.fromarray(m)

def cutout(im):
    """Returns an RGBA image cropped to the car, or None when the cut-out does not look like a whole car."""
    try:
        from rembg import remove
        rgba = remove(im.convert("RGB")).convert("RGBA"); m = rgba.split()[3]
    except Exception:
        m = _grabcut(im); rgba = im.convert("RGBA"); rgba.putalpha(m)
    box = m.getbbox()
    if not box:
        return None
    x0, y0, x1, y1 = box; area = np.array(m).astype(bool).sum() / float(im.width * im.height)
    bw, bh = x1 - x0, y1 - y0
    if not (.12 < area < .85) or bw < im.width * .35 or not (1.3 < bw / max(bh, 1) < 4.2):   # a car is wide and fills a fair part of the photo
        return None
    ma = np.array(m) > 127
    cs, _ = cv2.findContours(ma.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    hull = cv2.contourArea(cv2.convexHull(max(cs, key=cv2.contourArea))) if cs else 0
    if hull <= 0 or ma.sum() / hull < .80:                     # ragged shape: people, a cut-off car or a messy background got in
        return None
    m2 = m.filter(ImageFilter.GaussianBlur(1.6)); rgba.putalpha(m2)
    return rgba.crop(box)

def _cover(im, w, h):
    s = max(w / im.width, h / im.height); im = im.resize((int(im.width * s) + 1, int(im.height * s) + 1), Image.LANCZOS)
    x, y = (im.width - w) // 2, (im.height - h) // 2
    return im.crop((x, y, x + w, y + h))

def compose(car_path, bg_path, out_path):
    car = cutout(Image.open(car_path))
    if car is None:
        return None
    bg = _cover(Image.open(bg_path).convert("RGB"), W, H)
    bg = ImageEnhance.Color(bg).enhance(1.08)
    cw = int(W * .90); ch = int(car.height * cw / car.width)
    if ch > H * .45:
        ch = int(H * .45); cw = int(car.width * ch / car.height)
    car = car.resize((cw, ch), Image.LANCZOS)
    x, y = (W - cw) // 2, int(H * .76) - ch
    # soft ground shadow
    sh = Image.new("L", (W, H), 0); a = np.array(sh)
    cv2.ellipse(a, (W // 2, y + ch - int(ch * .04)), (int(cw * .46), int(ch * .09)), 0, 0, 360, 170, -1)
    sh = Image.fromarray(a).filter(ImageFilter.GaussianBlur(22))
    bg = Image.composite(Image.new("RGB", (W, H), (10, 12, 10)), bg, sh.point(lambda v: int(v * .75)))
    # match the car's brightness to the scene a little
    tone = np.array(bg.crop((0, int(H * .55), W, int(H * .8)))).mean() / 255.0
    rgb = ImageEnhance.Brightness(car.convert("RGB")).enhance(.9 + .25 * tone)
    car = Image.merge("RGBA", (*rgb.split(), car.split()[3]))
    bg.paste(car, (x, y), car)
    bg.save(out_path, "JPEG", quality=90)
    return out_path
