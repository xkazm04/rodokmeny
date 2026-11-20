"""Test citací zdrojů (SOUR → TITL/AUTH) v ged_import.py: Smart Match (cizí strom) × Record Match (záznam).

Z kořene repozitáře:
  python3 -I tests/ged/test_zdroje.py skills/rodokmen/tools/ged_import.py
  (Windows: python -I -X utf8 …)
Malý GEDCOM s vymyšlenými osobami ve stylu exportu z webu MyHeritage (upstream #30, #143).
"""
import os, subprocess, sys, tempfile

GED = os.path.abspath(sys.argv[1])
PY = [sys.executable, "-I", "-X", "utf8"]
VYSLEDKY = []

STROM = """0 HEAD
1 CHAR UTF-8
0 @I1@ INDI
1 NAME Petr /Novák/
1 BIRT
2 DATE 1950
2 SOUR @S2@
3 PAGE 1921 Czechia Census
1 FAMC @F1@
0 @I2@ INDI
1 NAME Jan /Novák/
1 BIRT
2 DATE 1920
1 SOUR @S1@
2 PAGE Smart Matching
1 SOUR @S1@
1 SOUR @S9@
1 FAMS @F1@
1 FAMC @F2@
0 @I3@ INDI
1 NAME Marie /Malá/
1 SOUR @S1@
1 SOUR @S3@
1 FAMS @F1@
0 @F1@ FAM
1 HUSB @I2@
1 WIFE @I3@
1 CHIL @I1@
0 @I4@ INDI
1 NAME Josef /Novák/
1 SOUR @S5@
1 FAMS @F2@
0 @I5@ INDI
1 NAME Anna /Nováková/
1 SOUR Rozhovor s babičkou Annou 1990
1 FAMS @F2@
0 @F2@ FAM
1 HUSB @I4@
1 WIFE @I5@
1 CHIL @I2@
1 MARR
2 DATE 1918
2 PLAC Holice
2 SOUR @S4@
0 @S1@ SOUR
1 TITL Dvořák Web Site
1 AUTH Karel Dvo&#345;&aacute;k
0 @S2@ SOUR
1 TITL 1921 Czechia Census
0 @S3@ SOUR
1 TITL BillionGraves
0 @S4@ SOUR
1 TITL Matrika oddaných Holice 1915–1925
0 @S5@ SOUR
1 TITL Novák Family Tree
0 TRLR
"""


def over(nazev, ok, vystup=""):
    VYSLEDKY.append(ok)
    print(("OK    " if ok else "CHYBA ") + nazev)
    if not ok:
        print("      " + vystup.replace("\n", "\n      "))


d = tempfile.mkdtemp(prefix="ged_zdroje_")
cesta = os.path.join(d, "strom.ged")
with open(cesta, "w", encoding="utf-8", newline="\n") as f:
    f.write(STROM)
out = subprocess.run(PY + [GED, cesta, "Petr Novák"], capture_output=True, text=True, encoding="utf-8").stdout
over("Record Match u události (sčítání)", "zdroj: 1921 Czechia Census – Record Match" in out, out)
over("Smart Match: název a autor (HTML entity), jen jednou",
     out.count("zdroj: Dvořák Web Site (Karel Dvořák) – Smart Match") == 2 and "2 | Jan Novák" in out, out)
over("osoba jen z cizího stromu označená", "2 | Jan Novák | * 1920  [jen cizí stromy → mh]" in out, out)
over("osoba i se záznamem neoznačená", "3 | Marie Malá |  [jen" not in out and "zdroj: BillionGraves – Record Match" in out, out)
# citace sňatku u rodiny (FAM/MARR) se počítá k osobě (review #41)
over("zdroj sňatku z rodiny u osoby", "zdroj: Matrika oddaných Holice 1915–1925 – Record Match" in out
     and "4 | Josef Novák |  [jen" not in out, out)
# neznámý druh zdroje a odkaz na chybějící zdroj nejsou Record Match (review #42)
over("ústní zdroj není Record Match", "zdroj: Rozhovor s babičkou Annou 1990 – jiný zdroj" in out, out)
over("chybějící zdroj @S9@ ohlášen a osoba s ním zůstává mh", "zdroj: @S9@ – nenalezený zdroj" in out
     and "2 | Jan Novák | * 1920  [jen cizí stromy → mh]" in out, out)
py = subprocess.run(PY + [GED, cesta, "Petr Novák", "--osoby"], capture_output=True, text=True, encoding="utf-8").stdout
ns = {}
try:
    exec(py, ns)
except Exception as e:  # noqa: BLE001
    over("kostra osoby.py jde načíst", False, f"{e}\n{py}")
P = ns.get("P", {})
over("kostra: jen cizí strom → st mh s poznámkou", P.get(2, {}).get("st") == "mh" and "Smart Match" in P[2].get("note", ""), py)
over("kostra: se záznamem zůstává fam", P.get(3, {}).get("st") == "fam" and P.get(1, {}).get("st") == "fam", py)

print(f"\n{sum(VYSLEDKY)}/{len(VYSLEDKY)} v pořádku")
sys.exit(0 if all(VYSLEDKY) else 1)
