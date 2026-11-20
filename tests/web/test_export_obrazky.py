"""Test: export_web.py smaže z web/public/img a web/public/zdroje obrázky, které sám dřív vyexportoval a které už
k žádnému zápisu ani dokumentu nepatří (smazaný zápis nesmí dál jít na web, upstream #25); ručně přidané obrázky
nechá (evidence web/.exportovane_obrazky.json). Rámečky v plných snímcích: evidence web/.ramecky_zdroju.json.

Z kořene repozitáře:
  python3 -I tests/web/test_export_obrazky.py
  (Windows: python -I -X utf8 …)
Založí dočasný projekt s ukázkovou rodinou (novy_projekt.py --ukazka) a pustí jen export dat (bez npm).
ImageMagick nahradí náhražka „magick“ (místo kreslení připíše k souboru značku), ať test běží všude stejně.
"""
import json, os, shutil, subprocess, sys, tempfile

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PY = [sys.executable, "-I", "-X", "utf8"]
VYSLEDKY = []
NAKRESLENO = b"RAMECEK"
NAHRAZKA = f"""import sys
a = sys.argv[1:]
if a and a[-1] == "info:":
    print("1000 1500")
else:
    open(a[-1], "wb").write(open(a[0], "rb").read() + {NAKRESLENO!r})
"""


def check(nazev, ok, detail=""):
    VYSLEDKY.append(bool(ok))
    print(("OK  " if ok else "CHYBA ") + nazev + ("" if ok else "\n    " + str(detail)[:1500].replace("\n", "\n    ")))


tmp = tempfile.mkdtemp(prefix="export_obrazky_")
try:
    proj = os.path.join(tmp, "p")
    r = subprocess.run(PY + [os.path.join(REPO, "skills", "rodokmen", "tools", "novy_projekt.py"), proj, "--ukazka"],
                       capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0, r.stdout + r.stderr
    bez, s_magick = os.path.join(tmp, "bez"), os.path.join(tmp, "magick")   # PATH bez / s náhražkou ImageMagicku
    os.makedirs(bez)
    os.makedirs(s_magick)
    with open(os.path.join(s_magick, "magick.py"), "w", encoding="utf-8") as f:
        f.write(NAHRAZKA)
    if os.name == "nt":
        with open(os.path.join(s_magick, "magick.bat"), "w", encoding="utf-8") as f:
            f.write(f'@"{sys.executable}" -I "{os.path.join(s_magick, "magick.py")}" %*\n')
    else:
        with open(os.path.join(s_magick, "magick"), "w", encoding="utf-8") as f:
            f.write(f"#!{sys.executable}\n" + NAHRAZKA)
        os.chmod(os.path.join(s_magick, "magick"), 0o755)

    def export(magick=False):
        env = dict(os.environ, PATH=s_magick if magick else bez)
        r = subprocess.run(PY + [os.path.join(proj, "tools", "export_web.py")], capture_output=True, text=True,
                           encoding="utf-8", cwd=proj, env=env)
        return r.returncode, r.stdout + r.stderr

    def cti(p):
        return open(p, "rb").read()

    rc, out = export()
    img, zdr = (os.path.join(proj, "web", "public", s) for s in ("img", "zdroje"))
    puvodni = sorted(os.listdir(img))
    check("první export zkopíruje výřezy", rc == 0 and puvodni, out)

    # ručně přidaný obrázek (třeba foto bočního příbuzného) export nesmaže – nevytvořil ho (review #26)
    with open(os.path.join(img, "banner.jpg"), "wb") as f:
        f.write(b"\xff\xd8 rucne \xff\xd9")
    with open(os.path.join(img, "poznamka.txt"), "w", encoding="utf-8") as f:
        f.write("jiný soubor než .jpg export nechá")
    stazeny = puvodni[0]   # výřez, který uživatel smazal z vyrezy/ (zápis stažen z webu)
    shutil.move(os.path.join(proj, "vyrezy", stazeny), os.path.join(tmp, stazeny))

    rc, out = export()
    zbyva = sorted(os.listdir(img))
    check("smaže obrázek, jehož výřez ve vyrezy/ už není", rc == 0 and stazeny not in zbyva, (out, zbyva))
    check("ruční obrázek, který export nevytvořil, nechá", "banner.jpg" in zbyva, (out, zbyva))
    check("ostatní obrázky nechá", set(puvodni) - {stazeny} <= set(zbyva), (puvodni, zbyva))
    check("soubor, který není .jpg, nechá", "poznamka.txt" in zbyva, zbyva)
    check("výpis řekne, kolik smazal", "smazáno" in out, out)
    shutil.move(os.path.join(tmp, stazeny), os.path.join(proj, "vyrezy", stazeny))   # zpět – rámečky ho potřebují

    # rámečky: bez ImageMagicku jde na web kopie bez rámečků a evidence to tak zapíše (review #35)
    evidence = os.path.join(proj, "web", ".ramecky_zdroju.json")
    zv_cesta = os.path.join(proj, "data", "zvyrazneni.json")
    zv = json.load(open(zv_cesta, encoding="utf-8"))
    s_ramecky = sorted(k for k in zv if zv[k].get("boxes") and os.path.exists(os.path.join(zdr, k + ".jpg")))
    ev = json.load(open(evidence, encoding="utf-8"))
    check("bez ImageMagicku evidence nezapíše rámečky, které v souboru nejsou",
          s_ramecky and all(ev.get(k) == [] for k in s_ramecky), (s_ramecky, ev))
    rc, out = export(magick=True)
    ev = json.load(open(evidence, encoding="utf-8"))
    check("po instalaci ImageMagicku se rámečky dokreslí",
          rc == 0 and all(cti(os.path.join(zdr, k + ".jpg")).endswith(NAKRESLENO) for k in s_ramecky), out)
    check("evidence má plné snímky s rámečky", all(ev.get(k) == zv[k]["boxes"] for k in s_ramecky), ev)

    # překreslit jen snímky, jejichž rámečky se změnily (upstream #216)
    a, b = s_ramecky[:2]
    ZNACKA = b"\xff\xd8 neprekreslovat \xff\xd9"
    for k in (a, b):
        with open(os.path.join(zdr, k + ".jpg"), "wb") as f:
            f.write(ZNACKA)
    zv[a]["boxes"] = [[0.1, 0.2, 0.9, 0.5]]
    with open(zv_cesta, "w", encoding="utf-8", newline="\n") as f:
        json.dump(zv, f, ensure_ascii=False)
    rc, out = export(magick=True)
    check("snímek se změněným rámečkem se překreslí", rc == 0 and cti(os.path.join(zdr, a + ".jpg")) != ZNACKA, out)
    check("snímek beze změny rámečku se nepřekresluje", cti(os.path.join(zdr, b + ".jpg")) == ZNACKA, out)
    check("evidence má nový rámeček", json.load(open(evidence, encoding="utf-8")).get(a) == zv[a]["boxes"])

    # projekt ze starší verze (bez evidence): soubory novější než zvyrazneni.json převezme bez překreslení
    os.remove(evidence)
    with open(os.path.join(zdr, a + ".jpg"), "wb") as f:
        f.write(ZNACKA)
    t = os.path.getmtime(zv_cesta)
    os.utime(os.path.join(zdr, a + ".jpg"), (t + 10, t + 10))
    rc, out = export(magick=True)
    check("první běh s evidencí nepřekreslí snímek novější než rámečky",
          rc == 0 and cti(os.path.join(zdr, a + ".jpg")) == ZNACKA and os.path.exists(evidence), out)

    # … ale snímek starší než změna rámečků (třeba odebraný rámeček) se překreslí (review #34)
    os.remove(evidence)
    del zv[b]
    with open(zv_cesta, "w", encoding="utf-8", newline="\n") as f:
        json.dump(zv, f, ensure_ascii=False)
    t = os.path.getmtime(zv_cesta)
    os.utime(os.path.join(zdr, b + ".jpg"), (t - 10, t - 10))
    os.utime(os.path.join(proj, "zdroje", b + ".jpg"), (t - 20, t - 20))
    rc, out = export(magick=True)
    check("první běh s evidencí překreslí snímek starší než změna rámečků",
          rc == 0 and cti(os.path.join(zdr, b + ".jpg")) == cti(os.path.join(proj, "zdroje", b + ".jpg")), out)
finally:
    shutil.rmtree(tmp, ignore_errors=True)

print(f"{sum(VYSLEDKY)}/{len(VYSLEDKY)} v pořádku")
sys.exit(0 if all(VYSLEDKY) else 1)
