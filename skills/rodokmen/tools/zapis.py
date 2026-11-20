#!/usr/bin/env python3
"""Přidá nebo nahradí jednu položku v datech projektu – formát souboru zůstane stejný (odsazení 1, české znaky, konce
řádků LF), takže změna v historii je jen ta jedna položka.

Použití (z kořene projektu):
  zapis.py <soubor> <klíč> <vstup.json> [--sloucit | --prepsat]
    soubor     zaznamy | svazky | prepisy | zvyrazneni | mista | dokumenty   (= data/<soubor>.json)
    klíč       zaznamy: „klic“ zápisu; dokumenty: „img“; ostatní: klíč ve slovníku (id svazku, klíč zápisu, obec)
    vstup.json soubor s jedním objektem JSON (napiš ho nástrojem Write do pracovni/), „-“ = ze vstupu
    --sloucit  jen změní / doplní uvedená pole, ostatní pole položky nechá
    --prepsat  nahradí položku celou, i když nový vstup některá dosavadní pole nemá (ta se ztratí)
Položka se stejným klíčem se nahradí, jinak se přidá na konec. Chyběla-li by v náhradě pole, která položka měla,
nástroj nic nezmění a vypíše je (pak --sloucit, nebo --prepsat). Python skripty ani `sed -i` na data nepoužívej.

  zapis.py odkaz <osoba> <klíč zápisu> [<klíč> …]
    Přidá klíč(e) do seznamu `r` v data/osoby.py: osoba = Kekulého číslo (P), nebo část jména bočního příbuzného
    (SIDE, musí sedět na jediného). Zbytek souboru zůstane doslova, klíč musí být v zaznamy.json.

  zapis.py --smazat <klíč zápisu>
    Smaže zápis, který se ukázal jako omyl (cizí rodina): položku v zaznamy, prepisy a zvyrazneni (zbytek souborů
    beze změny) a výřezy vyrezy/<klíč>.jpg a zdroje/<klíč>.jpg přesune do pracovni/smazano_<datum>[_N]/ (jdou vrátit;
    obrázek, který používá i rodinný dokument z dokumenty.json, zůstane). Nejdřív zkontroluje všechny soubory;
    když něco selže uprostřed, vrátí vše do původního stavu.
    Když zápis ještě cituje osoba, boční příbuzný nebo text na webu (osoby.py, pribeh.md, pribehy/, zajimavosti.md,
    web.json), nic nesmaže a vypíše kde; zmínky v deníku a dalších poznámkách jen ohlásí.

  zapis.py prejmenuj <starý klíč> <nový klíč>
    Přejmenuje zápis všude: zaznamy, prepisy, zvyrazneni, odkazy `r` a `zaznamy` i zmínky v textech osoby.py,
    data/*.md a web.json (i v deníku) a výřezy vyrezy/ a zdroje/. Ostatní text souborů zůstane doslova.
"""
import ast, codecs, json, os, re, shutil, sys, tempfile, time
for _s in (sys.stdout, sys.stderr):   # UTF-8 výstup i na Windows bez -X utf8 (cp1250 neumí třeba „→“)
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stdin, "reconfigure"):   # vstup „-“ (roura, heredoc) je UTF-8; na Windows by se jinak četl v cp1250
    sys.stdin.reconfigure(encoding="utf-8-sig")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SEZNAMY = {"zaznamy": "klic", "dokumenty": "img"}   # soubory se seznamem: pole, podle kterého se položka pozná
SLOVNIKY = {"svazky", "prepisy", "zvyrazneni", "mista"}
WS = re.compile(r"\s*")


def polozky(text):
    """Položky nejvyšší úrovně: [(klíč nebo None, začátek hodnoty, konec hodnoty)] – pozice v původním textu."""
    dec, i = json.JSONDecoder(), WS.match(text).end()
    otevreni, i, out = text[i], i + 1, []
    while True:
        i = WS.match(text, i).end()
        if text[i] in "]}":
            return out
        klic = None
        if otevreni == "{":
            klic, i = dec.raw_decode(text, i)
            i = WS.match(text, WS.match(text, i).end() + 1).end()   # za dvojtečku
        _, j = dec.raw_decode(text, i)
        out.append((klic, i, j))
        i = WS.match(text, j).end()
        if text[i] == ",":
            i += 1


def jako(text, s, e, v):
    """Hodnota v JSON ve stejném stylu jako text[s:e] (na jednom řádku, nebo odsazená po jedné mezeře)."""
    if "\n" not in text[s:e]:
        return json.dumps(v, ensure_ascii=False)
    odsazeni = text[text.rfind("\n", 0, s) + 1:s]
    odsazeni = odsazeni[:len(odsazeni) - len(odsazeni.lstrip())]
    return json.dumps(v, ensure_ascii=False, indent=1).replace("\n", "\n" + odsazeni)


def bajty_pozice(src):
    """(řádek, sloupec v bajtech UTF-8) z ast → pozice v bajtech celého souboru."""
    starts, n = [0], 0
    for radek in src.split(b"\n"):
        n += len(radek) + 1
        starts.append(n)
    return lambda line, col: starts[line - 1] + col


def nacti_osoby(src):
    ns = {}
    exec(compile(src, "data/osoby.py", "exec"), ns)
    return ns


def odkaz(osoba, klice):
    path = os.path.join(ROOT, "data", "osoby.py")
    src = open(path, "rb").read()
    try:
        strom = ast.parse(src)
        pred = nacti_osoby(src)
    except Exception as e:
        sys.exit(f"data/osoby.py nejde načíst ({e}) – oprav ho nejdřív (git diff ukáže poslední změnu).")
    try:
        zaznamy = {z.get("klic") for z in json.load(open(os.path.join(ROOT, "data", "zaznamy.json"), encoding="utf-8-sig"))}
    except (OSError, ValueError) as e:
        sys.exit(f"data/zaznamy.json nejde přečíst ({e}).")
    chybi = [k for k in klice if k not in zaznamy]
    if chybi:
        sys.exit(f"Zápis {', '.join(chybi)} v data/zaznamy.json není – nejdřív ho zapiš (zapis.py zaznamy …).")

    def hodnota(jmeno):   # P = {…} / SIDE = […] na nejvyšší úrovni
        for uzel in strom.body:
            if isinstance(uzel, ast.Assign) and any(isinstance(t, ast.Name) and t.id == jmeno for t in uzel.targets):
                return uzel.value
        return None

    if re.fullmatch(r"\d+", osoba):
        P, k = hodnota("P"), int(osoba)
        volani = None
        if isinstance(P, ast.Dict):
            volani = next((v for kl, v in zip(P.keys, P.values) if isinstance(kl, ast.Constant) and kl.value == k), None)
        if volani is None:
            sys.exit(f"Osoba {k} v P (data/osoby.py) není.")
        popis, stare = f"osoba {k} ({pred['P'][k].get('n')})", pred["P"][k]
    else:
        side = hodnota("SIDE")
        kandidati = []
        for i, v in enumerate(side.elts if isinstance(side, ast.List) else []):
            n = next((kw.value.value for kw in getattr(v, "keywords", []) if kw.arg == "n" and isinstance(kw.value, ast.Constant)), "")
            if osoba.lower() in str(n).lower():
                kandidati.append((i, v, n))
        if len(kandidati) != 1:
            sys.exit(f"Bočního příbuzného „{osoba}“ " + ("v SIDE není." if not kandidati else
                     "je víc: " + "; ".join(n for _, _, n in kandidati) + " – napiš delší část jména."))
        i, volani, n = kandidati[0]
        popis, stare = f"boční příbuzný {n}", pred["SIDE"][i]
    jako_dict = isinstance(volani, ast.Call) and getattr(volani.func, "id", "") == "dict" and not volani.args
    if not (jako_dict or isinstance(volani, ast.Dict)):
        sys.exit(f"{popis}: čekal jsem dict(…) nebo {{…}} – uprav ručně.")

    nove = [k for k in klice if k not in (stare.get("r") or [])]
    if not nove:
        print(f"{popis}: zápis už má, nic neměním.")
        return
    pos = bajty_pozice(src)
    if jako_dict:
        r = next((kw.value for kw in volani.keywords if kw.arg == "r"), None)
    else:
        r = next((v for kl, v in zip(volani.keys, volani.values) if isinstance(kl, ast.Constant) and kl.value == "r"), None)
    # styl uvozovek podle souboru: první řetězec v položce (v ukázce a z importu bývají apostrofy)
    prvni = next((n for n in ast.walk(volani) if isinstance(n, ast.Constant) and isinstance(n.value, str)), None)
    apostrof = prvni is not None and src[pos(prvni.lineno, prvni.col_offset):][:1] == b"'"
    retez = lambda k: (repr(k) if apostrof else json.dumps(k, ensure_ascii=False))
    vlozit = ", ".join(retez(k) for k in nove).encode("utf-8")
    if r is not None:
        if not isinstance(r, ast.List):
            sys.exit(f"{popis}: r není seznam [ … ] – uprav ručně.")
        konec = pos(r.end_lineno, r.end_col_offset) - 1          # pozice „]“
        pred_z = src[:konec].rstrip()
        oddel = b"" if not r.elts else (b" " if pred_z.endswith(b",") else b", ")
    else:
        konec = pos(volani.end_lineno, volani.end_col_offset) - 1   # pozice „)“ nebo „}“
        pred_z = src[:konec].rstrip()
        klic_r = b"r=[" if jako_dict else (retez("r") + ": [").encode()
        oddel = (b" " if pred_z.endswith(b",") else b", ") + klic_r
        vlozit += b"]"
    if r is not None and not r.elts:   # r=[] → r=["klíč"]
        novy = src[:konec] + vlozit + src[konec:]
    else:   # za poslední prvek / argument; mezery a konec řádku před „]“ či „)“ zůstanou
        novy = pred_z + oddel + vlozit + src[len(pred_z):]

    # pojistka: soubor jde načíst, u osoby přibyly jen ty klíče a nic jiného se nezměnilo
    try:
        po = nacti_osoby(novy)
    except Exception as e:
        sys.exit(f"Úprava by rozbila data/osoby.py ({e}) – nic jsem nezapsal, uprav ručně.")
    ocekavane = dict(pred)
    if popis.startswith("osoba"):
        ocekavane["P"] = {**pred["P"], k: {**stare, "r": (stare.get("r") or []) + nove}}
    else:
        ocekavane["SIDE"] = [*pred["SIDE"][:i], {**stare, "r": (stare.get("r") or []) + nove}, *pred["SIDE"][i + 1:]]
    for jmeno in ("P", "SIDE", "LINES", "ISSUES", "HYPOTEZY", "SAME"):
        if po.get(jmeno) != ocekavane.get(jmeno):
            sys.exit(f"Úprava by změnila i {jmeno} – nic jsem nezapsal, uprav ručně.")

    zapis_bajty(path, novy)
    print(f"data/osoby.py: {popis} – přidán zápis {', '.join(nove)}")


def prepis_v_poradku(klic, v):
    """prepisy.json: web čte jen „orig“ (přepis) a „cs“ (překlad); jiné pole by na webu tiše chybělo (upstream #74)."""
    jine = sorted(set(v) - {"orig", "cs"})
    chybi = [p for p in ("orig", "cs") if not isinstance(v.get(p), str) or not v[p].strip()]
    if jine or chybi:
        sys.exit(f"Přepis „{klic}“ nezapsán: má mít jen pole „orig“ (přepis originálu) a „cs“ (český překlad), "
                 "obě neprázdná." + (f" Chybí: {', '.join(chybi)}." if chybi else "")
                 + (f" Navíc: {', '.join(jine)} – web je nezobrazí (překlad patří do „cs“)." if jine else ""))


def bez_polozky(text, poz, idx):
    """Text JSON bez položky idx – zbytek souboru zůstane doslova (stejně jako při nahrazení)."""
    if len(poz) == 1:
        zacatek = WS.match(text).end()
        return text[:zacatek + 1] + text[text.rindex("]" if text[zacatek] == "[" else "}"):]
    if idx > 0:   # od konce předchozí hodnoty: „,\n <klíč>: hodnota“
        return text[:poz[idx - 1][2]] + text[poz[idx][2]:]
    zacatek = WS.match(text, WS.match(text).end() + 1).end()      # první položka (u slovníku i s klíčem)
    za = WS.match(text, poz[0][2]).end() + 1                      # za čárku
    return text[:zacatek] + text[WS.match(text, za).end():]


def vzor_klice(klic):
    return re.compile(r"(?<![\w-])" + re.escape(klic) + r"(?![\w-])")


def soubory_dat():
    """Textové soubory v data/, kde může být klíč zápisu: *.py, *.md, web.json a příběhy v data/pribehy/."""
    data = os.path.join(ROOT, "data")
    out = [f for f in sorted(os.listdir(data)) if f.endswith((".py", ".md")) or f == "web.json"]
    if os.path.isdir(os.path.join(data, "pribehy")):
        out += ["pribehy/" + f for f in sorted(os.listdir(os.path.join(data, "pribehy"))) if f.endswith(".md")]
    return out


def kdo_cituje(klic):
    """Kde v datech je klíč zápisu ještě použitý (osoby.py, markdown, web.json)."""
    vzor = vzor_klice(klic)
    return [f for f in soubory_dat() if vzor.search(open(os.path.join(ROOT, "data", f), encoding="utf-8-sig").read())]


BLOKUJE = ("osoby.py", "pribeh.md", "zajimavosti.md", "web.json")   # z nich vzniká obsah webu – citace musí pryč


def cti_text(path):
    """Text souboru a zda začínal BOM; konce řádků zůstanou, jak jsou (CRLF se při zápisu zachová)."""
    b = open(path, "rb").read()
    bom = b.startswith(codecs.BOM_UTF8)
    return b[len(codecs.BOM_UTF8) if bom else 0:].decode("utf-8"), bom


def zapis_bajty(path, data):
    """Celý soubor naráz přes dočasný soubor s jedinečným názvem (dva běhy najednou si ho nepřepíšou)."""
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path), prefix=os.path.basename(path) + ".", suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
        if os.path.exists(path):
            shutil.copymode(path, tmp)
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise


def zapis_text(path, text, bom=False):
    zapis_bajty(path, (codecs.BOM_UTF8 if bom else b"") + text.encode("utf-8"))


def bez_duplicit(dvojice):
    """object_pairs_hook pro json.loads: stejný klíč dvakrát by json.loads tiše sloučil (jeden přepis by se ztratil)."""
    klice = [k for k, _ in dvojice]
    dvakrat = sorted({k for k in klice if klice.count(k) > 1})
    if dvakrat:
        raise ValueError(f"klíč {', '.join(dvakrat)} je tam dvakrát")
    return dict(dvojice)


def nacti_json(nazev, text):
    try:
        return json.loads(text, object_pairs_hook=bez_duplicit) if text.strip() else None
    except ValueError as e:
        sys.exit(f"data/{nazev} nejde přečíst ({e}) – nic jsem nezměnil, oprav ho nejdřív.")


def jen_nazev(klic):
    """Klíč zápisu je zároveň název souboru vyrezy/<klíč>.jpg – nesmí v něm být cesta (../foto by sahalo mimo)."""
    if not klic or klic in (".", "..") or os.path.basename(klic) != klic or re.search(r"[\\/:]", klic):
        sys.exit(f"„{klic}“ není klíč zápisu (jen název bez lomítek a „..“) – nic jsem nezměnil.")


def obrazky_dokumentu():
    """Klíče obrázků, které používá rodinný dokument (data/dokumenty.json „img“ → vyrezy/<img>.jpg)."""
    path = os.path.join(ROOT, "data", "dokumenty.json")
    if not os.path.exists(path):
        return set()
    data = nacti_json("dokumenty.json", cti_text(path)[0]) or []
    return {d.get("img") for d in data if isinstance(d, dict)} if isinstance(data, list) else set()


def proved(zmeny, presuny):
    """Zapíše texty {cesta: (text, bom)} a přesune / zkopíruje obrázky [(odkud, kam, kopie)]. Když cokoli selže,
    vrátí, co už stihl – data nezůstanou napůl změněná a stejný příkaz jde spustit znovu."""
    puvodni = {path: open(path, "rb").read() for path in zmeny}
    hotovo = []
    try:
        for path, (text, bom) in zmeny.items():
            zapis_text(path, text, bom)
        for odkud, kam, kopie in presuny:
            os.makedirs(os.path.dirname(kam), exist_ok=True)
            (shutil.copy2 if kopie else shutil.move)(odkud, kam)
            hotovo.append((odkud, kam, kopie))
    except Exception as e:
        for odkud, kam, kopie in reversed(hotovo):
            if kopie:
                os.remove(kam)
            else:
                shutil.move(kam, odkud)
        for path, b in puvodni.items():
            zapis_bajty(path, b)
        sys.exit(f"Změna selhala ({e}) – vrátil jsem soubory do původního stavu, nic se nezměnilo.")


def smazat(klic):
    jen_nazev(klic)
    zminky = kdo_cituje(klic)
    cituje = [f for f in zminky if f in BLOKUJE or f.startswith("pribehy/")]
    if cituje:
        sys.exit(f"Zápis „{klic}“ nesmazán: ještě ho cituje {', '.join('data/' + f for f in cituje)}. "
                 "Nejdřív ho odeber z „r“ osob a z textů, pak smaž znovu.")
    # nejdřív se načtou a zkontrolují všechny soubory, zapisuje se až potom (vadný prepisy.json nic nerozbije)
    zmeny, smazano = {}, []
    for nazev in ("zaznamy", "prepisy", "zvyrazneni"):
        path = os.path.join(ROOT, "data", nazev + ".json")
        if not os.path.exists(path):
            continue
        text, bom = cti_text(path)
        data = nacti_json(nazev + ".json", text)
        if not data:
            continue
        if not isinstance(data, list if nazev in SEZNAMY else dict):
            sys.exit(f"data/{nazev}.json nemá čekaný tvar – nic jsem nezměnil, oprav ho nejdřív.")
        poz = polozky(text)
        if nazev in SEZNAMY:
            idx = next((n for n, x in enumerate(data) if isinstance(x, dict) and x.get(SEZNAMY[nazev]) == klic), None)
        else:
            idx = next((n for n, (k, _, _) in enumerate(poz) if k == klic), None)
        if idx is None:
            continue
        novy = bez_polozky(text, poz, idx)
        ocekavano = [x for n, x in enumerate(data) if n != idx] if nazev in SEZNAMY else \
            {k: v for k, v in data.items() if k != klic}
        if json.loads(novy) != ocekavano:   # pojistka: smazala se právě ta jedna položka
            sys.exit(f"data/{nazev}.json: smazání by změnilo víc než jednu položku – nic jsem nezměnil.")
        zmeny[path] = (novy, bom)
        smazano.append(f"data/{nazev}.json")
    obrazky = [s for s in ("vyrezy", "zdroje") if os.path.exists(os.path.join(ROOT, s, klic + ".jpg"))]
    dokument = bool(obrazky) and klic in obrazky_dokumentu()
    presuny = []
    if obrazky and not dokument:
        # každé smazání do vlastní složky – druhé smazání téhož klíče nesmí přepsat zálohu prvního
        zaklad = os.path.join(ROOT, "pracovni", "smazano_" + time.strftime("%Y%m%d"))
        kam, n = zaklad, 1
        while any(os.path.exists(os.path.join(kam, s, klic + ".jpg")) for s in obrazky):
            n += 1
            kam = f"{zaklad}_{n}"
        for s in obrazky:
            presuny.append((os.path.join(ROOT, s, klic + ".jpg"), os.path.join(kam, s, klic + ".jpg"), False))
            smazano.append(f"{s}/{klic}.jpg → {os.path.relpath(kam, ROOT).replace(os.sep, '/')}/{s}/")
    if not smazano:
        sys.exit(f"Zápis „{klic}“ v datech není.")
    proved(zmeny, presuny)
    print(f"smazán zápis „{klic}“: " + "; ".join(smazano))
    if dokument:
        print(f"Obrázky {', '.join(s + '/' + klic + '.jpg' for s in obrazky)} nechávám – používá je rodinný dokument "
              "v data/dokumenty.json.")
    jinde = [f for f in zminky if f not in cituje]
    if jinde:
        print(f"Zmiňuje ho i {', '.join('data/' + f for f in jinde)} – text nech, odkaz na web („/zdroj/{klic}/“) "
              "případně uprav (npm run data ho ohlásí jako nefunkční).")
    print("Do deníku (research_log.md) zapiš, proč zápis nepatří k rodině – ať ho příště nikdo nenajde „znovu“.")


def prejmenovano(x, stary, novy):
    """Struktura dat s klíčem zápisu `stary` nahrazeným `novy` ve všech řetězcích (na kontrolu výsledku)."""
    if isinstance(x, str):
        return vzor_klice(stary).sub(novy, x)
    if isinstance(x, list):
        return [prejmenovano(v, stary, novy) for v in x]
    if isinstance(x, tuple):
        return tuple(prejmenovano(v, stary, novy) for v in x)
    if isinstance(x, dict):
        return {prejmenovano(k, stary, novy): prejmenovano(v, stary, novy) for k, v in x.items()}
    return x


def prejmenuj(stary, novy):
    jen_nazev(stary)
    if not re.fullmatch(r"[a-z0-9_]+", novy):
        sys.exit(f"Nový klíč „{novy}“: jen malá písmena bez diakritiky, číslice a podtržítka (obec_druh_jmeno_rok).")
    try:
        zaz = json.load(open(os.path.join(ROOT, "data", "zaznamy.json"), encoding="utf-8-sig"))
    except (OSError, ValueError) as e:
        sys.exit(f"data/zaznamy.json nejde přečíst ({e}).")
    klice = {z.get("klic") for z in zaz if isinstance(z, dict)}
    if stary not in klice:
        sys.exit(f"Zápis „{stary}“ v data/zaznamy.json není.")
    obsazeno = klice | obrazky_dokumentu()
    for nazev in ("prepisy.json", "zvyrazneni.json"):   # přepis pod novým klíčem by se sloučil se starým
        path = os.path.join(ROOT, "data", nazev)
        data = nacti_json(nazev, cti_text(path)[0]) if os.path.exists(path) else None
        obsazeno |= set(data) if isinstance(data, dict) else set()
    if novy in obsazeno or kdo_cituje(novy):
        sys.exit(f"Klíč „{novy}“ už v datech je – vyber jiný.")
    for slozka in ("vyrezy", "zdroje"):
        if os.path.exists(os.path.join(ROOT, slozka, novy + ".jpg")):
            sys.exit(f"{slozka}/{novy}.jpg už existuje – vyber jiný klíč.")
    vzor = vzor_klice(stary)
    zmeny = {}   # soubor → nový text; zapisuje se až po kontrole všech souborů
    for nazev in dict.fromkeys(("zaznamy.json", "prepisy.json", "zvyrazneni.json", *soubory_dat())):
        path = os.path.join(ROOT, "data", nazev)
        if not os.path.exists(path):
            continue
        text, bom = cti_text(path)
        nove = vzor.sub(novy, text)
        if nove == text:
            continue
        if nazev.endswith(".json"):   # pojistka: změnil se jen ten klíč (a žádný klíč není dvakrát)
            pred = nacti_json(nazev, text)
            try:
                po = json.loads(nove, object_pairs_hook=bez_duplicit)
            except ValueError as e:
                sys.exit(f"data/{nazev}: přejmenování by rozbilo soubor ({e}) – nic jsem nezměnil.")
            if po != prejmenovano(pred, stary, novy):
                sys.exit(f"data/{nazev}: přejmenování by změnilo i něco jiného – nic jsem nezměnil.")
        elif nazev == "osoby.py":
            try:
                pred, po = nacti_osoby(text), nacti_osoby(nove)
            except Exception as e:
                sys.exit(f"data/osoby.py nejde načíst ({e}) – nic jsem nezměnil.")
            for jmeno in set(pred) | set(po):
                if jmeno != "__builtins__" and po.get(jmeno) != prejmenovano(pred.get(jmeno), stary, novy):
                    sys.exit(f"data/osoby.py: přejmenování by změnilo i {jmeno} – nic jsem nezměnil, uprav ručně.")
        zmeny[path] = (nove, bom)
    # obrázek, který používá i rodinný dokument (dokumenty.json „img“), zůstane dokumentu – zápis dostane kopii
    dokument = stary in obrazky_dokumentu()
    presuny = [(os.path.join(ROOT, s, stary + ".jpg"), os.path.join(ROOT, s, novy + ".jpg"), dokument)
               for s in ("vyrezy", "zdroje") if os.path.exists(os.path.join(ROOT, s, stary + ".jpg"))]
    proved(zmeny, presuny)
    print(f"přejmenováno „{stary}“ → „{novy}“: "
          + ", ".join(os.path.relpath(p, ROOT).replace(os.sep, "/") for p in [*zmeny, *(k for _, k, _ in presuny)]))
    if dokument and presuny:
        print(f"Obrázky „{stary}“ používá i rodinný dokument (data/dokumenty.json) – zůstaly mu, zápis má kopii.")


def main():
    if len(sys.argv) == 3 and sys.argv[1] == "--smazat":
        return smazat(sys.argv[2])
    if sys.argv[1:2] == ["prejmenuj"]:
        if len(sys.argv) != 4:
            sys.exit(__doc__)
        return prejmenuj(sys.argv[2], sys.argv[3])
    if sys.argv[1:2] == ["odkaz"]:
        if len(sys.argv) < 4:
            sys.exit(__doc__)
        return odkaz(sys.argv[2], sys.argv[3:])
    args = [a for a in sys.argv[1:] if a not in ("--sloucit", "--prepsat")]
    sloucit, prepsat = "--sloucit" in sys.argv, "--prepsat" in sys.argv
    if sloucit and prepsat:
        sys.exit("--sloucit a --prepsat nejdou spolu – vyber jedno.")
    if len(args) != 3 or args[0] not in {*SEZNAMY, *SLOVNIKY}:
        sys.exit(__doc__)
    nazev, klic, vstup = args
    try:
        obj = json.load(sys.stdin if vstup == "-" else open(vstup, encoding="utf-8-sig"))
    except (OSError, ValueError) as e:
        sys.exit(f"Vstup {vstup} není platný JSON: {e}")
    zapis(nazev, klic, obj, sloucit, prepsat)


OBNOVIT = {"snimku"}   # u svazku z archivu vždy podle archivu (počet snímků se mění)


def zapis_svazek(klic, polozka):
    """Svazek z archivu (příkaz „svazek“ v aron_img.py, portafontium.py, ebadatelna.py): chybějící pole doplní,
    počet snímků obnoví; jinou neprázdnou hodnotu, kterou už svazek má (třeba ručně rozšířený popis), nechá
    a vypíše rozdíl."""
    path = os.path.join(ROOT, "data", "svazky.json")
    try:
        stare = json.load(open(path, encoding="utf-8-sig")).get(klic) if os.path.exists(path) else None
    except (OSError, ValueError, AttributeError):
        stare = None   # vadný soubor ohlásí zapis()
    nove = dict(polozka)
    if isinstance(stare, dict):
        for k, v in polozka.items():
            if k not in OBNOVIT and stare.get(k) not in (None, "") and stare.get(k) != v:
                del nove[k]
                print(f"svazek {klic}: „{k}“ nechávám, jak je v data/svazky.json (archiv uvádí: "
                      f"{json.dumps(v, ensure_ascii=False)[:120]}). Přepsat podle archivu: zapis.py svazky {klic} "
                      "<vstup.json> --sloucit")
    zapis("svazky", klic, nove, sloucit=True)


def zapis(nazev, klic, obj, sloucit=False, prepsat=False):
    """Zapíše jednu položku do data/<nazev>.json, zbytek souboru nechá doslova. Volají ho i jiné nástroje
    (`aron_img.py`, `portafontium.py`, `ebadatelna.py` u příkazu svazek – přes zapis_svazek, ať ručně doplněná
    a upravená pole svazku zůstanou)."""
    if not isinstance(obj, dict):
        sys.exit("Vstup musí být jeden objekt JSON ({…}).")
    path = os.path.join(ROOT, "data", nazev + ".json")
    if len(obj) == 1 and isinstance(obj.get(klic), dict):   # {"klíč": {…}} – rozbalit jedinou položku
        obj = obj[klic]
    vnorene = [k for k, x in obj.items() if isinstance(x, dict)]
    if nazev in ("zaznamy", "prepisy", "zvyrazneni") and vnorene:
        # dřív se vstup {"k1": {…}, "k2": {…}} uložil celý pod klíč z příkazové řádky (vznikl nesmyslný klíč „x“)
        sys.exit(f"Vstup vypadá jako víc položek najednou ({', '.join(vnorene[:4])}). zapis.py zapisuje jednu položku: "
                 "pro každý klíč spusť příkaz zvlášť, nebo použij tools/nalez.py.")
    seznam = nazev in SEZNAMY
    if seznam and obj.setdefault(SEZNAMY[nazev], klic) != klic:
        sys.exit(f"Klíč „{klic}“ nesedí s „{SEZNAMY[nazev]}“ ve vstupu („{obj[SEZNAMY[nazev]]}“).")
    text = open(path, encoding="utf-8-sig").read() if os.path.exists(path) else ""
    try:
        data = json.loads(text) if text.strip() else ([] if seznam else {})
        if not isinstance(data, list if seznam else dict):
            raise ValueError("čekal jsem " + ("seznam [ … ]" if seznam else "slovník { … }"))
    except ValueError as e:
        sys.exit(f"data/{nazev}.json nejde přečíst ({e}) – oprav ho nejdřív (git diff ukáže poslední změnu).")

    poz = polozky(text) if data else []
    if seznam:
        idx = next((n for n, x in enumerate(data) if isinstance(x, dict) and x.get(SEZNAMY[nazev]) == klic), None)
    else:
        idx = next((n for n, (k, _, _) in enumerate(poz) if k == klic), None)
    stare = None if idx is None else (data[idx] if seznam else data[klic])
    nove = {**stare, **obj} if sloucit and isinstance(stare, dict) else obj
    ztracena = sorted(set(stare) - set(nove)) if isinstance(stare, dict) and not prepsat else []
    if ztracena:   # tiché přepsání by smazalo pole (např. podrobný seznam obcí svazku)
        sys.exit(f"data/{nazev}.json: „{klic}“ už existuje a náhrada nemá pole {', '.join(ztracena)} – nic jsem "
                 "nezměnil. Doplnit / změnit jen uvedená pole: --sloucit; nahradit celé (pole se ztratí): --prepsat.")
    if not poz:   # prázdný nebo nový soubor
        text = json.dumps([nove] if seznam else {klic: nove}, ensure_ascii=False, indent=1) + "\n"
    elif idx is not None:   # nahradit jen text té jedné položky, zbytek souboru zůstane doslova
        _, s, e = poz[idx]
        text = text[:s] + jako(text, s, e, nove) + text[e:]
    else:   # přidat za poslední položku ve stejném stylu
        _, s, e = poz[-1]
        radek = text[text.rfind("\n", 0, s) + 1:s]
        odsazeni = radek[:len(radek) - len(radek.lstrip())]
        text = (text[:e] + ",\n" + odsazeni + ("" if seznam else json.dumps(klic, ensure_ascii=False) + ": ")
                + jako(text, s, e, nove) + text[e:])
    if nazev == "prepisy":
        prepis_v_poradku(klic, nove)
    json.loads(text)   # pojistka: výsledek musí být platný JSON

    zapis_text(path, text)   # celý soubor naráz – při chybě nezůstane rozepsaný
    print(f"data/{nazev}.json: {'přidáno' if idx is None else 'změněno'} „{klic}“")


if __name__ == "__main__":
    main()
