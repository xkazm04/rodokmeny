"""Test českých slovních dat z MyHeritage / Family Tree Builderu v ged_import.py (upstream #143).

Z kořene repozitáře:
  python3 -I tests/ged/test_datum.py skills/rodokmen/tools/ged_import.py
  (Windows: python -I -X utf8 …)
Napíše malý GEDCOM s vymyšlenými osobami a z výpisu osob (id | jméno | narození) přečte převedená data.
"""
import os, subprocess, sys, tempfile

GED = os.path.abspath(sys.argv[1])
PY = [sys.executable, "-I", "-X", "utf8"]
VYSLEDKY = []

PRIPADY = [   # (DATE v GEDCOMu, čekaný tvar)
    ("Odhadovaný: 23. úno, 1907", "asi 23. 2. 1907"),
    ("Okolo roku 1790", "asi 1790"),
    ("Po roce 1900", "po 1900"),
    ("Před rokem 1896", "před 1896"),
    ("Neověřený rok úmrtí: 1957", "1957 (?)"),
    ("12. čvc 1850", "12. 7. 1850"),
    ("čvn 1851", "6. 1851"),
    ("3. bře. 1852", "3. 3. 1852"),
    ("Mezi rokem 1820 a 1825", "mezi 1820 a 1825"),
    # dřívější tvary beze změny
    ("14 FEB 1890", "14. 2. 1890"),
    ("ABT 1850", "asi 1850"),
    ("SRPEN 1945", "8. 1945"),
    ("PŘED 1900", "před 1900"),
    ("ČERVENEC 1950", "7. 1950"),
    ("ČERVEN 1950", "6. 1950"),
    ("5. července 1880", "5. 7. 1880"),
]

radky = ["0 HEAD", "1 CHAR UTF-8"]
for i, (datum, _) in enumerate(PRIPADY, 1):
    radky += [f"0 @I{i}@ INDI", f"1 NAME Osoba{i} /Nováková/", "1 BIRT", f"2 DATE {datum}"]
radky.append("0 TRLR")
tmp = tempfile.mkdtemp(prefix="ged_datum_")
cesta = os.path.join(tmp, "strom.ged")
with open(cesta, "w", encoding="utf-8", newline="\n") as f:
    f.write("\n".join(radky) + "\n")
r = subprocess.run(PY + [GED, cesta], capture_output=True, text=True, encoding="utf-8")
vystup = {}
for radek in r.stdout.splitlines():
    casti = [c.strip() for c in radek.split("|")]
    if len(casti) == 3:
        vystup[casti[0]] = casti[2]
for i, (datum, cekam) in enumerate(PRIPADY, 1):
    je = vystup.get(f"@I{i}@", "")
    ok = je == "* " + cekam
    VYSLEDKY.append(ok)
    print(("OK  " if ok else "CHYBA ") + f"„{datum}“ → „{cekam}“" + ("" if ok else f" (vyšlo „{je}“)"))
os.remove(cesta)
os.rmdir(tmp)
if r.returncode:
    print("NÁVRATOVÝ KÓD", r.returncode, r.stderr)
print(f"{sum(VYSLEDKY)}/{len(VYSLEDKY)} v pořádku")
sys.exit(0 if all(VYSLEDKY) and not r.returncode else 1)
