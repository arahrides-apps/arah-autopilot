"""HTML to JPEG with headless Chromium (Playwright, open source)."""
import tempfile, os
from pathlib import Path

_PW = {}

def page(w=1080, h=1350):
    """A new tab in ONE Chromium kept open for the whole run (starting Chromium for every post cost ~2 s each time)."""
    if "b" not in _PW:
        import atexit
        from playwright.sync_api import sync_playwright
        _PW["pw"] = sync_playwright().start()
        _PW["b"] = _PW["pw"].chromium.launch(args=["--allow-file-access-from-files"])
        atexit.register(close)
    return _PW["b"].new_page(viewport={"width": w, "height": h})

def close():
    try:
        if "b" in _PW: _PW.pop("b").close()
        if "pw" in _PW: _PW.pop("pw").stop()
    except Exception:
        pass

def render_all(jobs):
    """jobs: list of (html, height, out_path). Writes 1080-wide JPEGs."""
    pg = page(1080, 1350)
    try:
        for html_, h, out in jobs:
            Path(out).parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False, encoding="utf-8") as f:
                f.write(html_); name = f.name
            try:
                pg.set_viewport_size({"width": 1080, "height": h})
                pg.goto(Path(name).as_uri()); pg.wait_for_timeout(150)
                if "fonts.googleapis" in html_:                  # guide slides use web fonts: wait until they are loaded (falls back to local fonts if offline)
                    try: pg.evaluate("Promise.race([document.fonts.ready, new Promise(r => setTimeout(r, 4000))]).then(() => 1)")
                    except Exception: pass
                pg.screenshot(path=str(out), type="jpeg", quality=90, clip={"x": 0, "y": 0, "width": 1080, "height": h})
            finally:
                os.unlink(name)
    finally:
        pg.close()
