#!/usr/bin/env python3
"""Složí přiblížené snímky obrazovky jednoho zápisu do jednoho ostrého výřezu (prohlížeče, ze kterých nejde stáhnout).

U archivů jen v prohlížeči (MZA, SOA Třeboň, ZA Opava, FamilySearch) je snímek obrazovky celé stránky malý (~800 px)
a drobné písmo nečitelné. Postup: v prohlížeči nastav pevné přiblížení, zápis nasnímej po záběrech – posun o šířku
(výšku) pohledu minus kousek překryvu, po řádcích zleva doprava a shora dolů – a nástroj je slepí.
Na síť nesahá. Potřebuje ImageMagick (magick).

Použití (z kořene projektu):
  sloz_zaber.py <výstup.jpg> [--sloupcu N] [--prekryv auto|PX] <záběr1> <záběr2> …
      --sloupcu N   kolik záběrů je v jednom řádku (výchozí: všechny v jednom řádku)
      --prekryv     auto (výchozí) = překryv sousedních záběrů najde sám (porovnání zmenšenin v odstínech šedi),
                    číslo = pevný překryv v bodech (když se posouváš vždy o stejný kus)
Záběry musí mít stejné přiblížení a velikost (lišty prohlížeče skryj, nebo je ořízni předem vyrez.py). Šikmý posun
nástroj nehledá – posouvej jen vodorovně v řádku a svisle mezi řádky.
Šetrně: každý záběr přiblíženého místa načte dlaždice znovu. Snímej jen zápis, který čteš, tempem jako v prohlížeči
(SKILL.md, Šetrně k archivům) – ne celé stránky ani svazky. Výsledek je pro čtení; na web nanejvýš výřez zápisu.
"""
import glob, os, shutil, subprocess, sys, tempfile

for _s in (sys.stdout, sys.stderr):   # UTF-8 výstup i na Windows bez -X utf8
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")

ZMENSENI = 4   # překryv se hledá na zmenšeninách 1:4 (rychle, bez knihoven); přesnost asi ±4 body


def magick():
    m = (shutil.which("magick") or next(iter(sorted(glob.glob(r"C:\Program Files\ImageMagick*\magick.exe"))), None)
         or (os.name != "nt" and shutil.which("convert")))
    if not m:
        sys.exit("Chybí ImageMagick (příkaz magick). Nainstaluj ho (macOS: brew install imagemagick, "
                 "Windows: winget install ImageMagick.ImageMagick) a spusť nástroj znovu.")
    return m


def pgm(data):
    """Binární PGM (P5, 8 bitů) -> (šířka, výška, bajty)."""
    casti, i = [], 0
    while len(casti) < 4:
        while data[i:i + 1].isspace():
            i += 1
        if data[i:i + 1] == b"#":
            while data[i:i + 1] not in (b"\n", b""):
                i += 1
            continue
        j = i
        while not data[j:j + 1].isspace():
            j += 1
        casti.append(data[i:j])
        i = j
    if casti[0] != b"P5" or int(casti[3]) > 255:
        raise ValueError("čekám 8bitový PGM P5")
    w, h = int(casti[1]), int(casti[2])
    return w, h, data[i + 1:i + 1 + w * h]


def rozdil(a, b, w_a, w_b, h, posun, svisle=False, h_a=None):
    """Průměrný rozdíl jasu překryvu: b posunuté o `posun` bodů vůči pravému (dolnímu) okraji a. Menší = lepší."""
    soucet = n = 0
    krok = 2   # každý druhý bod stačí
    if not svisle:   # vodorovně: posledních `posun` sloupců a = prvních `posun` sloupců b
        for y in range(0, h, krok):
            ra, rb = y * w_a + (w_a - posun), y * w_b
            for x in range(0, posun, krok):
                soucet += abs(a[ra + x] - b[rb + x])
                n += 1
    else:            # svisle: posledních `posun` řádků a = prvních `posun` řádků b (společná šířka)
        for y in range(0, posun, krok):
            ra, rb = (h_a - posun + y) * w_a, y * w_b
            for x in range(0, min(w_a, w_b), krok):
                soucet += abs(a[ra + x] - b[rb + x])
                n += 1
    return soucet / n if n else 1e9


def najdi_prekryv(a, b, svisle=False):
    """Překryv (v bodech zmenšeniny) dvou sousedních záběrů; a, b = (šířka, výška, bajty). Hledá 4 %–60 % rozměru."""
    (wa, ha, da), (wb, hb, db) = a, b
    rozmer = ha if svisle else wa
    od, do = max(4, rozmer * 4 // 100), rozmer * 60 // 100
    nejlepsi = min(range(od, do + 1), key=lambda p: rozdil(da, db, wa, wb, min(ha, hb), p, svisle, ha))
    return nejlepsi


def zmensenina(M, soubor, d):
    r = subprocess.run([M, soubor + "[0]", "-colorspace", "Gray", "-resize", f"{100 // ZMENSENI}%", "-depth", "8", "pgm:-"],
                       capture_output=True, cwd=d)
    if r.returncode:
        sys.exit(f"ImageMagick nepřečetl {soubor}: {r.stderr.decode('utf-8', 'replace')[:200]}")
    return pgm(r.stdout)


def main(a):
    if len(a) < 3 or a[0] in ("-h", "--help"):
        sys.exit(__doc__.strip())
    out, a = a[0], a[1:]
    sloupcu, prekryv = None, "auto"
    while a and a[0].startswith("--"):
        if a[0] == "--sloupcu" and len(a) > 1 and a[1].isdigit() and int(a[1]) > 0:
            sloupcu, a = int(a[1]), a[2:]
        elif a[0] == "--prekryv" and len(a) > 1 and (a[1] == "auto" or a[1].isdigit()):
            prekryv, a = a[1], a[2:]
        else:
            sys.exit(__doc__.strip())
    zabery = [os.path.abspath(z) for z in a]
    for z in zabery:
        if not os.path.isfile(z):
            sys.exit(f"Záběr {z} neexistuje.")
    sloupcu = sloupcu or len(zabery)
    if len(zabery) % sloupcu:
        sys.exit(f"{len(zabery)} záběrů nejde rozdělit do řádků po {sloupcu}.")
    radky = [zabery[i:i + sloupcu] for i in range(0, len(zabery), sloupcu)]
    M = magick()
    d = tempfile.mkdtemp(dir=os.path.dirname(os.path.abspath(out)) or ".")
    try:
        hotove = []
        for ri, radek in enumerate(radky):
            dily = []   # (záběr, překryv s předchozím)
            male = zmensenina(M, radek[0], d) if prekryv == "auto" else None
            for z in radek[1:]:
                if prekryv == "auto":
                    dalsi = zmensenina(M, z, d)
                    p = najdi_prekryv(male, dalsi) * ZMENSENI
                    male = dalsi
                else:
                    p = int(prekryv)
                print(f"řádek {ri + 1}: {os.path.basename(z)} překryv {p} bodů")
                dily.append((z, p))
            args = [radek[0] + "[0]"]
            for z, p in dily:
                args += ["(", z + "[0]", "-gravity", "West", "-chop", f"{p}x0", ")"]
            hotove.append(os.path.join(d, f"radek{ri:03d}.miff"))
            subprocess.run([M, *args, "+gravity", "+append", hotove[-1]], check=True, cwd=d)
        args = [hotove[0]]
        if len(hotove) > 1:
            male = zmensenina(M, hotove[0], d) if prekryv == "auto" else None
            for h in hotove[1:]:
                if prekryv == "auto":
                    dalsi = zmensenina(M, h, d)
                    p = najdi_prekryv(male, dalsi, svisle=True) * ZMENSENI
                    male = dalsi
                else:
                    p = int(prekryv)
                print(f"řádky: {os.path.basename(h)} překryv {p} bodů")
                args += ["(", h, "-gravity", "North", "-chop", f"0x{p}", ")"]
        subprocess.run([M, *args, "+gravity", "-append", "-quality", "92", os.path.abspath(out)], check=True, cwd=d)
    finally:
        shutil.rmtree(d, ignore_errors=True)
    print(out, "– zkontroluj švy (zdvojené nebo chybějící řádky textu); jinak --prekryv s pevným číslem")


if __name__ == "__main__":
    main(sys.argv[1:])
