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

_YC = {}
def load_yaml(name):
    """Content files are read once per run (they were re-read 150+ times); callers get their own copy, so changing it changes nothing on disk."""
    import copy
    f = ROOT / "content" / name
    k = (str(f), f.stat().st_mtime if f.exists() else 0)
    if k not in _YC:
        _YC[k] = yaml.safe_load(open(f)) or ({} if name.endswith("meta.yaml") else [])
    return copy.deepcopy(_YC[k])


# ---- run clock: every slow step (photo searches, Gemini lookups, Reels) checks it, so a run stops in time to save its work
_DEADLINE = [None]
def start_clock(cfg):
    import time
    _DEADLINE[0] = time.time() + cfg.get("max_run_minutes", 40) * 60
    cfg["_deadline"] = _DEADLINE[0]; _T0[0] = time.time()

def out_of_time(margin=0):
    import time
    return _DEADLINE[0] is not None and time.time() > _DEADLINE[0] - margin

# ---- where a run's minutes go: written to docs/run_stats.json after each day, so a slow run can be read back afterwards
TIMES = {}
_T0 = [None]
def tick(key, secs, n=1):
    t = TIMES.setdefault(key, [0, 0.0]); t[0] += n; t[1] += secs

def write_stats(extra=None):
    import time, json
    from . import queue as Q
    try:
        from . import vision as V
        g = dict(V.STATS)
    except Exception:
        g = {}
    d = {"elapsed_min": round((time.time() - (_T0[0] or time.time())) / 60, 1),
         "times": {k: {"count": v[0], "secs": round(v[1])} for k, v in sorted(TIMES.items(), key=lambda kv: -kv[1][1])},
         "ai": {k: (round(v) if isinstance(v, float) else v) for k, v in g.items() if k != "why"}}
    d.update(extra or {})
    try: (Q.DOCS / "run_stats.json").write_text(json.dumps(d, indent=1))
    except Exception: pass
