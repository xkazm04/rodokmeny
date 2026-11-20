#!/usr/bin/env python3
"""Obsahové kontroly dat, které dřív našla jen ruční kontrola vyšším modelem (Opus, 11. 11. 2026).

Volá je tools/kontrola.py (upozornění). Samostatně: `python -I -X utf8 tools/kontrola_dat.py` vypíše jen tyto nálezy.

Hlídá:
  1. roky v `y` nesedí s fakty `* …` a `† …` (web bere `y`, výpočty věku fakta)
  2. fakta mají rok narození / úmrtí, ale `y` ho nemá
  3. rok v `y` u doložené osoby pochází jen z cizího stromu (MyHeritage, „strom …“) – web ho ukáže jako doložený
  4. osoba cituje v `r` zápis, který sám o sobě říká, že je jen kandidát – web ho ukáže jako doklad
  5. zastaralé věty („V matrice neověřeno“, „křest se nečetl“) u osoby, která už zápis má
  6. ženich nebo nevěsta je v přepisu sňatku „ledig/svobodný“, ale osoba má u téhož sňatku „vdovec/vdova“ (nebo naopak)
"""
import json, os, re, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))   # -I nepřidá složku skriptu
import datumy  # noqa: E402 – jedno čtení dat pro všechny kontroly

for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROK = re.compile(r"(?<!\d)(1[0-9]{3}|20[0-9]{2})(?!\d)")
CIZI = re.compile(r"\bMH\b|MyHeritage|\bstrom\w*|Geni\b|FamilySearch.{0,20}strom", re.I)
KANDIDAT = re.compile(r"kandidát|jen kandid|nepotvrzen", re.I)
ZASTARALE = re.compile(r"V matrice neověřeno|(?:křest|sňatek|úmrtí|zápis)[^.]{0,30}\bse\s+nečetl[ay]?\b"
                       r"|\bnečetl[ay]?\s+se\b|matrika nečtena", re.I)
SVOBODNY = re.compile(r"\bledig\b|\bsvobodn[áýa]\b|\bcoelebs\b|\bvirgo\b|\bjuvenis\b", re.I)
VDOVEC = re.compile(r"\bWitwer\b|\bWitwe\b|\bvdov(?:ec|a)\b|\bviduus\b|\bvidua\b", re.I)
VDOVEC_M = re.compile(r"\bvdovec\b|\bWitwer\b|\bviduus\b", re.I)   # fakt o sobě: muž
VDOVA_Z = re.compile(r"\bvdova\b|\bWitwe\b|\bvidua\b", re.I)       # fakt o sobě: žena


def roky_y(y):
    """(narození, úmrtí) z pole y jako datumy.Datum (interval) nebo None – čte tools/datumy.py („asi 1760–64“,
    „* asi 1620–1630“, „1720–85“, „před 1740“) stejně jako ostatní kontroly."""
    return datumy.z_y(y)


def fakta_rok(p, znak):
    """[(Datum, text faktu)] z faktů o narození (* nebo „pokřtěn …“) či úmrtí († nebo „pohřben …“)."""
    out = []
    for f in p.get("f") or []:
        x = datumy.fakt(f)
        if x and x[0] == znak and x[1]:
            out.append((x[1], f))
    return out


def nesedi(d, fakta):
    """Rok v y nesedí s žádným faktem ani s tolerancí 1 roku (pro všechna možná data v intervalech)."""
    return d and fakta and not any(datumy.prekryv(d, x, dni=366) for x, _ in fakta)


def radky_snoubencu(orig):
    """Řádky přepisu, které popisují ženicha a nevěstu: (kdo, text)."""
    out = []
    for l in (orig or "").splitlines():
        m = re.match(r"\s*\[(Bräutigam|Braut|Sponsus|Sponsa|Ženich|Nevěsta|Copulati)[^\]]*\]\s*(.*)", l, re.I)
        if m:
            out.append((m.group(1).lower(), m.group(2)))
    return out


def kontroly(P, SIDE, zaz, prep):
    warn = []
    zaz_k = {z.get("klic"): z for z in zaz}
    for k, p in sorted(P.items()):
        n = p.get("n")
        if p.get("st") == "unk":
            continue
        yn, yz = roky_y(p.get("y"))
        fn, fz = fakta_rok(p, "*"), fakta_rok(p, "†")
        # 1 a 2: y × fakta
        if nesedi(yn, fn):
            warn.append(f"osoba {k} ({n}): y má narození {yn.text}, fakta {fn[0][0].text} – sjednoť (web bere y)")
        if nesedi(yz, fz):
            warn.append(f"osoba {k} ({n}): y má úmrtí {yz.text}, fakta {fz[0][0].text} – sjednoť (web bere y)")
        y = p.get("y") or ""
        vlastni_fn = [x for x in fn if not CIZI.search(x[1])]   # rok jen z cizího stromu do y nepatří
        if vlastni_fn and p.get("st") != "fam":
            if not y.strip():
                warn.append(f"osoba {k} ({n}): fakta mají narození {vlastni_fn[0][0].text}, ale y je prázdné – doplň y (web ukazuje y)")
        # 3: rok v y jen z cizího stromu u doložené osoby
        if p.get("st") == "doc":
            for d, f in fn + fz:
                if d.rok and CIZI.search(f) and re.search(rf"{d.rok}(?!\s*\(\?\))", y):   # „1930 (?)“ = nejistota přiznaná
                    warn.append(f"osoba {k} ({n}): rok {d.rok} v y je jen z cizího stromu („{f[:60]}“) – "
                                "u doložené osoby ho web ukáže jako doložený; dej do y jen roky ze zápisů")
                    break
        # 4: citovaný zápis je jen kandidát
        for r in p.get("r") or []:
            z = zaz_k.get(r) or {}
            if KANDIDAT.search(str(z.get("nazev", ""))) or re.search(r"^[^.]{0,80}\bjen kandidát", str(z.get("shrnuti", "")), re.I):
                warn.append(f"osoba {k} ({n}): cituje zápis {r}, který je podle názvu/shrnutí jen kandidát – "
                            "web ho ukáže jako doklad; přesuň do poznámky, HYPOTEZY nebo SIDE")
        # 5: zastaralé věty
        if p.get("r"):
            m = ZASTARALE.search(str(p.get("note", "")))
            if m:
                warn.append(f"osoba {k} ({n}): poznámka říká „{m.group(0)}“, ale osoba už cituje {len(p['r'])} zápis(ů) – "
                            "zastaralá věta?")
        # 6: svobodný × vdovec u sňatku
        for r in p.get("r") or []:
            z = zaz_k.get(r) or {}
            if z.get("druh") != "O":
                continue
            rok = ROK.search(str(z.get("datum", "")))
            if not rok:
                continue
            fakt = [f for f in p.get("f") or [] if isinstance(f, str) and "×" in f and rok.group(1) in f]
            if not fakt:
                continue
            muz = k % 2 == 0 if k > 1 else p.get("sex") == "M"
            # „vdovec“ u muže / „vdova“ u ženy – jinak jde o partnera („× … Sedláková (vdova)“)
            osoba_vdov = any((VDOVEC_M if muz else VDOVA_Z).search(f) for f in fakt)
            radky = radky_snoubencu((prep.get(r) or {}).get("orig", ""))
            for kdo, text in radky:
                je_on = kdo in ("bräutigam", "sponsus", "ženich")
                if muz is None or je_on != muz or kdo == "copulati":
                    continue
                if osoba_vdov and SVOBODNY.search(text) and not VDOVEC.search(text):
                    warn.append(f"osoba {k} ({n}): u sňatku {r} má fakta „vdovec/vdova“, přepis „{SVOBODNY.search(text).group(0)}“ – "
                                "přečti na výřezu sloupec ledig/Witwer (porovnej s řádkem nad a pod)")
    return warn


def main():
    ns = {}
    exec(open(os.path.join(ROOT, "data", "osoby.py"), encoding="utf-8-sig").read(), ns)
    j = lambda f, d: json.load(open(os.path.join(ROOT, "data", f), encoding="utf-8-sig")) if os.path.exists(os.path.join(ROOT, "data", f)) else d
    w = kontroly(ns.get("P", {}), ns.get("SIDE", []), j("zaznamy.json", []), j("prepisy.json", {}))
    for x in w:
        print("upozornění:", x)
    print(f"{len(w)} upozornění" if w else "Bez nálezů.")


if __name__ == "__main__":
    main()
