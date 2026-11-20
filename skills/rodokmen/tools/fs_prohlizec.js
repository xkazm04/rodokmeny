// fs_prohlizec.js – pomocník pro FamilySearch v uživatelově přihlášeném prohlížeči (reference/portaly.md, FamilySearch).
//
// Celý soubor předej jako funkci do browser_evaluate (Playwright) / javascript_tool (Claude in Chrome) na stránce
// www.familysearch.org. Vytvoří window.fs a vrátí stav. Po každém načtení stránky (navigate) ho vlož znovu.
//   fs.stav()              -> tempo, počet snímků dnes, případná stopka
//   fs.zdroje(<id osoby>)  -> názvy zdrojů připojených u osoby ve stromu (GET /platform/tree/persons/<id>/sources)
//   fs.film(<DGS>)         -> název filmu (CZEC0001D_<fara>-<N>-<roky>-<druh> = převod na knihu archivu)
//   fs.snimek(<ARK 3:1:…>) -> JSON {w, h, adresa, data} pro `python3 -I tools/cache.py uloz pracovni/fs.json …`
//                             (Playwright: browser_evaluate s filename "pracovni/fs.json")
//   fs.stahni(<ARK 3:1:…>) -> uloží snímek do Stažených jako fs_3_1_<id>.jpg; pak `bash tools/fs_prevezmi.sh …`
// Pravidla (stejná jako brzda tools/slusne.py, ta na prohlížeč nedosáhne):
//   - vždy jen jeden požadavek na volání, žádné smyčky ani Promise.all; mezi dvěma požadavky aspoň 10 s (čeká samo),
//   - nejvýš 30 snímků za den, jen ty, které čteš,
//   - HTTP 429/503, „Pardon Our Interruption“ (HTML místo obrázku) nebo 403 u přihlášeného uživatele = stopka
//     (30 min, druhá za den do konce dne) pro všechna další volání; Claude ji hned zapíše i do brzdy:
//     python3 -I tools/slusne.py zastav familysearch.org "<důvod>" – a ten den už FamilySearch ne.
//   - Stahovat snímky smí Claude jen se souhlasem uživatele zapsaným jednou v CLAUDE.md projektu. Když automatické
//     schvalování (auto mode) volání odmítne, nic neobcházej – čti snímek v prohlížeči (postup přes stránky).
() => {
  const KLIC = 'rodokmen_fs', ROZESTUP = 10000, DENNE = 30, STOPKA = 30 * 60 * 1000;
  const dnes = () => new Date().toISOString().slice(0, 10);
  const nacti = () => { try { return JSON.parse(localStorage.getItem(KLIC)) || {}; } catch (e) { return {}; } };
  const uloz = s => { try { localStorage.setItem(KLIC, JSON.stringify(s)); } catch (e) { /* bez úložiště jen v rámci stránky */ } };
  const spi = ms => new Promise(r => setTimeout(r, ms));
  const token = () => (document.cookie.match(/(?:^|;\s*)fssessionid=([^;]+)/) || [])[1] || '';

  function zastav(duvod) {
    const s = nacti(), ted = Date.now();
    const odm = (s.odmitnuti || []).filter(t => t > ted - 24 * 3600 * 1000).concat([ted]);
    s.odmitnuti = odm;
    s.stop = odm.length > 1 ? new Date(new Date().setHours(23, 59, 59, 999)).getTime() : ted + STOPKA;
    s.duvod = duvod;
    uloz(s);
    return `STOP: ${duvod}. FamilySearch je zastavený do ${new Date(s.stop).toLocaleString('cs-CZ')}. ` +
      `Zapiš do brzdy: python3 -I tools/slusne.py zastav familysearch.org "${duvod}" a dnes už FamilySearch nezkoušej.`;
  }

  async function slot(snimek) {   // tempo a denní limit; vrací text chyby, nebo null
    let s = nacti();
    if (s.stop && s.stop > Date.now()) return `FamilySearch je zastavený do ${new Date(s.stop).toLocaleString('cs-CZ')} (${s.duvod}). Nezkoušej to dřív.`;
    if (s.den !== dnes()) { s.den = dnes(); s.snimky = 0; }
    if (snimek && (s.snimky || 0) >= DENNE) return `Dnes už ${DENNE} snímků – dost. Další snímky čti v prohlížeči nebo zítra.`;
    const cekej = (s.posledni || 0) + ROZESTUP - Date.now();
    s.posledni = Math.max(Date.now(), (s.posledni || 0) + ROZESTUP);
    if (snimek) s.snimky = (s.snimky || 0) + 1;
    uloz(s);
    if (cekej > 0) await spi(cekej);
    s = nacti();
    if (s.stop && s.stop > Date.now()) return `FamilySearch je zastavený (${s.duvod}).`;
    return null;
  }

  async function dotaz(adresa, hlavicky, snimek) {
    const chyba = await slot(snimek);
    if (chyba) return { chyba };
    const r = await fetch(adresa, { credentials: 'include', headers: hlavicky || {} });
    if (r.status === 429 || r.status === 503) return { chyba: zastav(`HTTP ${r.status}`) };
    if (r.status === 403) {
      if (!token()) return { chyba: 'HTTP 403 – uživatel není přihlášený (nebo přihlášení vypršelo). Ať se přihlásí; blokace to není.' };
      return { chyba: zastav('HTTP 403 u přihlášeného uživatele') };
    }
    if (!r.ok) return { chyba: `HTTP ${r.status} – ${adresa.slice(0, 80)}` };
    return { r };
  }

  const json = { Accept: 'application/x-fs-v1+json' };
  const jsonAuth = () => Object.assign({}, json, token() ? { Authorization: 'Bearer ' + token() } : {});
  const arkOk = ark => /^3:1:[A-Z0-9-]+$/i.test(ark || '');
  const distUrl = ark => `https://www.familysearch.org/service/records/storage/deepzoomcloud/dz/v1/${ark}/$dist`;

  async function obrazek(ark) {
    if (!arkOk(ark)) return { chyba: 'ARK snímku má tvar 3:1:XXXX-XXXX-XXX (z adresy /ark:/61903/3:1:…).' };
    const o = await dotaz(distUrl(ark), null, true);
    if (o.chyba) return o;
    if (!(o.r.headers.get('content-type') || '').startsWith('image/'))
      return { chyba: zastav('Pardon Our Interruption (HTML místo obrázku)') };
    return { blob: await o.r.blob() };
  }

  const fs = {
    stav() {
      const s = nacti();
      return JSON.stringify({ snimky_dnes: s.den === dnes() ? s.snimky || 0 : 0, limit: DENNE, rozestup_s: ROZESTUP / 1000,
        stop: s.stop && s.stop > Date.now() ? `${new Date(s.stop).toLocaleString('cs-CZ')} (${s.duvod})` : null,
        prihlasen: !!token() });
    },
    async zdroje(id) {
      if (!/^[A-Z0-9]{4}-[A-Z0-9]{3,4}$/i.test(id || '')) return 'Id osoby ve stromu má tvar XXXX-XXX.';
      const o = await dotaz(`https://www.familysearch.org/platform/tree/persons/${id}/sources`, jsonAuth());
      if (o.chyba) return o.chyba;
      const d = await o.r.json();
      return (d.sourceDescriptions || []).map(z => ((z.titles || [])[0] || {}).value || '(bez názvu)').join('\n') || 'Žádné zdroje.';
    },
    async film(dgs) {
      const c = String(dgs || '').replace(/\D/g, '');
      if (!c) return 'DGS je číslo filmu (např. 004536201).';
      const o = await dotaz(`https://www.familysearch.org/das/v2/dgs:${c.padStart(9, '0')}`, jsonAuth());
      if (o.chyba) return o.chyba;
      const d = await o.r.json();
      const t = ((d.sourceDescriptions || [])[0] || {}).titles || [];
      return (t[0] || {}).value || JSON.stringify(d).slice(0, 300);
    },
    async snimek(ark) {
      const o = await obrazek(ark);
      if (o.chyba) return o.chyba;
      const bm = await createImageBitmap(o.blob);
      const data = await new Promise(ok => { const f = new FileReader(); f.onload = () => ok(f.result); f.readAsDataURL(o.blob); });
      return JSON.stringify({ w: bm.width, h: bm.height, adresa: distUrl(ark), data });
    },
    async stahni(ark) {
      const o = await obrazek(ark);
      if (o.chyba) return o.chyba;
      const jmeno = 'fs_' + ark.replace(/:/g, '_') + '.jpg';
      const a = document.createElement('a');
      a.href = URL.createObjectURL(o.blob);
      a.download = jmeno;
      document.body.appendChild(a);
      a.click();
      a.remove();
      setTimeout(() => URL.revokeObjectURL(a.href), 60000);
      return `Stahuje se do Stažených jako ${jmeno}. Pak: bash tools/fs_prevezmi.sh ${jmeno} pracovni/${jmeno} --ark ${ark}`;
    },
  };
  window.fs = fs;
  return 'fs připraven: ' + fs.stav();
}
