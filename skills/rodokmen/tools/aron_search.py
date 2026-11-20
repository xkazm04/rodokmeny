#!/usr/bin/env python3
"""Hledání svazků na portálu ARON (SOA Zámrsk, fond Sbírka matrik Východočeského kraje).
Použití: aron_search.py "<text v popisu, např. obec>" [filtr názvu fondu] [max]
  Víc slov oddělených čárkou musí být v popisu všechna: "Vinice,Hořice" = Vinice ve farnosti Hořice
  (stejnojmenných obcí bývá víc – výsledky jsou proto seřazené podle farnosti / první obce v popisu).
Vypíše: apu_id | signatura, druh a roky | popis (obce, které svazek pokrývá).
Samostatné svazky rejstříků („index NAROZENÝCH…“) vypíše zvlášť nahoře – hledej nejdřív v nich, kniha bez rejstříku
se čte stranu po straně.
Vypisuje i svazky bez snímků (hlavně 20. století) – jestli je svazek online, ukáže `aron_img.py <apu_id> info` (scans: 0 = není)."""
import json, re, sys, time, urllib.request
if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):   # nápověda místo pádu
    sys.exit(__doc__.strip())
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__))); import slusne  # noqa: E402 – brzda proti zablokování archivem (společný limit dotazů, tools/slusne.py)
for _s in (sys.stdout, sys.stderr):   # UTF-8 výstup i na Windows bez -X utf8 (cp1250 neumí třeba „→“)
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")

API = "https://aron.vychodoceskearchivy.cz/api/aron"

def post(path, body, tries=3):
    req = urllib.request.Request(API + path, data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    for attempt in range(tries):   # ARON občas neodpoví (timeout) – zkusit znovu s pauzou
        try:
            with urllib.request.urlopen(req, timeout=90) as r:
                return json.load(r)
        except OSError:
            if attempt == tries - 1:
                raise
            time.sleep(5 * (attempt + 1))

def search(desc, name="Sbírka matrik Východočeského kraje", maxn=500):
    out, offset = [], 0
    while True:
        d = post("/apu/listview?listType=SEARCH", {
            "filters": [{"field": "type", "operation": "EQ", "value": "ARCH_DESC"},
                        {"operation": "FTXF", "field": "name", "value": name},
                        *({"operation": "FTXF", "field": "description", "value": w.strip()}
                          for w in desc.split(",") if w.strip())],
            "sort": [], "offset": offset, "size": 100, "aggregations": []})
        items = d.get("items", [])
        out += items
        offset += len(items)
        if not items or offset >= min(d.get("count", 0), maxn):
            return out, d.get("count")

def _druh_a_misto(desc):
    """Rozdělí popis na úvodní druh knihy („římskokatolická matrika NAROZENÝCH“, „… index ODDANÝCH“) a zbytek."""
    parts = (desc or "").split(", ")
    druh = []
    while parts and re.search(r"matrika|index", parts[0]):
        druh.append(parts.pop(0))
    return ", ".join(druh), ", ".join(parts)

def place(desc):
    """Řadicí klíč: popis bez úvodního druhu knihy („římskokatolická matrika NAROZENÝCH, …“), tj. od farnosti / první obce."""
    return re.sub(r"^\(?(farnost|soudní okres) ", "", _druh_a_misto(desc)[1])

def je_index(item):
    """Samostatný svazek rejstříku: druh knihy v popisu (nebo název) obsahuje „index“ / „rejstřík“."""
    return bool(re.search(r"index|rejst[řr]ík", _druh_a_misto(item.get("description"))[0] + " " + item.get("name", ""), re.I))

def radky(items):
    """Řádky výpisu: rejstříky zvlášť nahoře (upstream #214), pak ostatní svazky; obojí podle farnosti."""
    def radek(i):
        n = i["name"].split(": ", 1)[-1]
        return " | ".join((i["id"], n.replace("Sbírka matrik Východočeského kraje, ", ""), (i.get("description") or "")[:220]))
    serad = sorted(items, key=lambda i: (place(i.get("description")), i["name"]))
    indexy = [radek(i) for i in serad if je_index(i)]
    ostatni = [radek(i) for i in serad if not je_index(i)]
    if not indexy:
        return ostatni
    return ([f"--- rejstříky (index) – hledej nejdřív v nich: {len(indexy)} ---"] + indexy
            + [f"--- matriky a ostatní svazky: {len(ostatni)} ---"] + ostatni)

if __name__ == "__main__":
    desc = sys.argv[1]
    name = sys.argv[2] if len(sys.argv) > 2 and sys.argv[2] else "Sbírka matrik Východočeského kraje"
    maxn = int(sys.argv[3]) if len(sys.argv) > 3 else 500
    items, cnt = search(desc, name, maxn)
    print("count", cnt)
    for r in radky(items):
        print(r)
