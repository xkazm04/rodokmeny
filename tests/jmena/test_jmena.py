"""Test volného porovnání jmen v tools/jmena.py (Kufa = Kufová, Nowak = Novák, kmeny pro kontrolu otce).

Z kořene repozitáře, složka nástrojů je argument:
  python3 -I tests/jmena/test_jmena.py skills/rodokmen/tools
  (Windows: python -I -X utf8 …)
"""
import os, sys

sys.path.insert(0, os.path.abspath(sys.argv[1]))
import jmena  # noqa: E402

VYSLEDKY = []


def over(nazev, a, b):
    VYSLEDKY.append(a == b)
    print(("OK    " if a == b else "CHYBA ") + f"{nazev}: {a!r}" + ("" if a == b else f" (čekal jsem {b!r})"))


for m, z in (("Kufa", "Kufová"), ("Kuffa", "Kufová"), ("Mika", "Miková"), ("Hula", "Hulová"), ("Novák", "Nováková"),
             ("Nowak", "Nováková"), ("Pech", "Pechová"), ("Javůrek", "Javůrková")):
    over(f"prijmeni_klic {m} = {z}", jmena.prijmeni_klic(m), jmena.prijmeni_klic(z))
over("prijmeni_klic Novák", jmena.prijmeni_klic("Novák"), "novak")
over("prijmeni_klic Dvořák beze změny", jmena.prijmeni_klic("Dvořák"), "dvorak")
over("krestni_klic Johann Georg", jmena.krestni_klic("Johann Georg"), "jan")
over("kmeny Jan Hána (Hahn)", jmena.kmeny_prijmeni("Jan Hána (Hahn)"), {"han", "hah"})
over("kmeny Anna Nováková roz. Dvořáková", jmena.kmeny_prijmeni("Anna Nováková roz. Dvořáková"), {"nov", "dvo"})
over("kmeny skrytá osoba", jmena.kmeny_prijmeni("(jméno skryto)"), set())
over("kmeny Josef Kufa ∩ Anna Kufová", bool(jmena.kmeny_prijmeni("Josef Kufa") & jmena.kmeny_prijmeni("Anna Kufová")), True)
over("kmeny Mathias Nowak ∩ Jan Novák", bool(jmena.kmeny_prijmeni("Mathias Nowak") & jmena.kmeny_prijmeni("Jan Novák")), True)

print(f"\n{sum(VYSLEDKY)}/{len(VYSLEDKY)} v pořádku")
sys.exit(0 if all(VYSLEDKY) else 1)
