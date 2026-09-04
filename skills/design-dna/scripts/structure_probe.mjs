#!/usr/bin/env node
/**
 * structure_probe.mjs
 *
 * Read the STRUCTURE of a first screen: what occupies it, where the ink sits,
 * what is at the edges, and the proportions of the type. Shared by
 * observe_reference.mjs (which records it for each reference) and
 * compare_structure.mjs (which reads the finished build and diffs it), so a
 * build and its references are always read by identical code.
 *
 * This exists because every earlier gate checked that the producer LOOKED at
 * a reference. None checked whether the thing it built RESEMBLED one. Given a
 * measuring pass that could only read font sizes and padding, the producer
 * came back with font sizes and padding, invented the layout, and shipped its
 * own design with one borrowed button on it. Nine times.
 *
 * Nothing here needs an image decoder. Occupancy is sampled with
 * elementFromPoint on a grid, and each sample is classified as media, text or
 * empty, which is enough to tell "a full-bleed photograph with the wordmark in
 * the corners" from "a headline top-left and an empty right half".
 */

export const GRID_X = 24;
export const GRID_Y = 16;
export const EDGE_PX = 80;

/** Page-side. Returns the structure signature of the current first screen. */
export const STRUCTURE_SCRIPT = `((GX, GY, EDGE) => {
  const vw = window.innerWidth, vh = window.innerHeight;
  const bodyBg = getComputedStyle(document.body).backgroundColor;
  const roots = [document];
  const capturedClosed = window.__designDnaCapturedShadowRoots || [];
  capturedClosed.forEach((item) => { if (item?.root && !roots.includes(item.root)) roots.push(item.root); });
  for (let rootIndex = 0; rootIndex < roots.length; rootIndex += 1) {
    roots[rootIndex].querySelectorAll('*').forEach((element) => {
      if (element.shadowRoot && !roots.includes(element.shadowRoot)) roots.push(element.shadowRoot);
    });
  }
  const allElements = [...new Set(roots.flatMap((root) => [...root.querySelectorAll('*')]))];
  const visible = (el) => {
    const style = getComputedStyle(el), rect = el.getBoundingClientRect();
    return style.display !== 'none' && style.visibility !== 'hidden' && Number(style.opacity) > 0 &&
      rect.width > 1 && rect.height > 1 && rect.bottom > 0 && rect.top < vh;
  };
  const visibleCanvases = allElements.filter((el) => el.tagName === 'CANVAS' && visible(el));
  const visibleFrames = allElements.filter((el) => el.tagName === 'IFRAME' && visible(el));
  const inspection = {
    roots: roots.length,
    open_or_captured_shadow_roots: roots.filter((root) => root.nodeType === 11).length,
    pseudo_elements: 0,
    visible_canvases: visibleCanvases.length,
    visible_iframes: visibleFrames.length,
    uninspectable: [
      ...visibleCanvases.map(() => 'canvas-structure-requires-raster-semantic-evidence'),
      ...visibleFrames.map(() => 'iframe-coordinate-space-not-projectable-by-structure-probe'),
    ],
  };

  const pseudoStyles = (el) => ['::before', '::after'].map((pseudo) => ({ pseudo, style: getComputedStyle(el, pseudo) }))
    .filter(({ style }) => style.display !== 'none' && Number(style.opacity) > 0 &&
      (String(style.content || '') !== 'none' && String(style.content || '') !== 'normal' ||
       style.backgroundImage !== 'none' || style.backgroundColor !== 'rgba(0, 0, 0, 0)' ||
       parseFloat(style.borderTopWidth) > 0 || style.boxShadow !== 'none'));
  inspection.pseudo_elements = allElements.reduce((sum, element) => sum + pseudoStyles(element).length, 0);

  const isMedia = (el) => {
    if (!el) return false;
    const t = el.tagName;
    if (t === 'IMG' || t === 'VIDEO' || t === 'CANVAS' || t === 'SVG' || t === 'PICTURE') return true;
    const bi = getComputedStyle(el).backgroundImage;
    return bi && bi !== 'none' && /url\\(/.test(bi);
  };
  const hasOwnText = (el) => {
    if (!el) return false;
    for (const n of el.childNodes) if (n.nodeType === 3 && n.nodeValue.trim().length) return true;
    return pseudoStyles(el).some(({ style }) => {
      const content = String(style.content || '');
      return content !== 'none' && content !== 'normal' && content !== '""' && content !== "''";
    });
  };
  const paints = (el) => {
    if (!el || el === document.body || el === document.documentElement) return false;
    const c = getComputedStyle(el);
    if (c.backgroundColor && c.backgroundColor !== 'rgba(0, 0, 0, 0)' && c.backgroundColor !== bodyBg) return true;
    if (parseFloat(c.borderTopWidth) || parseFloat(c.borderBottomWidth)) return true;
    if (pseudoStyles(el).some(({ style }) => style.backgroundImage !== 'none' ||
        style.backgroundColor !== 'rgba(0, 0, 0, 0)' || parseFloat(style.borderTopWidth) > 0 || style.boxShadow !== 'none')) return true;
    return false;
  };

  // Classify a sample point: 2 = media, 1 = text, 3 = a painted box, 0 = empty.
  //
  // A point counts as text only when a text node's own rectangle actually
  // covers it. Asking whether some ancestor merely CONTAINS text reported a
  // full-bleed photograph as "100% text", because a transparent wrapper with a
  // caption sat over the whole screen.
  const coversText = (el, x, y) => {
    for (const n of el.childNodes) {
      if (n.nodeType !== 3 || !n.nodeValue.trim()) continue;
      const range = document.createRange();
      range.selectNodeContents(n);
      for (const r of range.getClientRects()) {
        if (x >= r.left && x <= r.right && y >= r.top && y <= r.bottom) return true;
      }
    }
    return false;
  };
  const at = (x, y) => {
    const stack = [...document.elementsFromPoint(x, y)];
    for (const root of roots) {
      if (root === document || typeof root.elementsFromPoint !== 'function') continue;
      try { stack.push(...root.elementsFromPoint(x, y)); } catch { /* fail-closed metadata comes from the census */ }
    }
    let painted = 0;
    for (const el of stack) {
      if (el === document.body || el === document.documentElement) break;
      if (coversText(el, x, y)) return 1;
      if (isMedia(el)) return 2;
      if (!painted && paints(el)) painted = 3;
    }
    return painted;
  };

  const grid = [];
  let media = 0, text = 0, box = 0, empty = 0;
  for (let gy = 0; gy < GY; gy += 1) {
    const row = [];
    for (let gx = 0; gx < GX; gx += 1) {
      const x = Math.min(vw - 1, (gx + 0.5) * vw / GX);
      const y = Math.min(vh - 1, (gy + 0.5) * vh / GY);
      const v = at(x, y);
      row.push(v);
      if (v === 2) media += 1; else if (v === 1) text += 1; else if (v === 3) box += 1; else empty += 1;
    }
    grid.push(row);
  }
  const cells = GX * GY;

  // the largest thing actually on the first screen, and what kind it is
  let dominant = null, best = 0;
  allElements.forEach((el) => {
    const r = el.getBoundingClientRect();
    if (r.bottom <= 0 || r.top >= vh || r.width < 40 || r.height < 40) return;
    const w = Math.min(r.right, vw) - Math.max(r.left, 0);
    const h = Math.min(r.bottom, vh) - Math.max(r.top, 0);
    const area = Math.max(0, w) * Math.max(0, h);
    if (area <= best) return;
    const kind = isMedia(el) ? 'media' : (hasOwnText(el) ? 'text' : (paints(el) ? 'box' : null));
    if (!kind) return;
    best = area;
    dominant = { tag: el.tagName.toLowerCase(), kind, area_share: +(area / (vw * vh)).toFixed(3),
      cls: (typeof el.className === 'string' ? el.className : '').trim().slice(0, 40) };
  });

  // what lives against each edge of the first screen
  const band = (test) => {
    const kinds = new Set();
    allElements.forEach((el) => {
      const r = el.getBoundingClientRect();
      if (r.width < 8 || r.height < 8 || r.top > vh) return;
      if (!test(r)) return;
      const kind = isMedia(el) ? 'media' : (hasOwnText(el) ? 'text' : null);
      if (kind) kinds.add(kind);
    });
    return [...kinds].sort();
  };
  const edges = {
    top: band((r) => r.top < EDGE && r.bottom > 0),
    bottom: band((r) => r.bottom > vh - EDGE && r.top < vh),
    left: band((r) => r.left < EDGE && r.right > 0),
    right: band((r) => r.right > vw - EDGE && r.left < vw),
  };
  // corners, because a wordmark broken into the four corners is a structure a
  // property reader can never see
  const inCorner = (r, cx, cy) =>
    (cx === 0 ? r.left < EDGE * 2 : r.right > vw - EDGE * 2) &&
    (cy === 0 ? r.top < EDGE * 2 : r.bottom > vh - EDGE * 2 && r.top < vh);
  const corners = [[0, 0], [1, 0], [0, 1], [1, 1]].map(([cx, cy]) => {
    let found = 0;
    allElements.forEach((el) => {
      const r = el.getBoundingClientRect();
      if (r.width < 8 || r.height < 8 || r.top > vh) return;
      if (inCorner(r, cx, cy) && hasOwnText(el)) found = 1;
    });
    return found;
  });

  // type, by role, with proportions a face cannot fake
  const metrics = (family, size, weight) => {
    try {
      const c = document.createElement('canvas').getContext('2d');
      c.font = \`\${weight} 100px \${family}\`;
      const H = c.measureText('H'), x = c.measureText('x');
      const cap = H.actualBoundingBoxAscent || 0;
      const xh = x.actualBoundingBoxAscent || 0;
      const adv = c.measureText('Handgloves 0123').width;
      const iw = c.measureText('I').width;
      const raster = document.createElement('canvas'); raster.width = 720; raster.height = 150;
      const rc = raster.getContext('2d', { willReadFrequently: true });
      rc.fillStyle = '#000'; rc.font = \`\${weight} 96px \${family}\`; rc.textBaseline = 'alphabetic';
      const probe = 'Hamburgefontsiv 0123 Il1 @&?'; rc.fillText(probe, 4, 108);
      const data = rc.getImageData(0, 0, raster.width, raster.height).data;
      let hash = 2166136261, hash2 = 2654435769, ink = 0;
      for (let i = 3; i < data.length; i += 4) {
        if (!data[i]) continue;
        const signal = ((i / 4) & 0xffff) ^ data[i];
        ink += 1; hash ^= signal; hash = Math.imul(hash, 16777619);
        hash2 ^= signal + ink; hash2 = Math.imul(hash2, 2246822519);
      }
      return {
        x_ratio: cap ? +(xh / cap).toFixed(3) : null, advance: +(adv / 100).toFixed(3),
        i_ratio: cap ? +(iw / cap).toFixed(3) : null,
        lower_advance: +(c.measureText('abcdefghijklmnopqrstuvwxyz').width / 100).toFixed(3),
        upper_advance: +(c.measureText('ABCDEFGHIJKLMNOPQRSTUVWXYZ').width / 100).toFixed(3),
        digit_advance: +(c.measureText('0123456789').width / 100).toFixed(3),
        punct_advance: +(c.measureText('.,:;!?@&()[]').width / 100).toFixed(3),
        font_fingerprint: { raster: (hash >>> 0).toString(16).padStart(8, '0') + (hash2 >>> 0).toString(16).padStart(8, '0'), ink,
          probe_width: +rc.measureText(probe).width.toFixed(3) },
      };
    } catch (e) { return { x_ratio: null, advance: null }; }
  };
  let biggest = null, bigSize = 0;
  allElements.filter((el) => el.matches('h1,h2,h3,p,span,div,a,li')).forEach((el) => {
    const r = el.getBoundingClientRect();
    if (r.top >= vh || r.bottom <= 0 || !hasOwnText(el)) return;
    const s = parseFloat(getComputedStyle(el).fontSize) || 0;
    if (s > bigSize) { bigSize = s; biggest = el; }
  });
  const roleOf = (el) => {
    if (!el) return null;
    const c = getComputedStyle(el);
    const size = parseFloat(c.fontSize) || 0;
    return {
      family: c.fontFamily.split(',')[0].replace(/["']/g, '').trim(),
      size, weight: c.fontWeight,
      tracking: c.letterSpacing, transform: c.textTransform,
      leading: +( (parseFloat(c.lineHeight) || size) / size ).toFixed(3),
      ...metrics(c.fontFamily, size, c.fontWeight),
    };
  };
  const bodyStyle = getComputedStyle(document.body);
  const body = {
    family: bodyStyle.fontFamily.split(',')[0].replace(/["']/g, '').trim(),
    size: parseFloat(bodyStyle.fontSize) || 16,
    weight: bodyStyle.fontWeight,
    leading: +((parseFloat(bodyStyle.lineHeight) || 16) / (parseFloat(bodyStyle.fontSize) || 16)).toFixed(3),
    ...metrics(bodyStyle.fontFamily, 16, bodyStyle.fontWeight),
  };
  const display = roleOf(biggest);

  return {
    inspection: { ...inspection, complete: inspection.uninspectable.length === 0 },
    viewport: { w: vw, h: vh },
    grid,
    shares: {
      media: +(media / cells).toFixed(3),
      text: +(text / cells).toFixed(3),
      box: +(box / cells).toFixed(3),
      empty: +(empty / cells).toFixed(3),
    },
    dominant,
    edges,
    corners,
    type: {
      display, body,
      scale: display && body.size ? +(display.size / body.size).toFixed(2) : null,
      families: [...new Set([display && display.family, body.family].filter(Boolean))],
    },
  };
})(${GRID_X}, ${GRID_Y}, ${EDGE_PX})`;

/** Agreement between two classified grids, 0..1. */
export function gridAgreement(a, b) {
  if (!Array.isArray(a) || !Array.isArray(b) || a.length !== b.length) return 0;
  let same = 0, cells = 0;
  for (let y = 0; y < a.length; y += 1) {
    for (let x = 0; x < a[y].length; x += 1) {
      cells += 1;
      // Media and a painted box are different design decisions. Treating them
      // as equivalent let a colored rectangle pass for reference photography.
      if (a[y][x] === b[y][x]) same += 1;
    }
  }
  return cells ? +(same / cells).toFixed(3) : 0;
}

const near = (a, b, tol) =>
  typeof a === 'number' && typeof b === 'number' && b !== 0
    ? Math.abs(a - b) / Math.abs(b) <= tol
    : a === b;

/**
 * Does the build's first screen resemble the reference's?
 *
 * Four independent tests. All four are required: the old three-of-four rule
 * let a build replace the dominant medium or composition and compensate with
 * three coarse similarities.
 */
export function diffStructure(build, ref) {
  const tests = [];
  const bd = build.dominant || {}, rd = ref.dominant || {};
  tests.push({
    name: 'dominant',
    pass: bd.kind === rd.kind && near(bd.area_share, rd.area_share, 0.25),
    detail: `the largest thing on the first screen is ${bd.kind || 'nothing'} (<${bd.tag || '-'}>), the reference's is ${rd.kind || 'nothing'} (<${rd.tag || '-'}>)`,
  });
  const agree = gridAgreement(build.grid, ref.grid);
  tests.push({
    name: 'ink',
    pass: agree >= 0.7,
    value: agree,
    detail: `where media, text, surfaces and emptiness sit agrees on ${Math.round(agree * 100)}% of the screen (floor 70%)`,
  });
  const edgeScore = ['top', 'right', 'bottom', 'left'].reduce((n, side) => {
    const a = new Set(build.edges?.[side] || []);
    const b = new Set(ref.edges?.[side] || []);
    const union = new Set([...a, ...b]);
    if (!union.size) return n + 1;
    let hit = 0;
    union.forEach((k) => { if (a.has(k) && b.has(k)) hit += 1; });
    return n + hit / union.size;
  }, 0) / 4;
  const cornerScore = (build.corners || []).reduce(
    (n, v, i) => n + (v === (ref.corners || [])[i] ? 1 : 0), 0) / 4;
  tests.push({
    name: 'edges',
    pass: edgeScore >= 0.65 && cornerScore >= 0.75,
    value: +((edgeScore + cornerScore) / 2).toFixed(2),
    detail: `what sits against the edges matches ${Math.round(edgeScore * 100)}% and the corners ${Math.round(cornerScore * 100)}%`,
  });
  const bt = build.type || {}, rt = ref.type || {};
  const typeChecks = [
    near(bt.scale, rt.scale, 0.35),
    near(bt.display?.leading, rt.display?.leading, 0.25),
    near(bt.display?.x_ratio, rt.display?.x_ratio, 0.12),
    near(bt.body?.x_ratio, rt.body?.x_ratio, 0.12),
    near(bt.display?.advance, rt.display?.advance, 0.18),
    (bt.display?.transform || 'none') === (rt.display?.transform || 'none'),
  ];
  const typeScore = typeChecks.filter(Boolean).length / typeChecks.length;
  tests.push({
    name: 'type',
    pass: typeScore >= 0.8,
    value: +typeScore.toFixed(2),
    detail: `the type matches the reference on ${typeChecks.filter(Boolean).length} of ${typeChecks.length} proportions `
      + `(scale ${bt.scale} vs ${rt.scale}; display x-height ${bt.display?.x_ratio} vs ${rt.display?.x_ratio}; `
      + `width ${bt.display?.advance} vs ${rt.display?.advance}; case ${bt.display?.transform} vs ${rt.display?.transform})`,
  });
  const passed = tests.filter((t) => t.pass).length;
  const pass = passed === tests.length;
  return {
    pass,
    passed,
    of: tests.length,
    tests,
    verdict: pass
      ? 'The first screen is built like the reference it names.'
      : 'The first screen does not resemble the reference it names: '
        + tests.filter((t) => !t.pass).map((t) => t.detail).join('; '),
  };
}
