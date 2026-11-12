import subprocess, json
from PIL import Image
from autopilot import reel

def test_make_reel(tmp_path):
    ims = []
    for i, c in enumerate([(20, 120, 70), (240, 190, 40), (30, 120, 200)]):
        p = tmp_path / f"s{i}.jpg"; Image.new("RGB", (1080, 1350), c).save(p); ims.append(p)
    out = reel.make_reel(ims, tmp_path / "r.mp4", per_slide=1.0, fade=0.3, hold_last=0.5)
    j = json.loads(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=width,height,duration", "-of", "json", str(out)], capture_output=True, text=True).stdout)
    s = j["streams"][0]; assert (s["width"], s["height"]) == (1080, 1920) and float(s["duration"]) > 2
