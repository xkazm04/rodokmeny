"""Test tools/zapis.py: --smazat (zápis omylem), prejmenuj (nový klíč všude) a kontrola přepisu (jen orig a cs).

Z kořene repozitáře, složka nástrojů je argument:
  python3 -I tests/zapis/test_smazat.py skills/rodokmen/tools
  (Windows: python -I -X utf8 …)
Pracuje v dočasném projektu, nic nestahuje.
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


def cti(tmp, f):
    return open(os.path.join(tmp, f), encoding="utf-8").read()


ZAZNAMY = """[
 {
  "klic": "holice_krest_jan_1890",
  "svazek": "s1",
  "nazev": "Křest Jana"
 },
 {
  "klic": "holice_krest_cizi_1891",
  "svazek": "s1",
  "nazev": "Křest cizího"
 },
 {
  "klic": "holice_oddani_1915",
  "svazek": "s1",
  "nazev": "Sňatek"
 }
]
"""
PREPISY = """{
 "holice_krest_jan_1890": {"orig": "Joannes", "cs": "Jan"},
 "holice_krest_cizi_1891": {"orig": "Wenceslaus", "cs": "Václav"},
 "holice_oddani_1915": {"orig": "x", "cs": "y"}
}
"""
OSOBY = ('P = {\n    1: dict(n="Jan Novák", st="doc", f=["* 1890"], r=["holice_krest_jan_1890", "holice_oddani_1915"]),\n}\n'
         "SIDE = [\n    dict(k=1, n='Josef Novák', t='Bratr Jana.', r=['holice_krest_jan_1890']),\n]\n"
         'HYPOTEZY = [dict(rod=8, nadpis="x", text="viz holice_krest_jan_1890", polozky=[], zaznamy=["holice_krest_jan_1890"])]\n')

tmp = tempfile.mkdtemp(prefix="zapis_smazat_")
try:
    os.makedirs(os.path.join(tmp, "tools"))
    shutil.copy(os.path.join(TOOLS, "zapis.py"), os.path.join(tmp, "tools", "zapis.py"))
    zapis(os.path.join(tmp, "data", "zaznamy.json"), ZAZNAMY)
    zapis(os.path.join(tmp, "data", "prepisy.json"), PREPISY)
    zapis(os.path.join(tmp, "data", "zvyrazneni.json"), '{\n "holice_krest_cizi_1891": {"boxes": [[0, 0, 1, 1]]}\n}\n')
    zapis(os.path.join(tmp, "data", "osoby.py"), OSOBY)
    zapis(os.path.join(tmp, "data", "research_log.md"), "| 1 | 2026-01-01 | a | b | c | zapsáno `holice_krest_cizi_1891` | d |\n")
    zapis(os.path.join(tmp, "data", "pribeh.md"), "Jan byl pokřtěn ([zápis](/zdroj/holice_krest_jan_1890/)).\n")
    for slozka in ("vyrezy", "zdroje"):
        for k in ("holice_krest_cizi_1891", "holice_krest_jan_1890"):
            zapis(os.path.join(tmp, slozka, k + ".jpg"), "jpg")
    zap = PY + [os.path.join(tmp, "tools", "zapis.py")]

    # --smazat necitovaného zápisu
    r = subprocess.run(zap + ["--smazat", "holice_krest_cizi_1891"], cwd=tmp, capture_output=True, text=True, encoding="utf-8")
    over("smazat: projde", r.returncode == 0, r.stdout + r.stderr)
    zz = cti(tmp, "data/zaznamy.json")
    over("smazat: v zaznamy.json zmizela jen ta položka, zbytek doslova",
         zz == ZAZNAMY.replace(' {\n  "klic": "holice_krest_cizi_1891",\n  "svazek": "s1",\n  "nazev": "Křest cizího"\n },\n', ""), zz)
    pp = cti(tmp, "data/prepisy.json")
    over("smazat: prepisy bez položky, zbytek doslova",
         pp == PREPISY.replace(' "holice_krest_cizi_1891": {"orig": "Wenceslaus", "cs": "Václav"},\n', ""), pp)
    over("smazat: zvyrazneni (jediná položka) prázdné", json.loads(cti(tmp, "data/zvyrazneni.json")) == {})
    over("smazat: výřezy přesunuté do pracovni/smazano_…",
         not os.path.exists(os.path.join(tmp, "vyrezy", "holice_krest_cizi_1891.jpg"))
         and any(d.startswith("smazano_") for d in os.listdir(os.path.join(tmp, "pracovni"))))
    over("smazat: ohlásí zmínku v deníku", "research_log.md" in r.stdout, r.stdout)

    # --smazat citovaného zápisu nic nezmění
    r = subprocess.run(zap + ["--smazat", "holice_oddani_1915"], cwd=tmp, capture_output=True, text=True, encoding="utf-8")
    over("smazat citovaný: odmítne a řekne kde", r.returncode != 0 and "osoby.py" in r.stdout + r.stderr, r.stdout + r.stderr)
    over("smazat citovaný: zaznamy beze změny", "holice_oddani_1915" in cti(tmp, "data/zaznamy.json"))

    # prejmenuj
    r = subprocess.run(zap + ["prejmenuj", "holice_krest_jan_1890", "holice_krest_jan_novak_1890"], cwd=tmp,
                       capture_output=True, text=True, encoding="utf-8")
    over("prejmenuj: projde", r.returncode == 0, r.stdout + r.stderr)
    oso = cti(tmp, "data/osoby.py")
    over("prejmenuj: r osoby, SIDE (apostrofy), HYPOTEZY.zaznamy i zmínka v textu",
         oso.count("holice_krest_jan_novak_1890") == 4 and "'holice_krest_jan_novak_1890'" in oso
         and "holice_krest_jan_1890" not in oso, oso)
    over("prejmenuj: zaznamy, prepisy, příběh", "holice_krest_jan_novak_1890" in cti(tmp, "data/zaznamy.json")
         and "holice_krest_jan_novak_1890" in cti(tmp, "data/prepisy.json")
         and "/zdroj/holice_krest_jan_novak_1890/" in cti(tmp, "data/pribeh.md"))
    over("prejmenuj: výřezy", os.path.exists(os.path.join(tmp, "vyrezy", "holice_krest_jan_novak_1890.jpg"))
         and os.path.exists(os.path.join(tmp, "zdroje", "holice_krest_jan_novak_1890.jpg")))
    r = subprocess.run(zap + ["prejmenuj", "holice_oddani_1915", "holice_krest_jan_novak_1890"], cwd=tmp,
                       capture_output=True, text=True, encoding="utf-8")
    over("prejmenuj na existující klíč: odmítne", r.returncode != 0, r.stdout + r.stderr)

    # přepis jen s orig a cs
    zapis(os.path.join(tmp, "pracovni", "p.json"), '{"orig": "x", "preklad": "y"}')
    r = subprocess.run(zap + ["prepisy", "novy_1900", "pracovni/p.json"], cwd=tmp, capture_output=True, text=True, encoding="utf-8")
    over("prepisy s polem „preklad“: odmítne", r.returncode != 0 and "cs" in r.stdout + r.stderr, r.stdout + r.stderr)
    over("prepisy s polem „preklad“: nic nezapsáno", "novy_1900" not in cti(tmp, "data/prepisy.json"))
finally:
    shutil.rmtree(tmp, ignore_errors=True)

print(f"\n{sum(VYSLEDKY)}/{len(VYSLEDKY)} v pořádku")
sys.exit(0 if all(VYSLEDKY) else 1)
