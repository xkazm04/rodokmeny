"""Test tools/nalez.py: zápis nálezu jedním příkazem (jiný archiv než ARON, místní obrázek) na dočasném projektu.

Z kořene repozitáře, složka nástrojů je argument:
  python3 -I tests/nalez/test_nalez.py skills/rodokmen/tools
  (Windows: python -I -X utf8 …)
vyrez.py a ramecek.py nahradí jednoduché náhražky (ImageMagick test nepotřebuje); nic nestahuje.
"""
import json, os, shutil, subprocess, sys, tempfile

TOOLS = os.path.abspath(sys.argv[1])
PY = [sys.executable, "-I", "-X", "utf8"]
VYSLEDKY = []


def over(nazev, podminka, vystup=""):
    VYSLEDKY.append(bool(podminka))
    print(("OK    " if podminka else "CHYBA ") + nazev)
    if not podminka and vystup:
        print("      " + str(vystup).replace("\n", "\n      "))


def zapis(cesta, text):
    os.makedirs(os.path.dirname(cesta), exist_ok=True)
    with open(cesta, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


NAHRAZKA = '''import os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
jmeno = os.path.basename(__file__)
if jmeno == "vyrez.py":
    for d in ("zdroje", "vyrezy"):
        os.makedirs(os.path.join(ROOT, d), exist_ok=True)
        open(os.path.join(ROOT, d, sys.argv[2] + ".jpg"), "wb").write(b"jpg")
else:
    os.makedirs(os.path.join(ROOT, "pracovni"), exist_ok=True)
    open(os.path.join(ROOT, "pracovni", "ramecek_" + sys.argv[1] + ".jpg"), "wb").write(b"jpg")
print("hotovo " + jmeno)
'''

tmp = tempfile.mkdtemp(prefix="nalez_")
try:
    os.makedirs(os.path.join(tmp, "tools"))
    for m in ("nalez", "zapis", "denik"):
        shutil.copy(os.path.join(TOOLS, m + ".py"), os.path.join(tmp, "tools", m + ".py"))
    for m in ("vyrez", "ramecek"):
        zapis(os.path.join(tmp, "tools", m + ".py"), NAHRAZKA)
    zapis(os.path.join(tmp, "data", "osoby.py"),
          'P = {\n    1: dict(n="Jan Novák", y="1890–1950", st="doc", f=["* 1890 Holice"], r=[]),\n}\n'
          'SIDE = [\n    dict(k=1, n="Josef Novák (1892–1900)", t="Bratr Jana.", r=[]),\n]\n')
    zapis(os.path.join(tmp, "data", "zaznamy.json"), "[]\n")
    zapis(os.path.join(tmp, "data", "prepisy.json"), "{}\n")
    zapis(os.path.join(tmp, "data", "svazky.json"), '{"holice_n_05": {"svazek": "Holice N 05"}}\n')
    zapis(os.path.join(tmp, "data", "research_log.md"),
          "# Deník\n\n| # | datum | zdroj | rozsah | hledáno | výsledek | citace |\n|---|---|---|---|---|---|---|\n")
    zapis(os.path.join(tmp, "pracovni", "x.jpg"), "jpg")
    vstup = {"klic": "holice_krest_jan_novak_1890", "obraz": "pracovni/x.jpg", "svazek": "holice_n_05",
             "odkaz": "https://example.org/kniha/12", "snimek": 12, "vyrez": [0, 0.2, 1, 0.5],
             "ramecek": [[0, 0.1, 1, 0.6]],
             "zaznam": {"druh": "N", "datum": "3. 3. 1890", "nazev": "Křest Jana Nováka (1890)", "shrnuti": "Jan, syn Josefa."},
             "prepis": {"orig": "[Datum] 3. Martii 1890 | Joannes", "cz": "3. března 1890, Jan"},
             "osoby": [1, "Josef Novák"],
             "denik": {"zdroj": "Holice N 05", "rozsah": "sn. 12 (1890)", "hledano": "křest Jana (č. 1)",
                       "vysledek": "**nalezeno** | zapsáno"}}
    zapis(os.path.join(tmp, "pracovni", "v.json"), json.dumps(vstup, ensure_ascii=False))
    nalez = PY + [os.path.join(tmp, "tools", "nalez.py")]

    r = subprocess.run(nalez + ["nahled", "pracovni/v.json"], cwd=tmp, capture_output=True, text=True, encoding="utf-8")
    over("nahled projde", r.returncode == 0, r.stdout + r.stderr)
    over("nahled nemění zaznamy.json", open(os.path.join(tmp, "data", "zaznamy.json"), encoding="utf-8").read() == "[]\n")

    r = subprocess.run(nalez + ["zapis", "pracovni/v.json"], cwd=tmp, capture_output=True, text=True, encoding="utf-8")
    over("zapis projde", r.returncode == 0, r.stdout + r.stderr)
    zaz = json.load(open(os.path.join(tmp, "data", "zaznamy.json"), encoding="utf-8"))
    over("zápis v zaznamy.json se svazkem a odkazem",
         zaz and zaz[0]["klic"] == vstup["klic"] and zaz[0]["svazek"] == "holice_n_05" and zaz[0]["odkaz"], zaz)
    prep = json.load(open(os.path.join(tmp, "data", "prepisy.json"), encoding="utf-8"))
    over("přepis uložen pod „cs“ (vstup „cz“ přijat)", prep.get(vstup["klic"], {}).get("cs") == "3. března 1890, Jan", prep)
    osoby = open(os.path.join(tmp, "data", "osoby.py"), encoding="utf-8").read()
    over("odkaz u osoby 1 i u bočního příbuzného", osoby.count(vstup["klic"]) == 2, osoby)
    log = open(os.path.join(tmp, "data", "research_log.md"), encoding="utf-8").read()
    over("řádek deníku #1 se 7 sloupci a escapovaným „|“", "| 1 |" in log and r"\| zapsáno" in log, log)

    r = subprocess.run(nalez + ["zapis", "pracovni/v.json"], cwd=tmp, capture_output=True, text=True, encoding="utf-8")
    over("existující zápis bez --prepsat odmítne", r.returncode != 0 and "--prepsat" in r.stdout + r.stderr, r.stdout + r.stderr)

    spatne = dict(vstup, klic="holice_krest_2", osoby=[99])
    zapis(os.path.join(tmp, "pracovni", "s.json"), json.dumps(spatne, ensure_ascii=False))
    r = subprocess.run(nalez + ["zapis", "pracovni/s.json"], cwd=tmp, capture_output=True, text=True, encoding="utf-8")
    over("neexistující osoba: skončí dřív, než cokoli zapíše",
         r.returncode != 0 and len(json.load(open(os.path.join(tmp, "data", "zaznamy.json"), encoding="utf-8"))) == 1,
         r.stdout + r.stderr)
finally:
    shutil.rmtree(tmp, ignore_errors=True)

print(f"\n{sum(VYSLEDKY)}/{len(VYSLEDKY)} v pořádku")
sys.exit(0 if all(VYSLEDKY) else 1)
