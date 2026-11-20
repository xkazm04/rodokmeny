"""Test odkazů na snímky ARON: `aron_img.py <apu> link <n>` dává id souboru TILE (PUBLISHED otevře knihu na prvním
snímku, upstream #18) a `aron_img.py odkazy [--opravit]` opraví staré odkazy v data/.

Z kořene repozitáře:
  python3 -I tests/aron/test_odkazy.py skills/rodokmen/tools
  (Windows: python -I -X utf8 …)
Na archiv nechodí: popis svazku leží předem v pracovni/.cache_aron/ dočasného projektu.
"""
import json, os, shutil, subprocess, sys, tempfile

TOOLS = os.path.abspath(sys.argv[1])
PY = [sys.executable, "-I", "-X", "utf8"]
VYSLEDKY = []

APU = "1a0b2337-0000-4000-8000-000000000001"
DAO = "d0d0d0d0-0000-4000-8000-000000000002"
PUB = {n: f"aaaaaaaa-0000-4000-8000-{n:012d}" for n in (1, 2, 3)}
TILE = {n: f"bbbbbbbb-0000-4000-8000-{n:012d}" for n in (1, 2, 3)}


def check(nazev, ok, detail=""):
    VYSLEDKY.append(bool(ok))
    print(("OK  " if ok else "CHYBA ") + nazev + ("" if ok else "\n    " + str(detail).replace("\n", "\n    ")))


def zapis(cesta, text):
    os.makedirs(os.path.dirname(cesta), exist_ok=True)
    with open(cesta, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def odkaz(file_id):
    return f"https://aron.vychodoceskearchivy.cz/apu/{APU}/dao/{DAO}/file/{file_id}"


tmp = tempfile.mkdtemp(prefix="aron_odkazy_")
try:
    shutil.copytree(TOOLS, os.path.join(tmp, "tools"), ignore=shutil.ignore_patterns("__pycache__"))
    files = [dict(id=PUB[n], type="PUBLISHED", order=n) for n in PUB] + \
            [dict(id=TILE[n], type="TILE", order=n, referencedFile=f"https://example.org/{n}.dzi") for n in TILE]
    zapis(os.path.join(tmp, "pracovni", ".cache_aron", APU + ".json"),
          json.dumps(dict(id=APU, name="Fond: N Holice", digitalObjects=[dict(id=DAO, files=files)])))
    zaz = [dict(klic="a", odkaz=odkaz(PUB[2])), dict(klic="b", odkaz=odkaz(TILE[3])), dict(klic="c", odkaz=odkaz(PUB[2]))]
    zapis(os.path.join(tmp, "data", "zaznamy.json"), json.dumps(zaz, ensure_ascii=False, indent=1))
    zapis(os.path.join(tmp, "data", "STAV.md"), f"Křest Jana: {odkaz(PUB[3])}\r\n")
    aron = os.path.join(tmp, "tools", "aron_img.py")

    def spust(*a):
        r = subprocess.run(PY + [aron, *a], capture_output=True, text=True, encoding="utf-8", cwd=tmp)
        return r.returncode, r.stdout + r.stderr

    rc, out = spust(APU, "link", "2")
    check("link dává id souboru TILE", rc == 0 and out.strip() == odkaz(TILE[2]), out)

    puvodni = open(os.path.join(tmp, "data", "zaznamy.json"), encoding="utf-8").read()
    rc, out = spust("odkazy")
    check("odkazy bez --opravit jen vypíše", rc == 0 and "na první snímek 2" in out and "správně 1" in out
          and open(os.path.join(tmp, "data", "zaznamy.json"), encoding="utf-8").read() == puvodni, out)

    rc, out = spust("odkazy", "--opravit")
    zaz2 = json.load(open(os.path.join(tmp, "data", "zaznamy.json"), encoding="utf-8"))
    check("--opravit přepíše PUBLISHED na TILE téhož snímku",
          rc == 0 and [z["odkaz"] for z in zaz2] == [odkaz(TILE[2]), odkaz(TILE[3]), odkaz(TILE[2])], (out, zaz2))
    with open(os.path.join(tmp, "data", "STAV.md"), encoding="utf-8", newline="") as f:
        stav = f.read()
    check("opraví i .md a zachová konce řádků", stav == f"Křest Jana: {odkaz(TILE[3])}\r\n", repr(stav))

    rc, out = spust("odkazy")
    check("podruhé už není co opravit", rc == 0 and "na první snímek 0" in out and "správně 2" in out, out)
finally:
    shutil.rmtree(tmp, ignore_errors=True)

print(f"{sum(VYSLEDKY)}/{len(VYSLEDKY)} v pořádku")
sys.exit(0 if all(VYSLEDKY) else 1)
