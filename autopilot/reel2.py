"""Hook Reels: built from the post's real photos, not its slides.

What makes them stop the scroll (the patterns that do well on Reels right now):
  - a hook line on screen in the first second, bigger than everything else
  - fast cuts (about 1.3 s a shot) with movement on every shot: push in, pull out, pan
  - one short caption per shot that pops in (slides up and fades in), in the bold boxed style people know from Reels/TikTok
  - punchy transitions (white flash, slide, zoom) instead of slow crossfades
  - a clean end card with the call to action, held long enough to read
  - music when you add tracks to content/music/ (Instagram's own trending sounds cannot be attached through the posting API)
"""
from pathlib import Path
import html as H, re, subprocess, random, datetime as dt
from .config import ROOT

FPS = 30
W, HH = 1080, 1920
Y, K, C = "#E8A93A", "#1A1F1C", "#FFFFFF"
MUSIC = ROOT / "content" / "music"

def _clean(t, n=60):
    t = re.sub(r"[\U0001F300-\U0001FAFF☀-➿]", "", str(t or "")).strip()
    t = re.sub(r"\s+", " ", t)
    return t if len(t) <= n else t[:n].rsplit(" ", 1)[0] + "…"

def _caption_html(text, hook, idx, total):
    words = H.escape(text).split(" ")
    # highlight the last two words in yellow (the punchline), like the bold caption templates on Reels
    cut = max(1, len(words) - 2)
    body = " ".join(words[:cut]) + (" <span class=hl>" + " ".join(words[cut:]) + "</span>" if len(words) > 1 else "")
    size = 104 if hook else 82
    top = 760 if hook else 1080
    dots = "" if hook else "".join(f"<i class='{'on' if i == idx else ''}'></i>" for i in range(total))
    return f"""<!doctype html><html><head><meta charset=utf-8><style>*{{margin:0;box-sizing:border-box}}
body{{width:{W}px;height:{HH}px;background:transparent;font-family:'Poppins','Inter','Arial Black',sans-serif;position:relative;overflow:hidden}}
.shade{{position:absolute;left:0;right:0;top:{top - 260}px;height:900px;background:radial-gradient(ellipse at 50% 50%,rgba(0,0,0,.42),rgba(0,0,0,0) 70%)}}
.cap{{position:absolute;left:70px;right:70px;top:{top}px;text-align:center;color:{C};font-weight:900;font-size:{size}px;line-height:1.08;
 text-shadow:0 6px 0 rgba(0,0,0,.55),0 0 28px rgba(0,0,0,.55);-webkit-text-stroke:3px rgba(0,0,0,.65);letter-spacing:-1px}}
.hl{{color:{K};background:{Y};-webkit-text-stroke:0;text-shadow:none;padding:0 14px;border-radius:16px;box-decoration-break:clone;-webkit-box-decoration-break:clone}}
.brand{{position:absolute;left:0;right:0;top:150px;text-align:center;color:{C};font-weight:800;font-size:34px;letter-spacing:6px;text-shadow:0 3px 12px rgba(0,0,0,.6)}}
.dots{{position:absolute;left:0;right:0;top:1540px;display:flex;gap:14px;justify-content:center}}
.dots i{{width:16px;height:16px;border-radius:50%;background:rgba(255,255,255,.45)}}.dots i.on{{background:{Y};width:46px;border-radius:10px}}
</style></head><body><div class=shade></div><div class=brand>ARAHRIDES.COM</div><div class=cap>{body}</div><div class=dots>{dots}</div></body></html>"""

def render_captions(lines, outdir):
    from playwright.sync_api import sync_playwright
    outdir = Path(outdir); outdir.mkdir(parents=True, exist_ok=True); out = []
    with sync_playwright() as pw:
        br = pw.chromium.launch(); pg = br.new_page(viewport={"width": W, "height": HH})
        for i, t in enumerate(lines):
            f = outdir / f"cap_{i}.png"
            pg.set_content(_caption_html(t, i == 0, i - 1, len(lines) - 1)); pg.wait_for_timeout(120)
            pg.screenshot(path=str(f), omit_background=True); out.append(f)
        br.close()
    return out

MOVES = [  # (zoom expression, x expression, y expression) over N frames: push in, pull out, pan right, pan left, push to top
    ("1.0+0.14*on/N", "iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)"),
    ("1.16-0.14*on/N", "iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)"),
    ("1.14", "(iw-iw/zoom)*on/N", "ih/2-(ih/zoom/2)"),
    ("1.14", "(iw-iw/zoom)*(1-on/N)", "ih/2-(ih/zoom/2)"),
    ("1.0+0.12*on/N", "iw/2-(iw/zoom/2)", "(ih-ih/zoom)*0.25"),
]
TRANS = ["fadewhite", "slideleft", "zoomin", "smoothup", "slideright", "circleopen"]

def pick_music(seed):
    tracks = sorted(MUSIC.glob("*.mp3")) + sorted(MUSIC.glob("*.m4a")) if MUSIC.exists() else []
    return tracks[seed % len(tracks)] if tracks else None

def make_hook_reel(photos, lines, end_img, out, seed=0, hook_s=2.0, beat_s=1.35, end_s=2.8, T=0.25):
    """photos: real photo files (any size). lines: [hook, caption 1, caption 2, ...] (one per photo). end_img: the post's last slide (call to action)."""
    n = min(len(photos), len(lines), 6)
    photos, lines = [Path(p) for p in photos[:n]], [_clean(l) for l in lines[:n]]
    out = Path(out); out.parent.mkdir(parents=True, exist_ok=True)
    caps = render_captions(lines, out.parent / (out.stem + "_caps"))
    rng = random.Random(seed)
    durs = [hook_s] + [beat_s] * (n - 1) + [end_s]
    cmd = ["ffmpeg", "-y", "-loglevel", "error"]
    for i in range(n):
        cmd += ["-loop", "1", "-t", f"{durs[i]:.2f}", "-framerate", str(FPS), "-i", str(photos[i])]
    for i in range(n):
        cmd += ["-loop", "1", "-t", f"{durs[i]:.2f}", "-framerate", str(FPS), "-i", str(caps[i])]
    cmd += ["-loop", "1", "-t", f"{end_s:.2f}", "-framerate", str(FPS), "-i", str(end_img)]
    music = pick_music(seed)
    if music:
        cmd += ["-i", str(music)]
    f = []
    moves = MOVES[:]; rng.shuffle(moves); moves = [MOVES[0]] + moves      # the hook always pushes in
    for i in range(n):
        N = int(durs[i] * FPS); z, x, y = (m.replace("/N", f"/{N}") for m in moves[i % len(moves)])
        f.append(f"[{i}:v]scale={int(W*1.25)}:{int(HH*1.25)}:force_original_aspect_ratio=increase,crop={int(W*1.25)}:{int(HH*1.25)},setsar=1,"
                 f"zoompan=z='{z}':x='{x}':y='{y}':d=1:s={W}x{HH}:fps={FPS},eq=contrast=1.06:saturation=1.12,trim=duration={durs[i]:.2f},setpts=PTS-STARTPTS[p{i}]")
        f.append(f"[{n + i}:v]format=rgba,fade=in:st=0.05:d=0.2:alpha=1,setpts=PTS-STARTPTS[c{i}]")
        f.append(f"[p{i}][c{i}]overlay=x=0:y='if(lt(t,0.3),(0.3-t)*260,0)':shortest=1,format=yuv420p[b{i}]")
    e = 2 * n
    f.append(f"[{e}:v]split[e1][e2];[e1]scale={W}:{HH}:force_original_aspect_ratio=increase,crop={W}:{HH},boxblur=30:2,eq=brightness=-0.12[eb];"
             f"[e2]scale={W}:-2[ef];[eb][ef]overlay=x=0:y=(H-h)/2,zoompan=z='1.0+0.04*on/{int(end_s*FPS)}':d=1:s={W}x{HH}:fps={FPS},trim=duration={end_s:.2f},setpts=PTS-STARTPTS,format=yuv420p[b{n}]")
    last, t_acc = "b0", durs[0]; t0 = rng.randrange(len(TRANS))
    for i in range(1, n + 1):
        tr = TRANS[(t0 + i) % len(TRANS)] if i < n else "fade"
        off = t_acc - T * i
        f.append(f"[{last}][b{i}]xfade=transition={tr}:duration={T}:offset={off:.2f}[x{i}]")
        last = f"x{i}"; t_acc += durs[i]
    total = sum(durs) - T * n
    cmd += ["-filter_complex", ";".join(f), "-map", f"[{last}]"]
    if music:
        a = 2 * n + 1
        cmd += ["-map", f"{a}:a", "-af", f"afade=t=in:d=0.4,afade=t=out:st={total - 0.8:.2f}:d=0.8", "-c:a", "aac", "-b:a", "160k"]
    cmd += ["-t", f"{total:.2f}", "-r", str(FPS), "-c:v", "libx264", "-preset", "veryfast", "-crf", "21", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(out)]
    subprocess.run(cmd, check=True, timeout=600)
    return out, bool(music)
