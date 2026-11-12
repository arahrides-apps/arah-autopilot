"""Reels: turns a finished carousel into a short vertical video (slow push-in on every slide, soft cross-fades), and rotates in the
animated Arah Rides ads from content/reels/. Reels get far more reach than still carousels. Needs ffmpeg (already on GitHub's runners)."""
import os, shutil, subprocess, logging, hashlib
from pathlib import Path
from . import queue as Q

log = logging.getLogger("reel")
W, H, FPS = 1080, 1920, 25

def _have_ffmpeg():
    return shutil.which("ffmpeg") is not None

def make_reel(images, out, per_slide=2.4, fade=0.4, hold_last=1.8):
    """images: list of image paths (1080x1350 slides). Writes an H.264 MP4, 1080x1920, no audio (add trending sound in the Instagram app)."""
    n = len(images); out = Path(out); out.parent.mkdir(parents=True, exist_ok=True)
    cmd = ["ffmpeg", "-y", "-loglevel", "error"]
    for i, im in enumerate(images):
        d = per_slide + fade + (hold_last if i == n - 1 else 0)
        cmd += ["-loop", "1", "-t", f"{d:.2f}", "-framerate", str(FPS), "-i", str(im)]
    f = []
    for i in range(n):
        frames = int((per_slide + fade + (hold_last if i == n - 1 else 0)) * FPS)
        f.append(f"[{i}:v]split[b{i}][f{i}];"
                 f"[b{i}]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},boxblur=40:4,eq=brightness=-0.08[bg{i}];"
                 f"[f{i}]scale=2160:-2,zoompan=z='1+0.07*on/{frames}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:s={W}x1350:fps={FPS}[fg{i}];"
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

REEL_TYPES = ("place", "experience", "trip", "moment", "car_hero", "tip", "review", "chat")

def add_reels(cfg, posts, date):
    """Marks some of the day's posts to go out as Reels. Returns notes. A reel replaces that slot's carousel on Instagram; the review page still shows the slides."""
    rc = cfg.get("reels") or {}
    n = rc.get("per_day", 0)
    if (os.environ.get("PYTEST_CURRENT_TEST") or os.environ.get("AUTOPILOT_NOW")) and not os.environ.get("ARAH_TEST_REELS"):
        return []                                  # the test suite checks reels on their own (tests/test_reel.py); other tests stay fast
    if not n or not _have_ffmpeg():
        return ["Reels skipped: ffmpeg not found"] if n else []
    notes = []; lib = sorted((Q.ROOT / "content" / "reels").glob("*_9x16.mp4")) if rc.get("library", True) else []
    cand = [p for p in posts if len(p.get("images", [])) >= 4 and p["type"] in REEL_TYPES and not p.get("single")]
    step = max(1, len(cand) // max(1, n)); pick = cand[::step][:n]
    used_lib = False
    for p in pick:
        rel = p["images"][0].rsplit("_", 1)[0] + ".mp4"
        try:
            if lib and not used_lib and p["type"] in ("moment", "chat", "tip"):      # one animated ad per day replaces a plain slideshow
                seed = int(hashlib.md5(str(date).encode()).hexdigest()[:4], 16)
                shutil.copy(lib[seed % len(lib)], Q.DOCS / rel); used_lib = True; p["reel_kind"] = "animated ad"
            else:
                make_reel([Q.DOCS / i for i in p["images"]], Q.DOCS / rel); p["reel_kind"] = "slideshow reel"
            p["reel"] = rel
            p.setdefault("flags", []).append("Goes out as a Reel (%s): approve as usual. Add trending audio in Instagram if you like." % p["reel_kind"])
        except Exception as e:
            notes.append("Reel for %s failed, stays a carousel: %s" % (p["id"], str(e)[:120]))
    return notes
