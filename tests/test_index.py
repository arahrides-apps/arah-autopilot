import datetime as dt, random, shutil, tempfile, json
from pathlib import Path
from PIL import Image
from autopilot import gazetteer as G, photos as P, indexer as I

def _gps_jpg(path, lat, lon, date="2026:11:08 10:00:00"):
    im = Image.new("RGB", (1600, 1200), (30, 140, 90)); ex = Image.Exif()
    def dms(v):
        v = abs(v); d = int(v); m = int((v - d) * 60); s = (v - d - m / 60) * 3600
        return ((d, 1), (m, 1), (int(s * 100), 100))
    gps = {1: "N" if lat >= 0 else "S", 2: tuple(x[0] / x[1] for x in dms(lat)), 3: "E" if lon >= 0 else "W", 4: tuple(x[0] / x[1] for x in dms(lon))}
    ex[0x8825] = gps; ex[306] = date
    im.save(path, exif=ex)

def test_gazetteer():
    assert G.nearest(18.0420, -77.5010)[0] == "Mandeville"
    assert G.nearest(18.27, -78.35)[0].startswith(("Negril", "Seven Mile"))
    assert not G.in_jamaica(25.77, -80.19)            # Miami

def test_exif_and_index(tmp_path, monkeypatch):
    d = tmp_path / "ph"; d.mkdir()
    _gps_jpg(d / "a.jpg", 18.0420, -77.5010); _gps_jpg(d / "b.jpg", 25.77, -80.19)
    Image.new("RGB", (1600, 1200), (200, 90, 60)).save(d / "c.jpg")
    info = P.exif_info(d / "a.jpg"); assert abs(info["lat"] - 18.042) < 0.01 and info["lon"] < -77 and info["date"] == "2026-11-08"
    monkeypatch.setattr(I, "AUTO", tmp_path / "auto.yaml"); monkeypatch.setattr(I, "THUMBS", tmp_path / "th"); monkeypatch.setattr(I, "ROOT", tmp_path)
    (tmp_path / "docs").mkdir()
    cfg = {"photos": {"min_short_side": 800, "allow_people_photos": True, "allow_people_scenery": True, "reuse_days": 90}, "sources": {"local": {"enabled": True, "dir": str(d)}, "drive": {"enabled": False, "service_account_env": "X"}}}
    class W:  # no web sources
        pass
    pk = P.Picker(cfg, None, dt.date(2026, 11, 12), random.Random(1), cache=tmp_path / "cache", web=[])
    n, done = I.run(cfg, picker=pk)
    assert n == 3
    k = {v["kind"] for v in done.values()}
    assert k == {"scenery", "not-jamaica", "unplaced"}, k
    a = done["local:a"]; assert a["place"] == "Mandeville" and a["coastal"] is False
    assert (tmp_path / "docs" / "photo_index.html").exists()
