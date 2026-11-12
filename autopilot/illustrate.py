"""When no free photo of a place or topic can be found, draw an accurate illustration of it (flat, bright, Jamaican colours) rather than
using a photo of somewhere else. It is flagged on the review page so a real photo can replace it."""
import math, random, hashlib
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter

W, H, SS = 1080, 1350, 2

KINDS = {   # what to draw for a place / topic
    "court": r"tennis|court|sport|marathon|run",
    "cliff": r"lover|leap|cliff|lighthouse|rick",
    "waterfall": r"fall|waterfall|dunn|reach|ys |y\.s|mayfield|somerset|konoko|river|rafting|martha brae|rio grande",
    "bamboo": r"bamboo|holland|tunnel|road trip|highway|road\b|drive|countryside|route",
    "beach": r"beach|negril|seven mile|doctor|treasure|bay\b|cay\b|sea\b|lagoon|pelican|frenchman|winnifred|boston",
    "hills": r"mandeville|blue mountain|hills|mountain|cockpit|coffee|manchester|christiana|holywell|newcastle",
    "city": r"kingston|downtown|devon|art walk|emancipation|bob marley|trench|city|half moon|montego|airport|hip strip",
}
import re
def kind_for(text):
    t = (text or "").lower()
    for k, rx in KINDS.items():
        if re.search(rx, t):
            return k
    return "hills"

def _sky(d, top, bot):
    for y in range(H * SS):
        t = y / (H * SS * 0.62)
        t = min(1, t)
        c = tuple(int(top[i] + (bot[i] - top[i]) * t) for i in range(3))
        d.line([(0, y), (W * SS, y)], fill=c)

def _ridge(d, base, amp, col, rnd, freq=1.0, phase=0.0):
    pts = [(0, H * SS)]
    for x in range(0, W * SS + 8, 8):
        y = base * SS - amp * SS * (0.6 * math.sin(x / (W * SS) * math.pi * 2 * freq + phase) + 0.4 * math.sin(x / (W * SS) * math.pi * 5 * freq + phase * 2))
        pts.append((x, y))
    pts.append((W * SS, H * SS)); d.polygon(pts, fill=col)

def _palm(d, x, y, h, lean=0.2, col=(34, 95, 52)):
    x, y, h = x * SS, y * SS, h * SS
    tx, ty = x + lean * h, y - h
    d.line([(x, y), ((x + tx) / 2 + lean * h * .25, (y + ty) / 2), (tx, ty)], fill=(92, 62, 38), width=int(14 * SS * h / (300 * SS)) + 6)
    for a in range(-80, 260, 40):
        r = math.radians(a); L = h * .45
        ex, ey = tx + math.cos(r) * L, ty - math.sin(r) * L * .55 + L * .25
        d.line([(tx, ty), ((tx + ex) / 2, (ty + ey) / 2 - L * .2), (ex, ey)], fill=col, width=int(10 * SS * h / (300 * SS)) + 4)

def _sun(d, x, y, r):
    d.ellipse([(x - r) * SS, (y - r) * SS, (x + r) * SS, (y + r) * SS], fill=(255, 214, 102))

def draw(kind, seed=0):
    rnd = random.Random(seed)
    im = Image.new("RGB", (W * SS, H * SS)); d = ImageDraw.Draw(im)
    sunset = rnd.random() < 0.5
    top, bot = ((255, 150, 80), (255, 216, 140)) if sunset else ((74, 170, 235), (190, 232, 250))
    _sky(d, top, bot)
    _sun(d, rnd.choice([280, 800]), 330, 90)
    if kind == "beach":
        _ridge(d, 760, 40, (52, 130, 70), rnd, .6)
        d.rectangle([0, 820 * SS, W * SS, H * SS], fill=(20, 170, 190))
        for i in range(9):
            y = 840 + i * 26; d.line([(0, y * SS), (W * SS, (y + 6) * SS)], fill=(120, 220, 230), width=4 * SS)
        d.polygon([(0, 1010 * SS), (W * SS, 960 * SS), (W * SS, H * SS), (0, H * SS)], fill=(244, 226, 170))
        _palm(d, 140, 1040, 430, .25); _palm(d, 930, 1010, 380, -.2); _palm(d, 240, 1060, 300, .1)
    elif kind == "waterfall":
        _ridge(d, 600, 120, (36, 104, 58), rnd, .8, 1); _ridge(d, 720, 80, (26, 84, 48), rnd, 1.2, 2)
        for i in range(4):
            x0 = 320 + i * 120
            d.polygon([(x0 * SS, 520 * SS), ((x0 + 150) * SS, 520 * SS), ((x0 + 210) * SS, 1000 * SS), ((x0 - 40) * SS, 1000 * SS)], fill=(235, 248, 252) if i % 2 == 0 else (206, 236, 246))
        d.ellipse([200 * SS, 940 * SS, 880 * SS, 1100 * SS], fill=(40, 170, 190))
        d.rectangle([0, 1040 * SS, W * SS, H * SS], fill=(30, 110, 70))
        _palm(d, 110, 1000, 420, .2); _palm(d, 980, 980, 360, -.25)
    elif kind == "bamboo":
        _ridge(d, 700, 90, (40, 110, 62), rnd, .7)
        d.polygon([(380 * SS, 800 * SS), (700 * SS, 800 * SS), (1200 * SS, H * SS), (-120 * SS, H * SS)], fill=(78, 78, 84))
        for k in range(8):
            y = 820 + k * k * 9; d.line([(540 * SS, y * SS), (540 * SS, (y + 16 + k * 6) * SS)], fill=(250, 214, 80), width=(3 + k) * SS)
        for side in (-1, 1):
            for j in range(9):
                x = 540 + side * (250 + j * 36) ; top_y = 120 + j * 6
                d.line([(x * SS, 1000 * SS), ((540 + side * (30 + j * 8)) * SS, top_y * SS)], fill=(108, 160, 60), width=18 * SS)
        d.polygon([(0, 0), (W * SS, 0), (W * SS, 200 * SS), (540 * SS, 130 * SS), (0, 200 * SS)], fill=(54, 120, 48))
    elif kind == "city":
        _ridge(d, 640, 150, (60, 122, 90), rnd, .6, 1)
        for i in range(10):
            x = i * 115; h = rnd.randint(160, 420); c = rnd.choice([(250, 196, 70), (244, 120, 90), (70, 170, 190), (240, 240, 230), (130, 190, 110)])
            d.rectangle([x * SS, (1000 - h) * SS, (x + 100) * SS, 1000 * SS], fill=c)
            for wy in range(1000 - h + 24, 980, 46):
                for wx in range(x + 14, x + 90, 30): d.rectangle([wx * SS, wy * SS, (wx + 14) * SS, (wy + 22) * SS], fill=(40, 70, 90))
        d.rectangle([0, 1000 * SS, W * SS, H * SS], fill=(84, 84, 90)); _palm(d, 90, 1010, 380, .15); _palm(d, 990, 1010, 340, -.15)
    elif kind == "cliff":
        d.rectangle([0, 900 * SS, W * SS, H * SS], fill=(20, 150, 190))
        for i in range(8):
            y = 930 + i * 38; d.line([(0, y * SS), (W * SS, (y + 8) * SS)], fill=(120, 220, 230), width=4 * SS)
        d.polygon([(0, 420 * SS), (520 * SS, 380 * SS), (640 * SS, 700 * SS), (560 * SS, 1000 * SS), (0, 1040 * SS)], fill=(150, 120, 96))
        d.polygon([(0, 420 * SS), (520 * SS, 380 * SS), (560 * SS, 460 * SS), (0, 520 * SS)], fill=(52, 130, 70))
        d.rectangle([380 * SS, 300 * SS, 396 * SS, 390 * SS], fill=(240, 240, 240)); d.polygon([(370 * SS, 300 * SS), (406 * SS, 300 * SS), (388 * SS, 270 * SS)], fill=(210, 60, 50))
        _palm(d, 140, 430, 300, .15)
    elif kind == "court":
        _ridge(d, 560, 100, (50, 120, 80), rnd, .5)
        d.polygon([(120 * SS, 1000 * SS), (960 * SS, 1000 * SS), (1100 * SS, H * SS), (-20 * SS, H * SS)], fill=(46, 140, 96))
        d.line([(120 * SS, 1000 * SS), (-20 * SS, H * SS)], fill="white", width=6 * SS); d.line([(960 * SS, 1000 * SS), (1100 * SS, H * SS)], fill="white", width=6 * SS)
        d.line([(540 * SS, 1000 * SS), (540 * SS, H * SS)], fill="white", width=5 * SS); d.rectangle([160 * SS, 900 * SS, 920 * SS, 1000 * SS], outline="white", width=4 * SS)
        d.line([(160 * SS, 950 * SS), (920 * SS, 950 * SS)], fill="white", width=3 * SS)
        _palm(d, 90, 880, 420, .2); _palm(d, 990, 880, 400, -.2)
    else:   # hills
        _ridge(d, 560, 170, (96, 150, 120), rnd, .5, 1); _ridge(d, 700, 140, (56, 122, 78), rnd, .8, 2); _ridge(d, 880, 110, (34, 96, 58), rnd, 1.1, 3)
        d.rectangle([0, 1100 * SS, W * SS, H * SS], fill=(28, 86, 52)); _palm(d, 150, 1120, 400, .2); _palm(d, 920, 1100, 340, -.2)
    im = im.resize((W, H), Image.LANCZOS)
    return im

def make(text, dest, label=""):
    kind = kind_for(text)
    seed = int(hashlib.md5((text or "").encode()).hexdigest()[:6], 16)
    Path(dest).parent.mkdir(parents=True, exist_ok=True)
    draw(kind, seed).save(dest, "JPEG", quality=90)
    return kind
