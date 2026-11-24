"""Reels: turns a finished carousel into a short vertical video (slow push-in on every slide, soft cross-fades), and rotates in the
animated Arah Rides ads from content/reels/. Reels get far more reach than still carousels. Needs ffmpeg (already on GitHub's runners)."""
import re
import os, shutil, subprocess, logging, hashlib
from pathlib import Path
from . import queue as Q

log = logging.getLogger("reel")
W, H, FPS = 1080, 1920, 25

def _have_ffmpeg():
    return shutil.which("ffmpeg") is not None

MOTIONS = {  # per-slide camera moves: z = zoom expression, x/y = pan expression
    "in":    ("1+0.07*on/{n}", "iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)"),
    "out":   ("1.09-0.07*on/{n}", "iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)"),
    "left":  ("1.08", "(iw-iw/zoom)*(1-on/{n})", "ih/2-(ih/zoom/2)"),
    "right": ("1.08", "(iw-iw/zoom)*on/{n}", "ih/2-(ih/zoom/2)"),
    "up":    ("1.08", "iw/2-(iw/zoom/2)", "(ih-ih/zoom)*(1-on/{n})"),
}
STYLES = {"classic": ["in"], "dynamic": ["in", "right", "out", "left", "up"], "punchy": ["in", "out"]}

def make_reel(images, out, per_slide=2.4, fade=0.4, hold_last=1.8, style="classic"):
    """images: list of image paths (1080x1350 slides). Writes an H.264 MP4, 1080x1920, no audio (add trending sound in the Instagram app)."""
    n = len(images); out = Path(out); out.parent.mkdir(parents=True, exist_ok=True)
    cmd = ["ffmpeg", "-y", "-loglevel", "error"]
    for i, im in enumerate(images):
        d = per_slide + fade + (hold_last if i == n - 1 else 0)
        cmd += ["-loop", "1", "-t", f"{d:.2f}", "-framerate", str(FPS), "-i", str(im)]
    f = []
    for i in range(n):
        frames = int((per_slide + fade + (hold_last if i == n - 1 else 0)) * FPS)
        mz, mx, my = MOTIONS[STYLES.get(style, STYLES["classic"])[i % len(STYLES.get(style, STYLES["classic"]))]]
        mz, mx, my = (e.replace("{n}", str(frames)) for e in (mz, mx, my))
        f.append(f"[{i}:v]split[b{i}][f{i}];"
                 f"[b{i}]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},boxblur=40:4,eq=brightness=-0.08[bg{i}];"
                 f"[f{i}]scale=2160:-2,zoompan=z='{mz}':x='{mx}':y='{my}':d=1:s={W}x1350:fps={FPS}[fg{i}];"
                 f"[bg{i}][fg{i}]overlay=0:(H-h)/2,format=yuv420p,setsar=1[v{i}]")
    last, t = "v0", per_slide
    for i in range(1, n):
        f.append(f"[{last}][v{i}]xfade=transition=fade:duration={fade}:offset={t:.2f}[x{i}]"); last = f"x{i}"; t += per_slide
    cmd += ["-filter_complex", ";".join(f), "-map", f"[{last}]", "-c:v", "libx264", "-crf", "20", "-preset", "veryfast",
            "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(out)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError("ffmpeg: " + r.stderr[-300:])
    return out

REEL_TYPES = ("place", "experience", "trip", "moment", "car_hero", "tip", "review", "chat", "qa", "brand", "engage", "list", "offer", "trust", "versus", "carousel", "journey", "spotlight", "deal")
KEEP_CAROUSEL = ("deposits", "offer", "review", "versus", "list", "carousel", "qa", "trust")   # these read best as swipeable carousels

def make_clip_reel(clip, end_card, out, seconds=9, hold=2.0):
    """A supplied video clip (any size) cropped to 1080x1920 and trimmed, then the slide with the booking button held at the end."""
    out = Path(out); out.parent.mkdir(parents=True, exist_ok=True)
    fc = (f"[0:v]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},fps={FPS},setsar=1,format=yuv420p[a];"
          f"[1:v]split[b][f];[b]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},boxblur=40:4,eq=brightness=-0.08[bg];"
          f"[f]scale={W}:-2[fg];[bg][fg]overlay=0:(H-h)/2,fps={FPS},setsar=1,format=yuv420p[e];[a][e]concat=n=2:v=1:a=0[v]")
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-t", str(seconds), "-i", str(clip), "-loop", "1", "-t", str(hold), "-framerate", str(FPS), "-i", str(end_card),
           "-filter_complex", fc, "-map", "[v]", "-c:v", "libx264", "-crf", "22", "-preset", "veryfast", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(out)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError("ffmpeg: " + r.stderr[-300:])
    return out

def cfg_web_video():
    try:
        from .config import load
        return load().get("reels", {}).get("web_video", True)
    except Exception:
        return True

CTA_LINES = ["Book in minutes on ArahRides.com", "Airport pickup: Montego Bay, Kingston, Ocho Rios", "Pay with Klarna, Affirm, Apple Pay or Google Pay", "WhatsApp Winston, 24/7"]
GENERIC_CLIPS = ["Jamaica road", "Jamaica coastal road drive", "Jamaica car driving", "Jamaica highway"]      # filler for car posts only: driving, which is what a rental is

def _hook(p, out, end_img, date):
    """The scroll-stopping Reel: real photos and real video clips, hook line first, fast cuts, pop-in captions, music, end card.
    Shots are filled with video clips (your Drive clips first, then Pexels, then Pixabay) that fit each caption; car posts keep the car photo as the hook and add Jamaica scenery clips.
    False only when fewer than 3 shots could be found."""
    from . import reel2
    raw = [x for x in p.get("raw", []) if Path(x).exists()]
    first = re.split(r"[\U0001F300-\U0001FAFF\u2600-\u27BF]|\n", p.get("copy_text") or p.get("alt") or "")[0].strip()
    lines = [p.get("hook_line") or first] + list(p.get("beat_lines", []))
    carpost = p.get("type") in ("deal", "deposits", "car_hero")
    target = max(4, min(6, len(lines)))
    if carpost:                                                      # car posts: the car photos carry the Reel, plus at most 2 Jamaica clips
        target = max(3, min(len(raw) + 2, 5))
    i = 0
    while len(lines) < target:
        lines.append(CTA_LINES[i % len(CTA_LINES)]); i += 1
    shots = raw[:target]
    nclips = 0
    if cfg_web_video():
        from . import webvideo as WV, story as S, themes as TH
        used = set()
        for k in range(target):
            if carpost and k == 0:
                continue                                             # a car post always opens on our own car photo
            have_photo = k < len(shots)
            if have_photo and k % 2 == 0:
                continue                                             # alternate: photo, clip, photo, clip... (more video, fewer stills)
            t = f"{lines[k]} {first}"
            pq = S.place_queries(t)
            qs = (pq + TH.slide_queries(t)) if not carpost else []
            qs = qs or S.place_queries(p.get("copy_text", ""))
            got = WV.find(qs, t, date, want=1, used=used, strict=bool(pq) and not carpost) if qs else []
            if not got and carpost:                                    # car posts only: a Jamaica driving clip (other posts never get a clip that does not fit their words)
                got = WV.find(GENERIC_CLIPS, "a car driving on a road in Jamaica", date, want=1, used=used)
            if got:
                used.add(str(got[0])); nclips += 1
                p.setdefault("clips", []).append(WV.KEYS.get(str(got[0]), ""))      # so a clip from a draft that is thrown away can be used again
                if have_photo: shots[k] = str(got[0])
                else: shots.append(str(got[0]))
    if len(shots) < 3:
        return False
    seed = int(hashlib.md5((str(date) + p["id"]).encode()).hexdigest()[:6], 16)
    try:                                                         # a branded end frame: logo, the offer, book in minutes, Winston, payment options
        from . import promo_art as _A
        if not str(end_img).endswith("end.png"):
            head = lines[0] if len(lines[0]) <= 48 else lines[0][:46].rsplit(" ", 1)[0] + "…"
            end_img = _A.render_reel_end(head, "Choose the car you want to drive.", Path(out).with_name(Path(out).stem + "_end.png"))
    except Exception as e:
        log.warning("branded end card failed, using the last slide: %s", e) if "log" in globals() else None
    _o, music = reel2.make_hook_reel(shots, lines[:len(shots)], end_img, out, seed=seed)
    p["reel_kind"] = f"hook Reel: {len(shots) - nclips} photos + {nclips} video clips, fast cuts, captions" + (", instrumental music" if music else ", no music")
    if nclips:
        p.setdefault("flags", []).append(f"Reel includes {nclips} real video clip(s) from Pixabay (free licence), checked by Claude against the words")
    if not music:
        p.setdefault("flags", []).append("Silent Reel: no music could be fetched this run. Add instrumental tracks (mp3) to content/music/, or post it from the Instagram app with a trending sound.")
    else:
        credit = getattr(reel2.make_hook_reel, "credit", None)
        if credit and credit not in p.get("caption", ""):
            parts = p["caption"].rstrip().split("\n\n")
            at = len(parts) - 1 if parts and parts[-1].strip().startswith("#") else len(parts)
            parts.insert(at, credit); p["caption"] = "\n\n".join(parts)[:2200]
        p.setdefault("flags", []).append("Music: " + (credit.replace("🎵 Music: ", "") if credit else "royalty-free instrumental (no credit needed)"))
    return True

def _fresh_file(files, date, peek=False):
    """Strict no-reuse for ready-made videos: a file not used in the last 90 days, or None (the post then becomes a photo slideshow)."""
    from . import promo as _P
    k = _P._pick([str(f) for f in files], date)
    if k and not peek: _P.note_use(k, date)
    return Path(k) if k else None

def add_reels(cfg, posts, date):
    try:                                                       # instrumental, commercial-use music for every Reel (Openverse, no key needed)
        from . import music as _M
        _n = cfg.get("reels", {}).get("music_tracks", 20)
        if _M.fetch(_n) < _n:
            _M.fetch_ccmixter(_n)
    except Exception as _e:
        log.warning("music fetch skipped: %s", _e) if "log" in globals() else None
    """Marks some of the day's posts to go out as Reels. Returns notes. A reel replaces that slot's carousel on Instagram; the review page still shows the slides."""
    rc = cfg.get("reels") or {}
    n = rc.get("per_day", 0)
    if (os.environ.get("PYTEST_CURRENT_TEST") or os.environ.get("AUTOPILOT_NOW")) and not os.environ.get("ARAH_TEST_REELS"):
        return []                                  # the test suite checks reels on their own (tests/test_reel.py); other tests stay fast
    if not n or not _have_ffmpeg():
        return ["Reels skipped: ffmpeg not found"] if n else []
    notes = []; lib = sorted(f for d in ("content/reels", "reels") for f in (Q.ROOT / d).glob("*_9x16.mp4")) if rc.get("library", True) else []
    cand = [p for p in posts if len(p.get("images", [])) >= 4 and p["type"] in REEL_TYPES and not p.get("single") and not any("Illustration" in f for f in p.get("flags", []))]
    keep = int(rc.get("carousels_per_day", 2))
    prom = [p for p in posts if p.get("promo") and len(p.get("images", [])) >= 2]       # the sale: every promo post is a Reel
    first = prom + [p for p in cand if p.get("event_reel_src") and p not in prom] + [p for p in cand if p.get("event_reel_flag") and not p.get("event_reel_src") and p not in prom]
    keepers = [p for p in cand if p["type"] in KEEP_CAROUSEL and p not in first][:keep]
    rest = [p for p in cand if p not in first and p not in keepers]
    keepers += rest[:max(0, keep - len(keepers))]                                  # not enough carousel-type posts: keep a few others as carousels
    pick = (first + [p for p in cand if p not in first and p not in keepers])[:n]
    clips = sorted((Q.ROOT / "content" / "reels").glob("clip_*.mp4")) if rc.get("clips", True) else []
    used_lib = False
    for p in pick:
        rel = p["images"][0].rsplit("_", 1)[0] + ".mp4"
        try:
            if p.get("promo"):
                from . import promo as _P, promo_art as _A
                pr = _P.active(date); k = prom.index(p) if p in prom else 0
                got = _P.get_clip(cfg, date, k) if (pr and (k + date.toordinal()) % 2 == 0) else None        # promo Reels alternate day by day: video clip, then photo slideshow        # the 1st promo Reel of the day is on a video clip, the 2nd is a photo slideshow
                if got:
                    _P.make_promo_reel(got[0], pr, Q.DOCS / rel, start=got[1]); _P.note_use(got[2], date); p["reel_kind"] = "sale video (Drive clip)"
                else:
                    _, endcard = _A.render(pr, Q.DOCS / "media" / "promo")
                    if not _hook(p, Q.DOCS / rel, endcard, date):
                        make_reel([Q.DOCS / i for i in p["images"]] + [endcard], Q.DOCS / rel, per_slide=2.0, style=("dynamic", "punchy")[(date.toordinal() + k) % 2])
                        p["reel_kind"] = "sale slideshow (photos + code card)"
            elif p.get("event_reel_src"):
                shutil.copy(p["event_reel_src"], Q.DOCS / rel); p["reel_kind"] = "event video"
            elif clips and _fresh_file(clips, date, peek=True) and p["type"] in ("tip", "chat", "qa", "brand", "engage", "trust") and int(hashlib.md5((p["id"]).encode()).hexdigest()[:4], 16) % 2 == 0:
                _c = _fresh_file(clips, date)
                make_clip_reel(_c, Q.DOCS / p["images"][-1], Q.DOCS / rel); p["reel_kind"] = "video clip"
            elif lib and not used_lib and _fresh_file(lib, date, peek=True) and p["type"] in ("moment", "chat", "tip"):      # one animated ad per day replaces a plain slideshow
                shutil.copy(_fresh_file(lib, date), Q.DOCS / rel); used_lib = True; p["reel_kind"] = "animated ad"
            elif _hook(p, Q.DOCS / rel, Q.DOCS / p["images"][-1], date):
                pass
            else:
                seed = int(hashlib.md5((str(date) + p["id"]).encode()).hexdigest()[:4], 16)
                sty = ("dynamic", "punchy", "dynamic", "classic")[seed % 4]
                make_reel([Q.DOCS / i for i in p["images"]], Q.DOCS / rel, per_slide=1.9 if sty == "punchy" else 2.4, style=sty)
                p["reel_kind"] = "animated slideshow (%s)" % sty
            p["reel"] = rel
            p.setdefault("flags", []).append("Goes out as a Reel (%s)." % p["reel_kind"])
        except Exception as e:
            notes.append("Reel for %s failed, stays a carousel: %s" % (p["id"], str(e)[:120]))
    return notes
