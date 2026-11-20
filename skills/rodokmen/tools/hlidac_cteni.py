#!/usr/bin/env python3
"""Hlídač čtení snímků pro pomocníky (volitelný hook PreToolUse na nástroj Read v .claude/settings.json projektu).

Zapíná se spolu s hlídačem sítě příkazem `novy_projekt.py <projekt> --hlidac`, vypíná `--bez-hlidace`.
Proč: pomocník se 48 snímky a zadáním „při chybě zkus ještě jednou“ udělal 1 500 čtení (každý snímek ~31×) a spálil
5hodinový limit i hlavní konverzaci. Do jednoho požadavku se vejde jen asi 40 snímků; pak Claude Code nejstarší
vyhodí („[media removed: request limit]“), zneplatní se cache a celý kontext se zapisuje znovu (upstream #90).

Co dělá: když Read volá pomocník (ve vstupu hooku je `agent_id`, v hlavní konverzaci chybí) a čte obrázek, zamítne
(kód 2 + vysvětlení pomocníkovi)
  - třetí čtení téhož snímku (RODOKMEN_CTENI_OPAKOVANI, výchozí 2),
  - čtení nad 30 snímků celkem (RODOKMEN_CTENI_MAX; zadání má nejvýš 15 snímků, každý nejvýš dvakrát).
Hlavní konverzaci nehlídá nikdy. Při jakékoli vlastní chybě čtení povolí – rozbitý hlídač nesmí zastavit práci.
Stav: ~/.cache/rodokmen_cteni/<session>_<pomocník>.cteni.log (řádek na čtení); své stavy (*.cteni.log) starší 3 dnů
maže, jiné soubory ve složce nechá.
"""
import json, os, sys, time

OBRAZKY = (".jpg", ".jpeg", ".png", ".webp", ".gif")
PRIPONA = ".cteni.log"   # stav hlídače; úklid maže jen tyto soubory (složka z RODOKMEN_CTENI_SLOZKA může být cizí)


def slozka():
    return os.environ.get("RODOKMEN_CTENI_SLOZKA") or os.path.join(os.path.expanduser("~"), ".cache", "rodokmen_cteni")


def main():
    try:
        max_snimku = int(os.environ.get("RODOKMEN_CTENI_MAX", "30"))
        max_opakovani = int(os.environ.get("RODOKMEN_CTENI_OPAKOVANI", "2"))
        vstup = json.load(sys.stdin)
        if vstup.get("tool_name") != "Read" or not vstup.get("agent_id"):
            return 0   # jen pomocníci, jen Read
        soubor = (vstup.get("tool_input") or {}).get("file_path") or ""
        if not soubor.lower().endswith(OBRAZKY):
            return 0
        soubor = os.path.normcase(os.path.realpath(soubor))
        sl = slozka()
        os.makedirs(sl, exist_ok=True)
        zaklad = "".join(c if c.isalnum() or c in "-_" else "_" for c in f"{vstup.get('session_id', 's')}_{vstup['agent_id']}")
        cesta = os.path.join(sl, zaklad + PRIPONA)
        cteni = []
        if os.path.exists(cesta):
            with open(cesta, encoding="utf-8") as f:
                cteni = [r.rstrip("\n") for r in f]
        for stary in os.listdir(sl):   # úklid starých stavů – jen vlastních
            p = os.path.join(sl, stary)
            if (stary.endswith(PRIPONA) and os.path.isfile(p) and not os.path.islink(p)
                    and time.time() - os.path.getmtime(p) > 3 * 86400):
                os.remove(p)
    except Exception:
        return 0   # chyba hlídače nesmí zastavit práci
    jmeno = os.path.basename(soubor)
    if cteni.count(soubor) >= max_opakovani:
        print(f"ZASTAVENO hlídačem čtení: snímek {jmeno} jsi četl už {max_opakovani}×. Nečti ho znovu – hláška "
              "„media removed“ znamená, že ho z požadavku vytlačil limit, a další čtení to jen zhorší a stojí tisíce "
              "tokenů. Zapiš ho mezi nepřečtené, dokonči ostatní a vrať, co máš.", file=sys.stderr)
        return 2
    if len(cteni) >= max_snimku:
        print(f"ZASTAVENO hlídačem čtení: máš za sebou {max_snimku} čtení snímků, víc se do jednoho požadavku "
              "bezpečně nevejde. Nečti další. Skonči, vrať přepis toho, co máš, a seznam nepřečtených snímků – "
              "hlavní konverzace je dá dalšímu pomocníkovi.", file=sys.stderr)
        return 2
    try:
        with open(cesta, "a", encoding="utf-8") as f:
            f.write(soubor + "\n")
    except OSError:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
