"""Place/photo matching: inland towns never get beach photos; photos naming another place or looking old/historic are rejected."""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from autopilot.photos import is_inland, COASTAL_PHOTO, OLD_PHOTO, names_other_place
assert is_inland("Mandeville", "Mandeville Manchester Jamaica") and is_inland("Blue Mountains") and not is_inland("Negril", "Negril Jamaica")
assert COASTAL_PHOTO.search("Lime Cay beach Kingston") and not COASTAL_PHOTO.search("Mandeville Manchester church green hills")
for t in ("Historic photo of Kingston 1907", "vintage postcard Jamaica", "black and white street", "old harbour sepia"): assert OLD_PHOTO.search(t), t
assert not OLD_PHOTO.search("Blue Mountain coffee farm sunrise")
assert names_other_place("Negril cliffs sunset", ["mandeville"]) and not names_other_place("Mandeville town green hills", ["mandeville"])
print("GEO OK")
