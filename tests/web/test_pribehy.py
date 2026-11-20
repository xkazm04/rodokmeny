"""Test: další příběhy data/pribehy/<slug>.md v export_web.py (upstream #15, #30, #49) – pořadí, frontmatter,
koncept, generované soubory, smazaný příběh, kontrola odkazů; hlavní data/pribeh.md dál funguje.

Z kořene repozitáře:
  python3 -I tests/web/test_pribehy.py
  (Windows: python -I -X utf8 …)
Založí dočasný projekt s ukázkovou rodinou (novy_projekt.py --ukazka) a pustí jen export dat (bez npm).
"""
import json, os, shutil, subprocess, sys, tempfile

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PY = [sys.executable, "-I", "-X", "utf8"]
VYSLEDKY = []


def check(nazev, ok, detail=""):
    VYSLEDKY.append(bool(ok))
    print(("OK  " if ok else "CHYBA ") + nazev + ("" if ok else "\n    " + str(detail)[:1500].replace("\n", "\n    ")))


def zapis(cesta, text):
    os.makedirs(os.path.dirname(cesta), exist_ok=True)
    with open(cesta, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


tmp = tempfile.mkdtemp(prefix="pribehy_")
try:
    proj = os.path.join(tmp, "p")
    r = subprocess.run(PY + [os.path.join(REPO, "skills", "rodokmen", "tools", "novy_projekt.py"), proj, "--ukazka"],
                       capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0, r.stdout + r.stderr
    gen = os.path.join(proj, "web", "src", "generated")

    def export():
        r = subprocess.run(PY + [os.path.join(proj, "tools", "export_web.py")], capture_output=True, text=True,
                           encoding="utf-8", cwd=proj)
        site = json.load(open(os.path.join(proj, "web", "src", "data", "site.json"), encoding="utf-8"))
        return r.returncode, r.stdout + r.stderr, site

    rc, out, site = export()
    check("bez data/pribehy: hlavní příběh jako dřív", rc == 0 and site["config"]["maPribeh"]
          and site["config"]["hlavniPribeh"] and site["stories"] == [], out)

    zapis(os.path.join(proj, "data", "pribehy", "mlynari.md"),
          "---\ntitle: Mlynáři\nlead: 'Od mlýna k mlýnu'\nrod: 9\nkoncept: true\n---\n\n## Mlýn\n"
          "Viz [kováři](/pribehy/kovari/) a [nic](/pribehy/neni/).\n")
    zapis(os.path.join(proj, "data", "pribehy", "kovari.md"),
          '---\ntitle: "Kováři: pět generací"\nlead: Řemeslo\nrod: 8\nmenu: Kováři\n---\n\n## Kovárna\nText.\n')
    zapis(os.path.join(proj, "data", "pribehy", "Spatny Nazev.md"), "---\ntitle: x\n---\n")
    zapis(os.path.join(proj, "data", "pribehy", "bez-titulku.md"), "## jen text\n")
    rc, out, site = export()
    st = site["stories"]
    check("dva platné příběhy seřazené podle rodu", [s["slug"] for s in st] == ["kovari", "mlynari"], st)
    check("frontmatter: uvozovky, rod, menu, koncept",
          st[0]["title"] == "Kováři: pět generací" and st[0]["rod"] == 8 and st[0]["menu"] == "Kováři"
          and st[1]["lead"] == "Od mlýna k mlýnu" and st[1]["koncept"] is True and st[0]["koncept"] is False, st)
    check("špatný název souboru a chybějící title ohlášeny", "Spatny Nazev.md" in out and "bez-titulku.md" in out, out)
    check("generované příběhy", sorted(os.listdir(os.path.join(gen, "pribehy"))) == ["kovari.md", "mlynari.md"])
    check("nefunkční odkaz na příběh ohlášen, platný ne",
          "/pribehy/neni/ v pribehy/mlynari.md" in out and "/pribehy/kovari/" not in out, out)

    zapis(os.path.join(proj, "data", "web.json"), json.dumps(
        dict(json.load(open(os.path.join(proj, "data", "web.json"), encoding="utf-8-sig")), pribehy=["mlynari"]),
        ensure_ascii=False))
    rc, out, site = export()
    check("pořadí z web.json „pribehy“", [s["slug"] for s in site["stories"]] == ["mlynari", "kovari"], site["stories"])

    # frontmatter s komentáři za hodnotou jako v reference/pribehy.md (review #43); „#“ v uvozovkách zůstane
    zapis(os.path.join(proj, "data", "pribehy", "komentar.md"),
          '---\ntitle: "Mlýn č. 5 # u kostela"   # název\nlead: Jedna věta.\nrod: 9\n'
          "menu: Mlynáři          # nepovinné – vlastní položka v menu webu\n"
          "koncept: true          # nepovinné – na webu se štítkem „koncept“\n---\n\n## Mlýn\nText.\n")
    rc, out, site = export()
    k = next((s for s in site["stories"] if s["slug"] == "komentar"), {})
    check("frontmatter: komentář za hodnotou se nepočítá do hodnoty",
          k.get("menu") == "Mlynáři" and k.get("koncept") is True and k.get("title") == "Mlýn č. 5 # u kostela", k)
    os.remove(os.path.join(proj, "data", "pribehy", "komentar.md"))

    os.remove(os.path.join(proj, "data", "pribehy", "kovari.md"))
    os.remove(os.path.join(proj, "data", "pribeh.md"))
    rc, out, site = export()
    check("smazaný příběh zmizí z generovaných", sorted(os.listdir(os.path.join(gen, "pribehy"))) == ["mlynari.md"])
    check("bez hlavního příběhu: rozcestník", site["config"]["maPribeh"] and not site["config"]["hlavniPribeh"],
          site["config"])
    r = subprocess.run(PY + [os.path.join(proj, "tools", "kontrola.py")], capture_output=True, text=True,
                       encoding="utf-8", cwd=proj)
    check("kontrola nechce příběh, když jsou v data/pribehy", "je čas napsat příběh" not in r.stdout, r.stdout)
finally:
    shutil.rmtree(tmp, ignore_errors=True)

print(f"\n{sum(VYSLEDKY)}/{len(VYSLEDKY)} v pořádku")
sys.exit(0 if all(VYSLEDKY) else 1)
