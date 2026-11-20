"""Test výpisu `aron_search.py`: samostatné svazky rejstříků („index NAROZENÝCH…“) jsou zvlášť nahoře, ostatní
svazky pod nimi, obojí podle farnosti (upstream #214 – pomocníci rejstříky mezi matrikami přehlédli).

Z kořene repozitáře:
  python3 -I tests/aron/test_hledani.py skills/rodokmen/tools
  (Windows: python -I -X utf8 …)
Na archiv nechodí: testuje jen řazení a rozdělení výpisu (funkce `radky`).
"""
import importlib.util, os, sys, tempfile

TOOLS = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else
                        os.path.join(os.path.dirname(__file__), "..", "..", "skills", "rodokmen", "tools"))
os.environ["SLUSNE_STAV"] = tempfile.mkdtemp(prefix="aron_hledani_slusne_")
VYSLEDKY = []


def check(nazev, ok, detail=""):
    VYSLEDKY.append(bool(ok))
    print(("OK  " if ok else "CHYBA ") + nazev + ("" if ok else "\n    " + str(detail).replace("\n", "\n    ")))


argv = sys.argv
sys.argv = ["aron_search.py", "x"]   # modul bez argumentu vypíše nápovědu a skončí
try:
    spec = importlib.util.spec_from_file_location("aron_search", os.path.join(TOOLS, "aron_search.py"))
    aron = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(aron)
finally:
    sys.argv = argv

F = "Sbírka matrik Východočeského kraje: Sbírka matrik Východočeského kraje, "
items = [
    dict(id="m1", name=F + "N Holice 05", description="římskokatolická matrika NAROZENÝCH, farnost Holice, Holice, Dašice"),
    dict(id="i1", name=F + "I Holice 12", description="římskokatolický index NAROZENÝCH, farnost Holice, Holice"),
    dict(id="m2", name=F + "O Bohdaneč 03", description="římskokatolická matrika ODDANÝCH, farnost Bohdaneč, Bohdaneč"),
    dict(id="i2", name=F + "I Bohdaneč 01", description="římskokatolický index ODDANÝCH, farnost Bohdaneč, Bohdaneč, Holice"),
    dict(id="m3", name=F + "Z Holice 07", description="římskokatolická matrika ZEMŘELÝCH, farnost Holice, Indexov"),
]
r = aron.radky(items)
ids = [x.split(" | ")[0] for x in r]
check("rejstříky jsou nahoře pod vlastním nadpisem", r[0].startswith("--- rejstříky") and ids[1:3] == ["i2", "i1"], r)
check("pod nimi nadpis a ostatní svazky podle farnosti", r[3].startswith("--- matriky") and ids[4:] == ["m2", "m1", "m3"], r)
check("počty v nadpisech", ": 2 ---" in r[0] and ": 3 ---" in r[3], r)
check("obec „Indexov“ v popisu matriky ji nedělá rejstříkem", not aron.je_index(items[4]))
check("řádek má apu | signaturu | popis", r[1] == "i2 | I Bohdaneč 01 | " + items[3]["description"], r[1])

bez = aron.radky([items[0], items[2]])
check("bez rejstříků výpis beze změny (bez nadpisů)", [x.split(" | ")[0] for x in bez] == ["m2", "m1"], bez)

print(f"\n{sum(VYSLEDKY)}/{len(VYSLEDKY)} OK")
sys.exit(0 if all(VYSLEDKY) else 1)
