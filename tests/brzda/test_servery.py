"""Test povolených serverů a opatrných limitů brzdy pro nové síťové cesty (Sprint 5: obcházení archivů).

Z kořene repozitáře, složka nástrojů je argument:
  python3 -I tests/brzda/test_servery.py skills/rodokmen/tools
  (Windows: python -I -X utf8 …)
Nic nestahuje: soal_zoomify.py se pouští jen s adresami, které odmítne dřív, než sáhne na síť. Stav brzdy
je v dočasné složce. Jen standardní knihovna.
"""
import importlib.util, os, subprocess, sys, tempfile

TOOLS = os.path.abspath(sys.argv[1])
os.environ["SLUSNE_STAV"] = tempfile.mkdtemp(prefix="servery_slusne_")
PY = [sys.executable, "-I", "-X", "utf8"]
VYSLEDKY = []


def ok(nazev, podminka, detail=""):
    VYSLEDKY.append(bool(podminka))
    print(("OK   " if podminka else "CHYBA"), nazev, "" if podminka else detail)


def modul(jmeno):
    sys.path.insert(0, TOOLS)
    spec = importlib.util.spec_from_file_location(jmeno, os.path.join(TOOLS, jmeno + ".py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


slusne = modul("slusne")

# --- nové weby: dotaz nejvýš 1 za 10 s (limit neznámý nebo Crawl-delay 10) ---
for host in ("www.holocaust.cz", "collections-server.arolsen-archives.org", "collections.arolsen-archives.org",
             "wcm.slovakiana.sk", "content.slovakiana.sk", "digi.nacr.cz", "vademecum.nacr.cz", "jbc.bj.uj.edu.pl",
             "data.matricula-online.eu", "hosted-images.matricula-online.eu", "www.familysearch.org"):
    skupina, lim = slusne._skupina(host)
    ok(f"brzda: {host} dotaz aspoň 10 s", skupina and lim[0] >= 10, (skupina, lim))
for host in ("vademecum.nacr.cz", "jbc.bj.uj.edu.pl"):
    ok(f"brzda: {host} dlaždice aspoň 1 s", slusne._skupina(host)[1][1] >= 1, slusne._skupina(host))

# --- soal_zoomify.py: jen servery ze seznamu, nové po jedné dlaždici a s limitem v brzdě ---
src = open(os.path.join(TOOLS, "soal_zoomify.py"), encoding="utf-8").read()
ns = {}
exec(src[src.index("SERVERY = {"):src.index("HOSTS = ")], ns)
SERVERY = ns["SERVERY"]
ok("zoomify: VadeMeCum NA a Jagellonská knihovna povolené", {"vademecum.nacr.cz", "jbc.bj.uj.edu.pl"} <= set(SERVERY), SERVERY)
for host, vlakna in SERVERY.items():
    if host != "images.soalitomerice.cz":
        ok(f"zoomify: {host} po jedné dlaždici", vlakna == 1, vlakna)
        ok(f"zoomify: {host} má vlastní limit v brzdě", slusne._skupina(host)[0] in slusne.LIMITY, slusne._skupina(host))


def zoomify(adresa):
    r = subprocess.run(PY + [os.path.join(TOOLS, "soal_zoomify.py"), adresa, "0", os.path.join(tempfile.gettempdir(), "x.jpg")],
                       capture_output=True, text=True, encoding="utf-8", timeout=60)
    return r.returncode, r.stdout + r.stderr


k, out = zoomify("https://example.org/zoomify/obrazek.jpg")
ok("zoomify: cizí server odmítne (žádný režim „jakýkoli server“)", k != 0 and "povoleném serveru Zoomify" in out, out)
k, out = zoomify("http://vademecum.nacr.cz/mrimage/vademecum/zoomify//x.jpg")
ok("zoomify: jen https", k != 0 and "povoleném serveru Zoomify" in out, out)
k, out = zoomify("https://images.archives.cz/x/ImageProperties.xml")
ok("zoomify: ZA Opava dál odmítá", k != 0 and "ZA Opava" in out, out)
k, out = zoomify("https://vademecum.nacr.cz.example.org/x.jpg")
ok("zoomify: podvržená doména se jménem povoleného serveru neprojde", k != 0 and "povoleném serveru Zoomify" in out, out)

print(f"\n{sum(VYSLEDKY)} z {len(VYSLEDKY)} v pořádku")
sys.exit(0 if all(VYSLEDKY) else 1)
