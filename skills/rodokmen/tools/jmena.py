#!/usr/bin/env python3
"""Volné porovnání jmen z matrik (společné pro graf.py a rodiny.py): Johann = Jan, Nowak = Novák = Nováková.

Shoda jmen je jen námět k ověření v zápisu, nikdy důkaz. Jen standardní knihovna.
"""
import re, unicodedata

# Křestní jména: latinské a německé tvary z matrik → český tvar (bez diakritiky, malá písmena).
KRESTNI = {
    "vaclav": "wenceslaus wenzel wenzl wentzel venceslaus wenceslai", "jan": "joannes johannes johann hans joanne joannis",
    "katerina": "catharina katharina katharine catherina", "ondrej": "andreas andre andreae", "jiri": "georgius georg georgii",
    "antonin": "antonius anton antoni", "antonie": "antonia", "frantisek": "franciscus franz francisci",
    "frantiska": "francisca franziska", "josef": "josephus joseph josephi", "josefa": "josepha",
    "rozalie": "rosalia rozalia", "anna": "anne", "marie": "maria", "terezie": "theresia teresia theresa terezia therese",
    "vavrinec": "laurentius lorenz laurenz", "mikulas": "nicolaus nikolaus nicolai", "martin": "martinus",
    "matej": "matthias mathias matthaeus", "petr": "petrus peter", "pavel": "paulus paul", "tomas": "thomas",
    "jakub": "jacobus jakob jacob", "vojtech": "adalbertus adalbert", "augustin": "augustinus", "dorota": "dorothea",
    "magdalena": "magdalene", "veronika": "veronica", "barbora": "barbara", "alzbeta": "elisabetha elisabeth",
    "ludmila": "ludmilla", "justina": "justine", "judita": "judith", "tobias": "tobiae", "karel": "carolus karl carl",
    "ignac": "ignatius ignaz", "alois": "aloysius aloys", "simon": "simeon", "stepan": "stephanus stephan",
    "vit": "vitus veit", "zuzana": "susanna susana zuzanna", "kristina": "christina", "jindrich": "henricus heinrich",
    "bartolomej": "bartholomaeus", "filip": "philippus philipp", "rehor": "gregorius gregor", "michal": "michael",
    "lukas": "lucas", "marek": "marcus", "daniel": "danielus", "adam": "adamus", "johana": "johanna",
    "anezka": "agnes", "marketa": "margaretha margarethe margareta",
}
_KR = {}
for _cz, _vs in KRESTNI.items():
    _KR[_cz] = _cz
    for _v in _vs.split():
        _KR[_v] = _cz


def bez_diakritiky(s):
    return "".join(c for c in unicodedata.normalize("NFKD", s or "") if not unicodedata.combining(c)).lower()


def krestni_klic(s):
    """„Johann Georg“ → „jan“ (první křestní jméno v českém tvaru)."""
    s = re.sub(r"[^a-z ]", " ", bez_diakritiky(s)).split()
    return _KR.get(s[0], s[0]) if s else ""


def prijmeni_klic(s):
    """Volný klíč příjmení: Novák, Nowak, Nowák, Nováková, Nováčka → novak; Petráček, Petráčková → petrak."""
    s = re.sub(r"[^a-z]", "", bez_diakritiky(s))
    s = s.replace("sch", "s").replace("cz", "c").replace("w", "v").replace("y", "i").replace("ia", "a")
    s = s.replace("tz", "c").replace("ch", "#").replace("c", "k").replace("#", "ch")
    for kon in ("ovich", "ova", "ovi", "ove", "a"):     # ženský tvar a koncovky → kmen (aspoň 3 písmena: Kufa = Kufová)
        if len(s) - len(kon) >= 3 and s.endswith(kon):
            s = s[: -len(kon)]
            break
    if s.endswith("ek"):                                # pohyblivé e: Javůrek / Javůrková, Doleček / Dolečková
        s = s[:-2] + "k"
    s = re.sub(r"(.)\1+", r"\1", s)
    return s


def kmeny_prijmeni(n):
    """Kmeny příjmení z celého jména v osoby.py (bez křestního): první 3 písmena klíče prijmeni_klic, takže
    Kufa = Kufová = Kuffa, Nowak = Novák. Varianty v závorce (Hána (Hahn)) jsou další kandidáti, „roz.“, „starší“,
    „mladší“ ne. Skrytá osoba → prázdná množina. Používá kontrola.py (otec 2n a dítě n mají mít stejné příjmení)."""
    if not isinstance(n, str) or "skryt" in n.lower():   # „(jméno skryto)“
        return set()
    out = set()
    for w in re.sub(r"[(),]", " ", n).split()[1:]:
        w = re.sub(r"[^a-z]", "", bez_diakritiky(w))
        if len(w) >= 3 and not w.startswith(("roz", "star", "mlad")):
            out.add(prijmeni_klic(w)[:3])
    return out


def osoba_klic(jmeno):
    """„Mathias Nowak (?)“ → („matej“, „novak“); jen jedno slovo → (křestní, "")."""
    cast = [c for c in re.sub(r"\(\?\)|\[.*?\]|†|\+", " ", jmeno or "").split() if c]
    if not cast:
        return None
    if len(cast) == 1:
        return (krestni_klic(cast[0]), "")
    return (krestni_klic(cast[0]), prijmeni_klic(cast[-1]))
