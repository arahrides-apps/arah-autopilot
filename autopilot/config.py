import os, datetime as dt, yaml
from zoneinfo import ZoneInfo
from pathlib import Path

ROOT = Path(os.environ.get("AUTOPILOT_ROOT", Path(__file__).resolve().parent.parent))

def load(path=None):
    cfg = yaml.safe_load(open(path or ROOT / "config.yaml"))
    cfg["_root"] = ROOT
    return cfg

def tz(cfg):
    return ZoneInfo(cfg.get("timezone", "America/Jamaica"))

def now(cfg):
    """Current time in Jamaica. AUTOPILOT_NOW (ISO, local) lets tests fake the clock."""
    o = os.environ.get("AUTOPILOT_NOW")
    if o:
        d = dt.datetime.fromisoformat(o)
        return d if d.tzinfo else d.replace(tzinfo=tz(cfg))
    return dt.datetime.now(tz(cfg))

def media_base(cfg):
    """Public URL that Instagram downloads images from (the docs/ folder of the repo)."""
    b = os.environ.get("MEDIA_BASE_URL")
    if b:
        return b.rstrip("/") + "/"
    repo = os.environ.get("GITHUB_REPOSITORY", "OWNER/REPO")
    branch = os.environ.get("MEDIA_BRANCH", "main")
    return f"https://raw.githubusercontent.com/{repo}/{branch}/docs/"

def load_yaml(name):
    return yaml.safe_load(open(ROOT / "content" / name)) or ({} if name.endswith("meta.yaml") else [])
