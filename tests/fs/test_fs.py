"""Testy pomocníků pro FamilySearch a Matriculu bez prohlížeče (tools/fs_prohlizec.js, fs_prevezmi.sh, matricula_snimek.py).

Z kořene repozitáře, složka nástrojů je argument:
  python3 -I tests/fs/test_fs.py skills/rodokmen/tools
  (Windows: python -I -X utf8 …)
Nic nestahuje: fetch v fs_prohlizec.js je podvržený (Node), stránka Matriculy je vepsaná v testu. fs_prohlizec.js
se zkouší jen tam, kde je Node (web ho potřebuje tak jako tak), fs_prevezmi.sh jen s bashem.
"""
import base64, importlib.util, json, os, shutil, subprocess, sys, tempfile

TOOLS = os.path.abspath(sys.argv[1])
os.environ["SLUSNE_STAV"] = tempfile.mkdtemp(prefix="fs_slusne_")
VYSLEDKY = []


def ok(nazev, podminka, detail=""):
    VYSLEDKY.append(bool(podminka))
    print(("OK   " if podminka else "CHYBA"), nazev, "" if podminka else detail)


# --- fs_prohlizec.js: tempo, stopka po 429 a „Pardon Our Interruption“, denní limit ---------------------------------
NODE = shutil.which("node")
UKOL = r"""
const src = require('fs').readFileSync(process.argv[1], 'utf8');
const store = {};
global.localStorage = { getItem: k => store[k] ?? null, setItem: (k, v) => { store[k] = String(v); } };
global.document = { cookie: 'fssessionid=abc' };
global.window = {};
global.createImageBitmap = async () => ({ width: 5, height: 7 });
global.FileReader = class { readAsDataURL() { this.result = 'data:image/jpeg;base64,AA=='; this.onload(); } };
const odpovedi = JSON.parse(process.argv[2]);
const volani = [];
global.fetch = async (u) => { volani.push(u); const o = odpovedi.shift();
  return { status: o.s, ok: o.s < 300, headers: { get: () => o.typ || '' }, blob: async () => ({}), json: async () => o.json || {} }; };
const realNow = Date.now; let posun = 0; Date.now = () => realNow() + posun;
global.setTimeout = (f, ms) => { posun += ms; f(); };   // čekání brzdy jen „naoko“, změří se posun
(async () => {
  eval('(' + src + ')')();
  const out = {};
  for (const [k, fn] of JSON.parse(process.argv[3])) out[k] = await eval(fn);
  out.volani = volani; out.cekano_ms = posun; out.stav = JSON.parse(window.fs.stav());
  console.log(JSON.stringify(out));
})();
"""


def js(odpovedi, kroky):
    r = subprocess.run([NODE, "-e", UKOL, os.path.join(TOOLS, "fs_prohlizec.js"), json.dumps(odpovedi), json.dumps(kroky)],
                       capture_output=True, text=True, encoding="utf-8", timeout=60)
    try:
        return json.loads(r.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        return {"chyba": r.stdout + r.stderr}


if NODE:
    o = js([{"s": 200, "typ": "image/jpeg"}, {"s": 200, "typ": "image/jpeg"}],
           [["a", "window.fs.snimek('3:1:AAAA-BBBB-CCC')"], ["b", "window.fs.snimek('3:1:AAAA-BBBB-CCD')"]])
    ok("fs.snimek: JSON s rozměry a adresou $dist", '"w":5' in o.get("a", "") and "$dist" in o.get("a", ""), o)
    ok("fs: dva požadavky aspoň 10 s od sebe", len(o.get("volani", [])) == 2 and o.get("cekano_ms", 0) >= 9900, o)
    o = js([{"s": 429}], [["a", "window.fs.film('4536201')"], ["b", "window.fs.snimek('3:1:AAAA-BBBB-CCC')"]])
    ok("fs: HTTP 429 = stopka a rada zapsat ji do brzdy", "STOP" in o.get("a", "") and "slusne.py zastav familysearch.org" in o.get("a", ""), o)
    ok("fs: po stopce další volání nic nestáhne", len(o.get("volani", [])) == 1 and "zastavený" in o.get("b", ""), o)
    o = js([{"s": 200, "typ": "text/html"}], [["a", "window.fs.snimek('3:1:AAAA-BBBB-CCC')"]])
    ok("fs: HTML místo obrázku (Pardon Our Interruption) = stopka", "Pardon" in o.get("a", "") and o["stav"]["stop"], o)
    o = js([], [["a", "window.fs.snimek('../../x')"], ["b", "window.fs.zdroje('x; y')"]])
    ok("fs: špatný ARK ani id osoby nic nepošlou", not o.get("volani") and "3:1:" in o.get("a", "") and "XXXX" in o.get("b", ""), o)
    o = js([{"s": 200, "typ": "image/jpeg"}] * 31, [[str(i), "window.fs.snimek('3:1:AAAA-BBBB-CCC')"] for i in range(31)])
    ok("fs: nejvýš 30 snímků za den", len(o.get("volani", [])) == 30 and "Dnes už 30" in o.get("30", ""), len(o.get("volani", [])))
else:
    print("(Node není – fs_prohlizec.js přeskočen)")

# --- fs_prevezmi.sh: jen soubor s přesným názvem, jen JPEG, uloží do mezipaměti ----------------------------------------
BASH = shutil.which("bash")
if BASH:
    t = tempfile.mkdtemp(prefix="fs_prevezmi_")
    env = dict(os.environ, STAZENE=t, RODOKMEN_SNIMKY=os.path.join(t, "mezipamet"))
    with open(os.path.join(t, "fs_3_1_ABCD-EFGH.jpg"), "wb") as f:
        f.write(b"\xff\xd8\xff\xe0" + b"x" * 100 + b"\xff\xd9")
    with open(os.path.join(t, "pardon.jpg"), "wb") as f:
        f.write(b"<html>Pardon Our Interruption</html>")
    sh = os.path.join(TOOLS, "fs_prevezmi.sh").replace("\\", "/")

    def prevezmi(*a):
        r = subprocess.run([BASH, sh, *a], capture_output=True, text=True, encoding="utf-8", env=env, timeout=120)
        return r.returncode, r.stdout + r.stderr
    cil = os.path.join(t, "pracovni", "x.jpg").replace("\\", "/")
    k, out = prevezmi("fs_3_1_ABCD-EFGH.jpg", cil, "--ark", "3:1:ABCD-EFGH")
    ok("fs_prevezmi: přesune snímek a uloží ho do mezipaměti", k == 0 and os.path.exists(cil)
       and os.path.exists(os.path.join(t, "mezipamet", "familysearch", "3_1_ABCD-EFGH.jpg")), out)
    k, out = prevezmi("pardon.jpg", cil)
    ok("fs_prevezmi: HTML místo obrázku nepřevezme", k == 1 and "Pardon" in out and os.path.exists(os.path.join(t, "pardon.jpg")), out)
    k, out = prevezmi("../tajne.jpg", cil)
    ok("fs_prevezmi: jen název souboru, ne cesta", k == 2, out)
else:
    print("(bash není – fs_prevezmi.sh přeskočen)")

# --- matricula_snimek.py: seznam „files“ a kontrola adres -------------------------------------------------------------
sys.argv = ["matricula_snimek.py", "--x"]
sys.path.insert(0, TOOLS)
spec = importlib.util.spec_from_file_location("matricula_snimek", os.path.join(TOOLS, "matricula_snimek.py"))
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def b64(u):
    return base64.urlsafe_b64encode(u.encode()).decode().rstrip("=")


HTML = ('<script>var x = {"labels": ["01-Einband_0001", "02-Taufe_0001", "03-cizi"], "files": ["/image/%s/", "/image/%s/", "/image/%s/"]};</script>'
        % (b64("http://hosted-images.matricula-online.eu/images/a/1.jpg"), b64("http://hosted-images.matricula-online.eu/images/a/2.jpg"),
           b64("http://zlo.example/3.jpg")))
adresy, popisky = m.seznam(HTML)
ok("matricula: adresy obrázků z base64 v „files“", adresy[:2] == ["http://hosted-images.matricula-online.eu/images/a/1.jpg",
                                                                  "http://hosted-images.matricula-online.eu/images/a/2.jpg"], adresy)
ok("matricula: cizí server ze seznamu se nepoužije", adresy[2] is None, adresy)
ok("matricula: popisky snímků", popisky[1] == "02-Taufe_0001", popisky)
ok("matricula: adresa knihy bez ?pg=", m.kniha("https://data.matricula-online.eu/de/oesterreich/wien/01-st-stephan/01-001/?pg=5")
   == "https://data.matricula-online.eu/de/oesterreich/wien/01-st-stephan/01-001/")
for zla in ("http://data.matricula-online.eu/de/a/b/c/d/", "https://evil.example/de/a/b/c/d/", "https://data.matricula-online.eu/de/"):
    try:
        m.kniha(zla)
        ok(f"matricula: odmítne {zla}", False)
    except SystemExit:
        ok(f"matricula: odmítne {zla}", True)

print(f"\n{sum(VYSLEDKY)} z {len(VYSLEDKY)} v pořádku")
sys.exit(0 if all(VYSLEDKY) else 1)
