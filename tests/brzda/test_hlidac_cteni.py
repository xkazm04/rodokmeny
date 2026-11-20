"""Test: hlídač čtení snímků pro pomocníky (tools/hlidac_cteni.py, upstream #90) a jeho zapnutí v novy_projekt.py.

Hlídač se spouští přesně tak, jak ho do .claude/settings.json zapíše `novy_projekt.py --hlidac` (na Windows bez shellu).
Z kořene repozitáře:
  python3 -I tests/brzda/test_hlidac_cteni.py skills/rodokmen
  (Windows: python -I -X utf8 …)
"""
import json, os, shutil, subprocess, sys, tempfile, time

SKILL = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else "skills/rodokmen")
sys.path.insert(0, os.path.join(SKILL, "tools"))
import novy_projekt  # noqa: E402

VYSLEDKY = []


def check(nazev, ok, detail=""):
    VYSLEDKY.append(bool(ok))
    print(f"[{'OK ' if ok else 'CHYBA'}] {nazev}{'' if ok else '  ' + str(detail)[:800]}", flush=True)


tmp = tempfile.mkdtemp(prefix="hlidac_cteni_")
try:
    projekt = os.path.join(tmp, "projekt")
    os.makedirs(os.path.join(projekt, "tools"))
    shutil.copy2(os.path.join(SKILL, "tools", "hlidac_cteni.py"), os.path.join(projekt, "tools"))
    env = dict(os.environ, CLAUDE_PROJECT_DIR=projekt, RODOKMEN_CTENI_SLOZKA=os.path.join(tmp, "stav"))
    hook = novy_projekt.hook_cteni()
    prikaz = [hook["command"]] + hook["args"] if "args" in hook else hook["command"]

    def cti(soubor, agent="pom1", session="s1", **navic):
        vstup = dict(tool_name="Read", session_id=session, tool_input={"file_path": soubor}, **navic)
        if agent:
            vstup["agent_id"] = agent
        r = subprocess.run(prikaz, input=json.dumps(vstup), capture_output=True, text=True, encoding="utf-8",
                           env=env, shell=isinstance(prikaz, str), timeout=30)
        return r.returncode, r.stderr

    snimek = os.path.join(tmp, "pracovni", "kniha_0057.jpg")
    check("hlavní konverzace se nehlídá (10× týž snímek)", all(cti(snimek, agent=None)[0] == 0 for _ in range(10)))
    rc1, rc2, (rc3, err3) = cti(snimek)[0], cti(snimek)[0], cti(snimek)
    check("pomocník: 1. a 2. čtení snímku projde", rc1 == 0 and rc2 == 0, (rc1, rc2))
    check("pomocník: 3. čtení téhož snímku zamítne s vysvětlením", rc3 == 2 and "ZASTAVENO" in err3 and "media removed" in err3, (rc3, err3))
    check("jiný pomocník má vlastní počítadlo", cti(snimek, agent="pom2")[0] == 0)
    check("textový soubor se nepočítá", all(cti(os.path.join(tmp, "data", "osoby.py"))[0] == 0 for _ in range(5)))

    vysl = [cti(os.path.join(tmp, "pracovni", f"s_{i:03d}.png"), agent="pom3")[0] for i in range(31)]
    check("30 různých snímků projde", vysl[:30] == [0] * 30, vysl)
    rc, err = cti(os.path.join(tmp, "pracovni", "s_100.jpg"), agent="pom3")
    check("31. snímek zamítne", vysl[30] == 2 and rc == 2 and "nepřečtených" in err, (vysl[30], rc, err))
    check("jiná konverzace má vlastní počítadlo", cti(snimek, session="s2")[0] == 0)

    cizi_sl = os.path.join(tmp, "data_projektu")   # RODOKMEN_CTENI_SLOZKA omylem na složku s daty projektu
    os.makedirs(cizi_sl)
    stare = time.time() - 5 * 86400
    for n in ("osoby.py", "denik.log", "s0_x.cteni.log"):
        open(os.path.join(cizi_sl, n), "w").close()
        os.utime(os.path.join(cizi_sl, n), (stare, stare))
    env["RODOKMEN_CTENI_SLOZKA"] = cizi_sl
    cti(snimek, agent="pom9")
    env["RODOKMEN_CTENI_SLOZKA"] = os.path.join(tmp, "stav")
    zbylo = sorted(os.listdir(cizi_sl))
    check("úklid maže jen vlastní staré stavy, cizí soubory ve složce nechá",
          "osoby.py" in zbylo and "denik.log" in zbylo and "s0_x.cteni.log" not in zbylo, zbylo)

    r = subprocess.run(prikaz, input="není json", capture_output=True, text=True, encoding="utf-8", env=env,
                       shell=isinstance(prikaz, str), timeout=30)
    check("rozbitý vstup čtení povolí", r.returncode == 0, r.stderr)
    env["RODOKMEN_CTENI_SLOZKA"] = os.path.join(tmp, "soubor_misto_slozky")
    open(env["RODOKMEN_CTENI_SLOZKA"], "w").close()
    check("chyba hlídače (nejde zapsat stav) čtení povolí", cti(snimek)[0] == 0)
    env2 = dict(env, CLAUDE_PROJECT_DIR=os.path.join(tmp, "bez_nastroje"))
    r = subprocess.run(prikaz, input=json.dumps(dict(tool_name="Read", agent_id="x", tool_input={"file_path": snimek})),
                       capture_output=True, text=True, encoding="utf-8", env=env2, shell=isinstance(prikaz, str), timeout=30)
    check("projekt bez tools/hlidac_cteni.py čtení nezastaví", r.returncode == 0, r.stderr)

    # zapnutí a vypnutí v .claude/settings.json
    def hooky(p):
        d = json.load(open(os.path.join(p, ".claude", "settings.json"), encoding="utf-8"))
        return {h["matcher"]: json.dumps(h) for h in d.get("hooks", {}).get("PreToolUse", [])}

    p = os.path.join(tmp, "nastaveni")
    os.makedirs(os.path.join(p, ".claude"))
    novy_projekt.nastaveni(p, None)
    check("bez --hlidac se nic nezapne", hooky(p) == {}, hooky(p))
    novy_projekt.nastaveni(p, True)
    h = hooky(p)
    check("--hlidac zapne hlídač sítě i čtení", "hlidac_site.py" in h.get(novy_projekt.MATCHER, "")
          and "hlidac_cteni.py" in h.get("Read", ""), h)
    novy_projekt.nastaveni(p, True)
    check("opakované --hlidac nepřidá hook dvakrát", len(hooky(p)) == 2 and
          sum("hlidac_cteni.py" in v for v in hooky(p).values()) == 1, hooky(p))
    novy_projekt.nastaveni(p, False)
    check("--bez-hlidace vypne oba", hooky(p) == {}, hooky(p))

    sp = os.path.join(p, ".claude", "settings.json")   # starší projekt: jen hlídač sítě a cizí hook
    cizi = {"matcher": "Read", "hooks": [{"type": "command", "command": "echo cizi"}]}
    json.dump({"hooks": {"PreToolUse": [{"matcher": novy_projekt.MATCHER, "hooks": [novy_projekt.hook_hlidace()]}, cizi]}},
              open(sp, "w", encoding="utf-8"))
    novy_projekt.nastaveni(p, None)
    pre = json.load(open(sp, encoding="utf-8"))["hooks"]["PreToolUse"]
    check("aktualizace projektu se zapnutým hlídačem sítě doplní hlídač čtení a cizí hook nechá",
          any("hlidac_cteni.py" in json.dumps(x) for x in pre) and cizi in pre and len(pre) == 3, pre)
finally:
    shutil.rmtree(tmp, ignore_errors=True)

print(f"\n{sum(VYSLEDKY)} z {len(VYSLEDKY)} správně")
sys.exit(0 if all(VYSLEDKY) else 1)
