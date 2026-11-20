"""Test: export_web.py smaže z web/public/img a web/public/zdroje obrázky, které už k žádnému zápisu ani dokumentu
nepatří (smazaný zápis nesmí dál jít na web, upstream #25), a ostatní nechá.

Z kořene repozitáře:
  python3 -I tests/web/test_export_obrazky.py
  (Windows: python -I -X utf8 …)
Založí dočasný projekt s ukázkovou rodinou (novy_projekt.py --ukazka) a pustí jen export dat (bez npm).
"""
import os, shutil, subprocess, sys, tempfile

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PY = [sys.executable, "-I", "-X", "utf8"]
VYSLEDKY = []


def check(nazev, ok, detail=""):
    VYSLEDKY.append(bool(ok))
    print(("OK  " if ok else "CHYBA ") + nazev + ("" if ok else "\n    " + str(detail)[:1500].replace("\n", "\n    ")))


tmp = tempfile.mkdtemp(prefix="export_obrazky_")
try:
    proj = os.path.join(tmp, "p")
    r = subprocess.run(PY + [os.path.join(REPO, "skills", "rodokmen", "tools", "novy_projekt.py"), proj, "--ukazka"],
                       capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0, r.stdout + r.stderr

    def export():
        r = subprocess.run(PY + [os.path.join(proj, "tools", "export_web.py")], capture_output=True, text=True,
                           encoding="utf-8", cwd=proj)
        return r.returncode, r.stdout + r.stderr

    rc, out = export()
    img, zdr = (os.path.join(proj, "web", "public", s) for s in ("img", "zdroje"))
    puvodni = sorted(os.listdir(img))
    check("první export zkopíruje výřezy", rc == 0 and puvodni, out)

    for d in (img, zdr):   # obrázek zápisu, který mezitím zmizel z dat
        with open(os.path.join(d, "smazany_zapis_1890.jpg"), "wb") as f:
            f.write(b"\xff\xd8\xff\xd9")
    with open(os.path.join(img, "poznamka.txt"), "w", encoding="utf-8") as f:
        f.write("jiný soubor než .jpg export nechá")
    stazeny = puvodni[0]   # výřez, který uživatel smazal z vyrezy/ (zápis stažen z webu)
    os.remove(os.path.join(proj, "vyrezy", stazeny))

    rc, out = export()
    zbyva = sorted(os.listdir(img))
    check("smaže obrázek zápisu, který v datech není", rc == 0 and "smazany_zapis_1890.jpg" not in zbyva
          and "smazany_zapis_1890.jpg" not in os.listdir(zdr), (out, zbyva))
    check("smaže obrázek, jehož výřez ve vyrezy/ už není", stazeny not in zbyva, zbyva)
    check("ostatní obrázky nechá", set(puvodni) - {stazeny} <= set(zbyva), (puvodni, zbyva))
    check("soubor, který není .jpg, nechá", "poznamka.txt" in zbyva, zbyva)
    check("výpis řekne, kolik smazal", "smazáno 3 starých" in out, out)
finally:
    shutil.rmtree(tmp, ignore_errors=True)

print(f"{sum(VYSLEDKY)}/{len(VYSLEDKY)} v pořádku")
sys.exit(0 if all(VYSLEDKY) else 1)
