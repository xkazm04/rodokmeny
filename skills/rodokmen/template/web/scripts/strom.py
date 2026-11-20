#!/usr/bin/env python3
"""Data for the family-view page /strom/ (Strom).

tools/export_web.py calls build() with the site data (ancestors, already privacy-sanitised) and the SIDE list from
data/osoby.py (side relatives with the optional keys id / v / koho / rodice / sex); it writes
web/src/generated/strom.json: one node per person with parents, spouses and children. Run on its own, it reads
web/src/data/site.json and data/osoby.py itself (after export_web.py).
"""
import json
import os
import re

WEB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.dirname(WEB)
SITE = os.path.join(WEB, "src", "data", "site.json")
OUT = os.path.join(WEB, "src", "generated", "strom.json")


def year_of(text):
    m = re.search(r"\d{4}", text or "")
    return int(m.group(0)) if m else 9999


def split_name(n):
    """'Josef Novák (* 1865)' -> ('Josef Novák', '* 1865'). Only the last parenthesis holds the years, and only when it
    contains a digit: 'Péter (Peter) Marko (* 1901)' -> ('Péter (Peter) Marko', '* 1901'), 'Anna (?)' -> ('Anna (?)', '')."""
    m = re.match(r"^(.*?)\s*\(([^()]*)\)\s*$", n)
    if m and re.search(r"\d", m.group(2)):
        return m.group(1).strip(), m.group(2).strip()
    return n.strip(), ""


def guess_sex(name):
    last = name.split()[-1] if name.split() else ""
    return "F" if last.endswith(("ová", "á")) else "M"



def main():
    with open(SITE, encoding="utf-8-sig") as f:
        site = json.load(f)
    ns = {}
    exec(open(os.path.join(ROOT, "data", "osoby.py"), encoding="utf-8-sig").read(), ns)   # utf-8-sig: BOM z Windows
    build(site, ns.get("SIDE", []))


def build(site, side):
    people = site["people"]
    by_k = {p["k"]: slug for slug, p in people.items()}
    for a, slug in (site.get("aliases") or {}).items():
        by_k[int(a)] = slug
    line_color = {l["k"]: l.get("color") for l in site.get("lines", {}).values()}
    line_name = {l["k"]: l.get("name") for l in site.get("lines", {}).values()}
    rec_title = {r["key"]: dict(title=r.get("title", r["key"]), date=r.get("date", "")) for r in site.get("records", [])}

    def avatar(slug, p):
        """A portrait only: an image named *portret* or whose caption starts with the person's name."""
        first = p["name"].split()[0] if p.get("name") else ""
        for d in site.get("docs", []):
            if slug not in d.get("people", []):
                continue
            img, cap = d.get("img", ""), d.get("caption", "")
            if "portret" in img or (first and cap.startswith(p["name"])) or (first and cap.startswith(first + " ")):
                return img
        return None

    def extras(slug, p):
        return dict(k=p.get("k"), gen=p.get("gen"), line=line_name.get(p.get("line")), lineSlug=p.get("lineSlug"),
                    photo=avatar(slug, p),
                    records=[dict(key=k, **rec_title.get(k, dict(title=k, date=""))) for k in p.get("records", [])],
                    docs=[dict(img=d["img"], caption=d.get("caption", "")) for d in p.get("docs", [])])

    nodes = {}

    def node(i):
        return nodes[i]

    def link_parent(child, parent):
        if parent and parent not in node(child)["parents"]:
            node(child)["parents"].append(parent)
        if parent and child not in node(parent)["children"]:
            node(parent)["children"].append(child)

    def link_spouse(a, b):
        if b not in node(a)["spouses"]:
            node(a)["spouses"].append(b)
        if a not in node(b)["spouses"]:
            node(b)["spouses"].append(a)


    for slug, p in people.items():
        nodes[slug] = dict(id=slug, name=p["name"], years=p.get("years", ""), sex=p.get("sex", "M"), page=slug,
                           rel=p.get("rel", ""), status=p.get("status", ""), st=p.get("st", "unk"),
                           color=line_color.get(p.get("line")), facts=p.get("facts", []), text=p.get("note", ""),
                           parents=[], spouses=[], children=[], **extras(slug, p))
    for slug, p in people.items():
        link_parent(slug, p.get("father"))
        link_parent(slug, p.get("mother"))
        if p.get("father") and p.get("mother"):
            link_spouse(p["father"], p["mother"])

    ids = {}
    for s in side:
        if not s.get("id"):
            continue
        name, years = split_name(s["n"])
        i = "s-" + s["id"]
        ids[s["id"]] = i
        nodes[i] = dict(id=i, name=name, years=years, sex=s.get("sex") or guess_sex(name), page=None, rel="",
                        status="", st="side", color=None, facts=s.get("f", []), text=s.get("t", ""),
                        parents=[], spouses=[], children=[], k=None, gen=None, line=None, lineSlug=None, photo=s.get("foto"),
                        records=[dict(key=k, **rec_title[k]) for k in s.get("r", []) if k in rec_title],   # jen zápisy se stránkou
                        docs=[dict(img=d["img"], caption=d.get("caption", "")) for d in site.get("docs", [])
                              if d.get("img") == s.get("foto") or d.get("img") in s.get("fotky", [])])

    def target(s):
        return ids.get(s["koho"]) if s.get("koho") else by_k.get(s["k"])

    def entries(kind):
        return [(s, ids[s["id"]], target(s)) for s in side if s.get("id") and s.get("v", "sour") == kind and target(s)]

    for s, i, t in entries("manz"):                # spouses before children, so a child gets both parents
        link_spouse(i, t)
    for s, i, t in entries("dite"):
        link_parent(i, t)
        if s.get("rodice") in ("otec", "matka"):   # child of this parent only (other parent not in the data)
            continue
        if len(node(t)["spouses"]) == 1:
            link_parent(i, node(t)["spouses"][0])
        elif node(t)["spouses"]:                   # remarried: the other parent is unknown, do not guess
            print(f"POZOR: strom – {s['n']}: {node(t)['name']} má víc manželů, druhého rodiče nevím; kreslím jen "
                  f"jednoho (rodice='otec'/'matka' hlášku vypne)")
    # siblings last and repeatedly: the target (also a side relative, in any order in SIDE) may get its parents later
    siblings = entries("sour")
    for _ in range(len(siblings) + 1):
        before = sum(len(n["parents"]) for n in nodes.values())
        for s, i, t in siblings:
            for par in list(node(t)["parents"]):
                if s.get("rodice") != ("matka" if node(par)["sex"] == "M" else "otec"):
                    link_parent(i, par)
        if sum(len(n["parents"]) for n in nodes.values()) == before:
            break

    def birth(i):
        return year_of(node(i)["years"])

    for n in nodes.values():
        n["children"].sort(key=birth)
        n["parents"].sort(key=lambda i: node(i)["sex"] != "M")   # father first
    root = site["root"]
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(dict(root=root, nodes=nodes), f, ensure_ascii=False, indent=1)
    print(f"strom.json: {len(nodes)} osob ({sum(1 for n in nodes.values() if n['page'])} předků)")


if __name__ == "__main__":
    main()
