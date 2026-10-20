"""HTML to JPEG with headless Chromium (Playwright, open source)."""
import tempfile, os
from pathlib import Path

def render_all(jobs):
    """jobs: list of (html, height, out_path). Writes 1080-wide JPEGs."""
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.launch(args=["--allow-file-access-from-files"])
        pg = b.new_page(viewport={"width": 1080, "height": 1350})
        for html_, h, out in jobs:
            Path(out).parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False, encoding="utf-8") as f:
                f.write(html_); name = f.name
            try:
                pg.set_viewport_size({"width": 1080, "height": h})
                pg.goto(Path(name).as_uri()); pg.wait_for_timeout(150)
                pg.screenshot(path=str(out), type="jpeg", quality=90, clip={"x": 0, "y": 0, "width": 1080, "height": h})
            finally:
                os.unlink(name)
        b.close()
