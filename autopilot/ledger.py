"""Photo and copy ledger. The 90-day no-reuse rule lives here.

A photo is blocked when ANY of these is true:
  - its id (drive:<fileId>, pexels:<id>, ...) or its file name was used in the last `reuse_days`
  - its fingerprint is the same picture (distance <= 3) as one used in the last `reuse_days`
  - its fingerprint is a near-identical shot (distance <= near_duplicate_distance) used in the last `near_duplicate_days`
"""
import json, datetime as dt
from PIL import Image
from .config import ROOT

PATH = ROOT / "data" / "ledger.json"

def dhash(path, size=8):
    im = Image.open(path).convert("L").resize((size + 1, size), Image.LANCZOS)
    px = list(im.getdata()); bits = 0
    for r in range(size):
        for c in range(size):
            bits = (bits << 1) | (px[r * (size + 1) + c] > px[r * (size + 1) + c + 1])
    return bits

def dist(a, b):
    return bin(a ^ b).count("1")

def _d(s):
    return dt.date.fromisoformat(s)

class Ledger:
    def __init__(self, path=PATH):
        self.path = path
        self.data = json.load(open(path)) if path.exists() else {"photos": {}, "copy": {}, "hashes": []}
        self.data.setdefault("photos", {}); self.data.setdefault("copy", {}); self.data.setdefault("series", [])
        if not isinstance(self.data.get("hashes"), list):
            self.data["hashes"] = []

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        json.dump(self.data, open(self.path, "w"), indent=1, sort_keys=True)

    # ---- photos
    def blocked(self, keys, h, today, cfg):
        p = cfg["photos"]; reuse = p["reuse_days"]
        for k in keys:
            e = self.data["photos"].get(k)
            if e and (today - _d(e["last_used"])).days < reuse:
                return f"used {e['last_used']} ({k})"
        if h is not None:
            for e in self.data["hashes"]:
                age = (today - _d(e["date"])).days; d = dist(h, int(e["h"], 16))
                if age < reuse and d <= 3:
                    return f"same picture as {e.get('id', '?')} used {e['date']}"
                if age < p["near_duplicate_days"] and d <= p["near_duplicate_distance"]:
                    return f"near-identical to {e.get('id', '?')} used {e['date']}"
        return None

    def series_age(self, series, today):
        """Days since a photo from the same shoot/series was last used (9999 = never)."""
        ages = [(today - _d(e["date"])).days for e in self.data["series"] if e["s"] == series]
        return min(ages) if ages else 9999

    def release(self, photo_id, name, date):
        """Un-use a photo that was only drafted (never approved) so it can be picked again."""
        for k in (photo_id, "name:" + name):
            e = self.data["photos"].get(k)
            if e and e.get("last_used") == date:
                if e.get("first_used") == date: del self.data["photos"][k]
                else: e["last_used"] = e["first_used"]
        self.data["hashes"] = [e for e in self.data["hashes"] if not (e.get("id") == photo_id and e["date"] == date)]
        self.data["series"] = [e for e in self.data["series"] if not (e.get("id") == photo_id and e["date"] == date)]

    def record(self, keys, h, today, source="", series=""):
        if series:
            self.data["series"].append({"s": series, "date": today.isoformat(), "id": keys[0]})
        for k in keys:
            e = self.data["photos"].setdefault(k, {"first_used": today.isoformat(), "source": source})
            e["last_used"] = today.isoformat()
        if h is not None:
            self.data["hashes"].append({"h": format(h, "016x"), "date": today.isoformat(), "id": keys[0]})

    def earliest_reuse(self, key, cfg):
        e = self.data["photos"].get(key)
        return (_d(e["last_used"]) + dt.timedelta(days=cfg["photos"]["reuse_days"])).isoformat() if e else None

    # ---- copy (wording)
    def copy_pick(self, kind, n, today, rng, cooldown):
        """Index of the least recently used entry. Returns (index, cycled) where cycled=True means the bank ran out of fresh wording."""
        last = lambda i: self.data["copy"].get(f"{kind}:{i}", "0000-00-00")
        order = sorted(range(n), key=lambda i: (last(i), rng.random()))
        i = order[0]
        l = last(i)
        cycled = l != "0000-00-00" and (today - _d(l)).days < cooldown
        return i, cycled

    def copy_record(self, kind, i, today):
        self.data["copy"][f"{kind}:{i}"] = today.isoformat()

    def prune(self, today, keep_days=400):
        self.data["hashes"] = [e for e in self.data["hashes"] if (today - _d(e["date"])).days < keep_days]
        self.data["series"] = [e for e in self.data["series"] if (today - _d(e["date"])).days < keep_days]
