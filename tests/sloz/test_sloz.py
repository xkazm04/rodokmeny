"""Test hledání překryvu záběrů v tools/sloz_zaber.py (skládání přiblížených snímků obrazovky).

Z kořene repozitáře, složka nástrojů je argument:
  python3 -I tests/sloz/test_sloz.py skills/rodokmen/tools
  (Windows: python -I -X utf8 …)
Bez ImageMagicku: obrázky jsou vymyšlené PGM v paměti, zkouší se čtení PGM a nalezení překryvu. Nic nestahuje.
"""
import importlib.util, os, random, sys

TOOLS = os.path.abspath(sys.argv[1])
spec = importlib.util.spec_from_file_location("sloz_zaber", os.path.join(TOOLS, "sloz_zaber.py"))
sz = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sz)
VYSLEDKY = []


def ok(nazev, podminka, detail=""):
    VYSLEDKY.append(bool(podminka))
    print(("OK   " if podminka else "CHYBA"), nazev, "" if podminka else detail)


random.seed(7)
W, H = 300, 120
STRANKA = [[(x * 7 + y * 13 + random.randint(0, 120)) % 256 for x in range(W)] for y in range(H)]   # „písmo“ = šum


def vyrez(x0, y0, w, h):
    return w, h, bytes(STRANKA[y][x] for y in range(y0, y0 + h) for x in range(x0, x0 + w))


# vodorovně: záběr 0–119 a 90–209 -> překryv 30
a, b = vyrez(0, 0, 120, 100), vyrez(90, 0, 120, 100)
ok("vodorovný překryv 30 bodů", sz.najdi_prekryv(a, b) == 30, sz.najdi_prekryv(a, b))
a, b = vyrez(0, 0, 120, 100), vyrez(60, 0, 120, 100)
ok("vodorovný překryv 60 bodů (polovina)", sz.najdi_prekryv(a, b) == 60, sz.najdi_prekryv(a, b))
# svisle: řádky 0–59 a 40–99 -> překryv 20; různé šířky řádků
a, b = vyrez(0, 0, 200, 60), vyrez(0, 40, 190, 60)
ok("svislý překryv 20 bodů (řádky různé šířky)", sz.najdi_prekryv(a, b, svisle=True) == 20, sz.najdi_prekryv(a, b, svisle=True))

data = b"P5\n# komentar\n3 2\n255\n" + bytes([1, 2, 3, 4, 5, 6])
ok("PGM P5 s komentářem", sz.pgm(data) == (3, 2, bytes([1, 2, 3, 4, 5, 6])), sz.pgm(data))
try:
    sz.pgm(b"P2\n1 1\n255\n0")
    ok("jiný než binární PGM odmítne", False)
except ValueError:
    ok("jiný než binární PGM odmítne", True)

print(f"\n{sum(VYSLEDKY)} z {len(VYSLEDKY)} v pořádku")
sys.exit(0 if all(VYSLEDKY) else 1)
