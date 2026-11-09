"""Every web photo must say Jamaica; Kingston posts get Kingston attractions; Mandeville never a beach; themed slide photos come from matching searches."""
import sys, pathlib, random, datetime as dt, tempfile
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from pathlib import Path
from PIL import Image
from autopilot import config, photos as P, ledger as L
cfg = config.load(); cfg["sources"]["drive"]["enabled"] = False; cfg["sources"]["local"]["enabled"] = False

class Web:
    name = "fake"; calls = []
    def search(self, query, rng):
        self.calls.append(query)
        base = [("Bangkok temple at night", 0), ("Cancun beach resort sunset", 1), ("%s" % query + " view", 2)]
        extra = {"Kingston Art Walk": "Kingston Art Walk Jamaica mural street", "Devon House Kingston": "Devon House Kingston Jamaica mansion landscape",
                 "Mandeville Jamaica town": "Mandeville Jamaica town hills view", "bun and cheese Jamaica": "Jamaica bun and cheese food vendor stand",
                 "couple Jamaica beach": "couple together on Jamaica beach"}
        out = [{"id": f"f:{abs(hash((query, n)))%10**7}", "name": f"f-{n}-{abs(hash(query))%999}", "w": 1600, "h": 1200, "text": t} for t, n in base]
        for k, t in extra.items():
            if k.lower() in query.lower(): out.append({"id": f"f:{abs(hash(t))%10**7}", "name": "f-x-" + t[:10].replace(" ", ""), "w": 1600, "h": 1200, "text": t})
        out.append({"id": "f:old", "name": "f-old", "w": 1600, "h": 1200, "text": "Historic Kingston Jamaica 1907 harbour vintage"})
        out.append({"id": "f:beachmand", "name": "f-bm", "w": 1600, "h": 1200, "text": "Mandeville Jamaica beach sand sea view"})
        return out
    def fetch(self, item, dest):
        Path(dest).parent.mkdir(parents=True, exist_ok=True); Image.new("RGB", (1600, 1200), (90, 140, 90)).save(dest, "JPEG")

tmp = Path(tempfile.mkdtemp())
def mk():
    led = L.Ledger(tmp / "l.json") if "path" in L.Ledger.__init__.__code__.co_varnames else L.Ledger()
    return P.Picker(cfg, led, dt.date(2026, 11, 9), random.Random(3), cache=tmp / "c", web=[Web()])
for seed in range(6):
    pk = mk(); pk.rng = random.Random(seed); pk.cfg["photos"]["web_share"] = 1.0
    p = pk.scene("Kingston Jamaica", "Kingston", ok=None)
    assert p is None or (P.TH.JA.search(p.text) and "bangkok" not in p.text.lower() and "cancun" not in p.text.lower() and "1907" not in p.text), p and p.text
    pk = mk(); pk.rng = random.Random(seed)
    p = pk.scene("Mandeville Manchester Jamaica", "Mandeville")
    assert p is None or not P.COASTAL_PHOTO.search(p.text), p and p.text
    pk = mk(); pk.rng = random.Random(seed)
    t = pk.theme_photo("couple")
    assert t is None or "jamaica" in t.text.lower(), t and t.text
    pk = mk(); pk.rng = random.Random(seed)
    f = pk.theme_photo("food")
    assert f is None or P.TH.JA.search(f.text), f and f.text
pk = mk(); pk.rng = random.Random(1); pk.scene("Kingston Jamaica", "Kingston")
assert any("Art Walk" in q or "Devon" in q or "Emancipation" in q or "Bob Marley" in q or "skyline" in q for q in Web.calls), Web.calls
print("THEME PHOTOS OK")
