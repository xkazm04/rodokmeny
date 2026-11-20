#!/usr/bin/env python3
"""Snímek z Matriculy (data.matricula-online.eu) bez prohlížeče – přímá adresa obrázku ze seznamu „files“ na stránce knihy.

Stránka knihy má v HTML seznam snímků („files“: /image/<base64>/, kde base64 je přímá adresa obrázku na
hosted-images.matricula-online.eu) a jejich popisky („labels“). Nástroj načte stránku knihy jednou (bez ?pg=,
tu robots.txt robotům zakazuje) a stáhne jen zadané snímky, po jednom přes brzdu (1 dotaz za 10 s, i snímky).

Použití (z kořene projektu):
  matricula_snimek.py seznam <adresa knihy>              -> počet snímků a popisky (číslo snímku = ?pg=N)
  matricula_snimek.py <adresa knihy> <N>[,<M>…] <vystup.jpg>
      -> snímek N (víc čísel: vystup_N.jpg…, nejvýš 10 na jedno spuštění) a trvalý odkaz <adresa knihy>?pg=N
Adresa knihy: https://data.matricula-online.eu/<jazyk>/<země>/<diecéze>/<farnost>/<kniha>/ (i s ?pg=N z prohlížeče).
Stahuj jen snímky, které čteš, žádné celé knihy. Snímky jsou pod CC BY-NC-ND 2.0: pro vlastní bádání; na web rodiny
nanejvýš výřez zápisu s uvedením zdroje (reference/soukromi.md).
"""
import base64, json, os, re, sys, urllib.error, urllib.parse, urllib.request
if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):   # nápověda místo pádu
    sys.exit(__doc__.strip())
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__))); import slusne  # noqa: E402 – brzda proti zablokování archivem (společný limit dotazů, tools/slusne.py)
for _s in (sys.stdout, sys.stderr):   # UTF-8 výstup i na Windows bez -X utf8
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")

WEB, OBRAZKY = "data.matricula-online.eu", "hosted-images.matricula-online.eu"
UA = {"User-Agent": "Mozilla/5.0 (rodokmen)"}
MAX = 10


def kniha(adresa):
    """Adresa stránky knihy bez ?pg= a bez #…; jiný web -> chyba."""
    u = urllib.parse.urlsplit(adresa.strip())
    if u.scheme != "https" or u.hostname != WEB or u.path.count("/") < 5:
        sys.exit(f"Zadej adresu knihy na https://{WEB}/<jazyk>/<země>/<diecéze>/<farnost>/<kniha>/, ne {adresa[:80]}")
    return f"https://{WEB}{u.path if u.path.endswith('/') else u.path + '/'}"


def seznam(html):
    """(adresy obrázků, popisky) ze stránky knihy."""
    def pole(jmeno):
        m = re.search(r'"%s"\s*:\s*(\[[^\]]*\])' % jmeno, html)
        try:
            return json.loads(m.group(1)) if m else []
        except ValueError:
            return []
    adresy = []
    for f in pole("files"):
        m = re.fullmatch(r"/image/([A-Za-z0-9_\-+/=]+?)/?", f)
        if not m:
            adresy.append(None)
            continue
        b = m.group(1)
        try:
            u = base64.urlsafe_b64decode(b + "=" * (-len(b) % 4)).decode("ascii")
        except (ValueError, UnicodeDecodeError):
            u = None
        adresy.append(u if u and urllib.parse.urlsplit(u).hostname == OBRAZKY else None)
    return adresy, pole("labels")


def get(url):
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
            return r.read()
    except urllib.error.HTTPError as e:   # 429/503 (a 403 u stránky) zastaví už brzda
        sys.exit(f"Matricula odpověděla HTTP {e.code} ({url[:100]}) – nic neopakuj, zkus to později nebo v prohlížeči.")
    except OSError as e:
        sys.exit(f"Matricula neodpovídá ({type(e).__name__}) – zkus to později.")


def main(a):
    if a[0] == "seznam" and len(a) == 2:
        k = kniha(a[1])
        adresy, popisky = seznam(get(k).decode("utf-8", "replace"))
        if not adresy:
            sys.exit("Na stránce není seznam snímků („files“) – změnil se web? Použij prohlížeč (reference/portaly.md).")
        print(f"# {k}: {len(adresy)} snímků")
        for i, p in enumerate(popisky or [""] * len(adresy), 1):
            print(f"{i}\t{p}")
        return
    if len(a) != 3 or not re.fullmatch(r"\d+(,\d+)*", a[1]):
        sys.exit(__doc__.strip())
    k, cisla, out = kniha(a[0]), [int(x) for x in a[1].split(",")], a[2]
    if len(cisla) > MAX:
        sys.exit(f"Nejvýš {MAX} snímků na jedno spuštění – stahuj jen ty, které čteš.")
    adresy, popisky = seznam(get(k).decode("utf-8", "replace"))
    if not adresy:
        sys.exit("Na stránce není seznam snímků („files“) – změnil se web? Použij prohlížeč (reference/portaly.md).")
    base, ext = os.path.splitext(out)
    for n in cisla:
        if not 1 <= n <= len(adresy) or not adresy[n - 1]:
            sys.exit(f"Snímek {n} v knize není (snímků je {len(adresy)}).")
        data = get(adresy[n - 1])
        if not data.startswith(b"\xff\xd8"):
            sys.exit(f"Snímek {n}: Matricula nevrátila obrázek – nic neukládám, zkus to v prohlížeči.")
        cil = out if len(cisla) == 1 else f"{base}_{n}{ext or '.jpg'}"
        os.makedirs(os.path.dirname(os.path.abspath(cil)), exist_ok=True)
        with open(cil, "wb") as f:
            f.write(data)
        popis = popisky[n - 1] if n <= len(popisky) else ""
        print(f"{cil}\t{popis}\t{k}?pg={n}")


if __name__ == "__main__":
    main(sys.argv[1:])
