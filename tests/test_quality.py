import datetime as dt
from PIL import Image
from autopilot import photos as P, themes as TH, illustrate as IL

def test_carnival_out_of_season():
    assert TH.out_of_season("Kingston Carnival Dance (Kingston)", 11)
    assert not TH.out_of_season("Kingston Carnival Dance", 4)
    assert not TH.out_of_season("Devon House Kingston", 11)

def test_junk_and_history():
    for t in ("Wikimedia 1890s colonial workers", "oil painting of boat", "police officer in vest", "protest crowd masks", "black and white archive photo"):
        assert not P.text_ok(t, 11), t
    assert P.text_ok("Holland Bamboo Avenue St Elizabeth Jamaica", 11)

def test_black_and_white_pixels(tmp_path):
    bw = tmp_path / "bw.jpg"; Image.effect_noise((300, 300), 40).convert("RGB").save(bw)
    col = tmp_path / "c.jpg"; im = Image.new("RGB", (300, 300), (20, 160, 90)); im.paste((240, 190, 40), (0, 0, 150, 300)); im.paste((30, 120, 200), (150, 0, 300, 150)); im.save(col)
    assert P.too_old_looking(bw) and not P.too_old_looking(col)

def test_illustration(tmp_path):
    assert IL.kind_for("Half Moon tennis Montego Bay") in ("court", "city")
    assert IL.kind_for("Holland Bamboo Avenue") == "bamboo"
    out = tmp_path / "x.jpg"; IL.make("Dunn's River Falls", out); assert Image.open(out).size == (1080, 1350)
