// Rozložení pohledu „Kolem osoby“ na stránce Strom (/strom/): vybraná osoba uprostřed, předci nad ní (otcova strana
// vlevo, matčina vpravo), sourozenci vlevo, partneři vpravo, potomci pod ní. Každý podstrom má vlastní šířku.
// Čistá funkce bez prohlížeče (počítá se v prohlížeči při každém výběru; test ji spouští v Node).
// nodes: id -> { parents, spouses, children }; W, H: rozměr kartičky v px.
// Vrátí { width, height, pos: id -> {x, y}, fams: [{ id, parents, children, x, y }] } jako předpočítané pohledy.

export const siblingsOf = (nodes, n) =>
  [...new Set(n.parents.flatMap((p) => nodes[p]?.children ?? []))].filter((c) => c !== n.id);

export function focusLayout(nodes, fid, up, down, W, H) {
  const GAP = 26, CGAP = 18, ROW = H + 84;
  const pos = {};
  const fams = [];
  const at = (id, x, row) => { pos[id] = { x, y: row * ROW }; };
  // dva rodiče na stejném řádku mají spojnici páru a z jejího středu vede čára k dětem; jinak čára od každého rodiče
  const junction = (ps) => (ps.length === 2 && pos[ps[0]].y === pos[ps[1]].y
    ? { x: (pos[ps[0]].x + pos[ps[1]].x) / 2, y: pos[ps[0]].y } : { x: null, y: null });
  // předci: vrátí x osoby `id` a pravý okraj podstromu jejích předků. Předek, který už kartičku má (týž předek
  // přes dvě větve), se znovu nekreslí, ale spojnice k dítěti zůstane.
  function upTree(id, depth, left, row) {
    const ps = depth > 0 ? nodes[id].parents.filter((p) => nodes[p]) : [];
    if (!ps.length) return { x: left + W / 2, right: left + W + GAP };
    let r = left;
    const xs = [];
    for (const p of ps) {
      if (pos[p]) continue;
      const t = upTree(p, depth - 1, r, row - 1);
      at(p, t.x, row - 1);
      r = t.right;
      xs.push(t.x);
    }
    fams.push({ id: `fu-${id}`, parents: ps, children: [id], ...junction(ps) });
    const x = xs.length === 2 ? (xs[0] + xs[1]) / 2 : xs.length ? xs[0] : left + W / 2;
    return { x, right: Math.max(r, left + W + GAP) };
  }
  // potomci: osoba s partnery je jedna jednotka, děti pod ní
  const partners = (id) => nodes[id].spouses.filter((s) => nodes[s]);
  const kidsOf = (id, depth) => (depth > 0 ? nodes[id].children.filter((c) => nodes[c]) : []);
  const unitW = (id) => (1 + partners(id).length) * W + partners(id).length * CGAP + GAP;
  const widthMemo = new Map();
  function measure(id, depth) {
    const k = `${id}|${depth}`;
    if (!widthMemo.has(k)) widthMemo.set(k, Math.max(unitW(id), kidsOf(id, depth).reduce((s, c) => s + measure(c, depth - 1), 0)));
    return widthMemo.get(k);
  }
  function downTree(id, depth, left, row) {
    const w = measure(id, depth), uw = unitW(id), sp = partners(id);
    let x = left + (w - uw) / 2 + W / 2;
    at(id, x, row);
    const sx = sp.map((s) => { x += W + CGAP; if (!pos[s]) at(s, x, row); return pos[s].x; });
    const kids = kidsOf(id, depth);
    let cl = left + (w - kids.reduce((s, c) => s + measure(c, depth - 1), 0)) / 2;
    for (const c of kids) { downTree(c, depth - 1, cl, row + 1); cl += measure(c, depth - 1); }
    // jedna rodina na partnera (děti, které ho mají za druhého rodiče), ostatní děti jen s tímto rodičem
    const rest = new Set(kids);
    sp.forEach((s, i) => {
      const ch = kids.filter((c) => nodes[c].parents.includes(s));
      ch.forEach((c) => rest.delete(c));
      fams.push({ id: `fd-${id}-${s}`, parents: [id, s], children: ch, x: (pos[id].x + sx[i]) / 2, y: row * ROW });
    });
    if (rest.size) fams.push({ id: `fd-${id}`, parents: [id], children: [...rest], x: null, y: null });
  }
  const top = upTree(fid, up, 0, 0);
  // potomci začínají tak, aby fid padl přesně pod předky spočítané výše
  downTree(fid, down, top.x - ((measure(fid, down) - unitW(fid)) / 2 + W / 2), 0);
  // sourozenci na stejném řádku vlevo; patří do rodiny podle rodičů, které s vybranou osobou opravdu sdílejí
  // (nevlastní sourozenec jen pod společným rodičem, ne pod oběma)
  const sibs = siblingsOf(nodes, nodes[fid]).filter((s) => !pos[s]);
  const leftmost = Math.min(...Object.values(pos).filter((p) => p.y === 0).map((p) => p.x));
  sibs.forEach((s, i) => at(s, leftmost - (i + 1) * (W + GAP), 0));
  const pf = fams.find((f) => f.id === `fu-${fid}`);
  if (pf) {
    for (const s of sibs) {
      const shared = pf.parents.filter((p) => nodes[s].parents.includes(p));
      if (!shared.length) continue;
      if (shared.length === pf.parents.length) { pf.children.push(s); continue; }
      const id = `fu-${fid}-${shared.join('-')}`;
      const f = fams.find((x) => x.id === id);
      if (f) f.children.push(s);
      else fams.push({ id, parents: shared, children: [s], x: null, y: null });
    }
  }
  // posun na kreslení od 0 jako u předpočítaných pohledů (fitAll s tím počítá)
  const xs = Object.values(pos).map((p) => p.x), ys = Object.values(pos).map((p) => p.y);
  const ox = Math.min(...xs) - W / 2 - 40, oy = Math.min(...ys) - H / 2 - 40;
  for (const p of Object.values(pos)) { p.x -= ox; p.y -= oy; }
  for (const f of fams) if (f.x != null && f.y != null) { f.x -= ox; f.y -= oy; }
  return { width: Math.max(...xs) - ox + W / 2 + 40, height: Math.max(...ys) - oy + H / 2 + 40, pos, fams };
}
