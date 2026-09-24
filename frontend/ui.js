/* Shared UI kit: line icons, card headers, tabs, progress, segmented bars,
   step-area KPI chart. Loaded before app.js.
   Icons are drawn in the Lucide style (MIT), 24px grid, 2px stroke. */
'use strict';

const ICONS = {
  dashboard: '<rect x="3" y="3" width="7" height="9" rx="1"/><rect x="14" y="3" width="7" height="5" rx="1"/><rect x="14" y="12" width="7" height="9" rx="1"/><rect x="3" y="16" width="7" height="5" rx="1"/>',
  users: '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/>',
  user: '<path d="M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/>',
  userPlus: '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M19 8v6"/><path d="M22 11h-6"/>',
  message: '<path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>',
  inbox: '<path d="M22 12h-6l-2 3h-4l-2-3H2"/><path d="M5.45 5.11 2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.45-6.89A2 2 0 0 0 16.76 4H7.24a2 2 0 0 0-1.79 1.11z"/>',
  megaphone: '<path d="m3 11 18-5v12L3 14v-3z"/><path d="M11.6 16.8a3 3 0 1 1-5.8-1.6"/>',
  chart: '<path d="M3 3v18h18"/><path d="M18 17V9"/><path d="M13 17V5"/><path d="M8 17v-3"/>',
  trend: '<path d="M3 3v18h18"/><path d="m19 9-5 5-4-4-3 3"/>',
  activity: '<path d="M22 12h-4l-3 9L9 3l-3 9H2"/>',
  shield: '<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/><path d="m9 12 2 2 4-4"/>',
  share: '<circle cx="18" cy="5" r="3"/><circle cx="6" cy="12" r="3"/><circle cx="18" cy="19" r="3"/><path d="m8.59 13.51 6.83 3.98"/><path d="m15.41 6.51-6.82 3.98"/>',
  list: '<path d="M8 6h13"/><path d="M8 12h13"/><path d="M8 18h13"/><path d="M3 6h.01"/><path d="M3 12h.01"/><path d="M3 18h.01"/>',
  file: '<path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z"/><path d="M14 2v6h6"/><path d="M16 13H8"/><path d="M16 17H8"/><path d="M10 9H8"/>',
  folder: '<path d="M4 20h16a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.93a2 2 0 0 1-1.66-.9l-.82-1.2A2 2 0 0 0 7.93 3H4a2 2 0 0 0-2 2v13c0 1.1.9 2 2 2Z"/>',
  sliders: '<path d="M4 21v-7"/><path d="M4 10V3"/><path d="M12 21v-9"/><path d="M12 8V3"/><path d="M20 21v-5"/><path d="M20 12V3"/><path d="M1 14h6"/><path d="M9 8h6"/><path d="M17 16h6"/>',
  help: '<circle cx="12" cy="12" r="10"/><path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"/><path d="M12 17h.01"/>',
  bell: '<path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9"/><path d="M10.3 21a1.94 1.94 0 0 0 3.4 0"/>',
  search: '<circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/>',
  calendar: '<rect x="3" y="4" width="18" height="18" rx="2"/><path d="M16 2v4"/><path d="M8 2v4"/><path d="M3 10h18"/>',
  more: '<circle cx="5" cy="12" r="1"/><circle cx="12" cy="12" r="1"/><circle cx="19" cy="12" r="1"/>',
  download: '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><path d="m7 10 5 5 5-5"/><path d="M12 15V3"/>',
  back: '<path d="m15 18-6-6 6-6"/>',
  chevronDown: '<path d="m6 9 6 6 6-6"/>',
  clock: '<circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/>',
  hash: '<path d="M4 9h16"/><path d="M4 15h16"/><path d="M10 3 8 21"/><path d="m16 3-2 18"/>',
  lock: '<rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/>',
  pencil: '<path d="M17 3a2.85 2.83 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5Z"/>',
  card: '<rect x="2" y="5" width="20" height="14" rx="2"/><path d="M2 10h20"/>',
  target: '<circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="6"/><circle cx="12" cy="12" r="2"/>',
  check: '<path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><path d="m9 11 3 3L22 4"/>',
  paperclip: '<path d="m21.44 11.05-9.19 9.19a6 6 0 0 1-8.49-8.49l8.57-8.57A4 4 0 1 1 18 8.84l-8.59 8.57a2 2 0 0 1-2.83-2.83l8.49-8.48"/>',
  send: '<path d="m22 2-7 20-4-9-9-4Z"/><path d="M22 2 11 13"/>',
  refresh: '<path d="M21 12a9 9 0 0 0-9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/><path d="M3 12a9 9 0 0 0 9 9 9.75 9.75 0 0 0 6.74-2.74L21 16"/><path d="M16 16h5v5"/>',
  plus: '<path d="M5 12h14"/><path d="M12 5v14"/>',
  logout: '<path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><path d="m16 17 5-5-5-5"/><path d="M21 12H9"/>',
  moon: '<path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z"/>',
  gauge: '<path d="m12 14 4-4"/><path d="M3.34 19a10 10 0 1 1 17.32 0"/>',
  history: '<path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/><path d="M12 7v5l4 2"/>',
  eye: '<path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7Z"/><circle cx="12" cy="12" r="3"/>',
  mail: '<rect x="2" y="4" width="20" height="16" rx="2"/><path d="m22 7-10 5L2 7"/>',
  panel: '<rect x="3" y="3" width="18" height="18" rx="2"/><path d="M9 3v18"/>',
  panelClose: '<rect x="3" y="3" width="18" height="18" rx="2"/><path d="M9 3v18"/><path d="m16 15-3-3 3-3"/>',
  panelOpen: '<rect x="3" y="3" width="18" height="18" rx="2"/><path d="M9 3v18"/><path d="m14 9 3 3-3 3"/>',
  chevronRight: '<path d="m9 18 6-6-6-6"/>',
  sun: '<circle cx="12" cy="12" r="4"/><path d="M12 2v2"/><path d="M12 20v2"/><path d="m4.93 4.93 1.41 1.41"/><path d="m17.66 17.66 1.41 1.41"/><path d="M2 12h2"/><path d="M20 12h2"/><path d="m6.34 17.66-1.41 1.41"/><path d="m19.07 4.93-1.41 1.41"/>',
  pause: '<rect x="6" y="4" width="4" height="16" rx="1"/><rect x="14" y="4" width="4" height="16" rx="1"/>',
  phone: '<rect x="5" y="2" width="14" height="20" rx="2"/><path d="M12 18h.01"/>',
};

/* An accessible on/off switch. */
function switchHtml(id, on, label) {
  return `<button class="switch" id="${id}" role="switch" aria-checked="${on ? 'true' : 'false'}"
    aria-label="${esc(label)}"><span></span></button>`;
}

/* Tick label thinning. The last label is shown only when it sits at least
   0.6 of a step away from the previous one, so end labels never collide. */
function showTick(i, N, step) {
  if (i % step === 0) return (N - 1) - i >= step * 0.6 || i === N - 1 || (N - 1) % step === 0;
  return i === N - 1;
}

/* Spread end-of-line direct labels so none sit closer than minGap pixels. */
function spreadLabels(ys, minGap, lo, hi) {
  const idx = ys.map((y, i) => [y, i]).sort((a, b) => a[0] - b[0]);
  for (let k = 1; k < idx.length; k++)
    if (idx[k][0] - idx[k - 1][0] < minGap) idx[k][0] = idx[k - 1][0] + minGap;
  const over = idx.length ? idx[idx.length - 1][0] - hi : 0;
  if (over > 0) idx.forEach(p => { p[0] = Math.max(lo, p[0] - over); });
  const out = []; idx.forEach(([y, i]) => { out[i] = y; }); return out;
}

function icon(name, size) {
  const s = size || 16;
  return `<svg class="ic" width="${s}" height="${s}" viewBox="0 0 24 24" fill="none" stroke="currentColor"
    stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${ICONS[name] || ICONS.hash}</svg>`;
}

const LOGO = `<svg width="30" height="30" viewBox="0 0 32 32" aria-hidden="true">
  <path d="M16 4a12 12 0 1 0 12 12h-6a6 6 0 1 1-6-6V4Z" fill="currentColor"/>
  <circle cx="23.5" cy="8.5" r="3.5" fill="currentColor"/></svg>`;

/* ------------------------------------------------------------ small bits */
function initials(name) {
  return String(name || '?').replace(/[^\p{L}\p{N} ]/gu, ' ').trim().split(/\s+/)
    .slice(0, 2).map(w => w[0] || '').join('').toUpperCase() || '#';
}
// Avatar tints come from a fixed list and follow the entity, never its rank.
const AVATAR_TINTS = ['#5b5fe9', '#e2703a', '#16a17a', '#c2410c', '#7c3aed', '#0e7490', '#b45309', '#be185d'];
function tintFor(key) {
  let h = 0; for (const ch of String(key)) h = (h * 31 + ch.charCodeAt(0)) >>> 0;
  return AVATAR_TINTS[h % AVATAR_TINTS.length];
}
function avatar(name, size) {
  const s = size || 32;
  return `<span class="avatar" style="width:${s}px;height:${s}px;font-size:${Math.round(s * .38)}px;background:${tintFor(name)}">${esc(initials(name))}</span>`;
}

function dotPill(label, color) {
  return `<span class="dot-pill"><i style="background:${color}"></i>${esc(label)}</span>`;
}

/* Progress rows, as in "Project completion". */
function progressRows(items) {
  return items.map(it => {
    const p = Math.max(0, Math.min(100, it.pct || 0));
    return `<div class="prog">
      <div class="prog-top"><span>${esc(it.label)}</span><strong>${it.value != null ? it.value : Math.round(p) + '%'}</strong></div>
      <div class="prog-track" role="progressbar" aria-valuenow="${Math.round(p)}" aria-valuemin="0" aria-valuemax="100"
        aria-label="${esc(it.label)}"><span style="width:${p}%"></span></div>
      ${it.note ? `<div class="prog-note">${esc(it.note)}</div>` : ''}
    </div>`;
  }).join('');
}

/* Segmented horizontal bar with 4px surface gaps and a dot legend carrying
   the values, as in "Recent activity". Every segment is labelled, so colour
   never carries meaning alone. */
function segBar(el, parts) {
  const total = parts.reduce((a, p) => a + (p.value || 0), 0);
  const live = parts.filter(p => p.value > 0);
  el.innerHTML = `
    <div class="segbar">${total ? live.map(p =>
      `<span style="flex:${p.value} 1 0;background:${p.color}" title="${esc(p.label)}: ${n(p.value)}"></span>`).join('')
      : '<span style="flex:1;background:var(--track)"></span>'}</div>
    <div class="seg-legend">${parts.map(p => `
      <div><i style="background:${p.color}"></i>${p.icon ? esc(p.icon) + ' ' : ''}${esc(p.label)}
        <strong>${n(p.value)}</strong>${total ? `<span>${(p.value / total * 100).toFixed(1)}%</span>` : ''}</div>`).join('')}
    </div>`;
}

/* Step-area KPI chart: one series, stepped line with a soft gradient fill,
   hover tooltip per bucket and a table view. Single series, so no legend. */
let _gradSeq = 0;
function stepArea(el, opts) {
  const { labels, values, yLabel } = opts;
  const W = Math.max(420, el.clientWidth || 560), H = opts.height || 200;
  const m = { t: 12, r: 6, b: 24, l: 6 };
  const iw = W - m.l - m.r, ih = H - m.t - m.b;
  const N = Math.max(1, values.length);
  const max = Math.max(1, ...values) * 1.15;
  const bw = iw / N;
  const X = i => m.l + i * bw;
  const Y = v => m.t + ih - (v / max) * ih;
  const gid = 'sa' + (++_gradSeq);
  let line = '', area = `M${X(0)},${m.t + ih}`;
  values.forEach((v, i) => {
    const y = Y(v).toFixed(1);
    line += `${i ? 'L' : 'M'}${X(i).toFixed(1)},${y} L${X(i + 1).toFixed(1)},${y} `;
    area += ` L${X(i).toFixed(1)},${y} L${X(i + 1).toFixed(1)},${y}`;
  });
  area += ` L${X(N)},${m.t + ih} Z`;
  const step = Math.max(1, Math.ceil(N / 7));
  let xl = '';
  labels.forEach((lb, i) => {
    if (!showTick(i, N, step)) return;
    xl += `<text x="${X(i) + bw / 2}" y="${H - 6}" text-anchor="middle">${esc(lb)}</text>`;
  });
  let hits = '';
  values.forEach((v, i) => {
    hits += `<rect class="sa-hit" data-i="${i}" x="${X(i)}" y="${m.t}" width="${bw}" height="${ih}" fill="transparent"/>`;
  });
  el.innerHTML = `
    <svg class="chart" viewBox="0 0 ${W} ${H}" preserveAspectRatio="xMidYMid meet" role="img" aria-label="${esc(yLabel || 'Chart')}">
      <defs><linearGradient id="${gid}" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0" stop-color="var(--series-1)" stop-opacity=".22"/>
        <stop offset="1" stop-color="var(--series-1)" stop-opacity="0"/></linearGradient></defs>
      <line class="axis-line" x1="${m.l}" y1="${m.t + ih}" x2="${m.l + iw}" y2="${m.t + ih}"/>
      <path d="${area}" fill="url(#${gid})"/>
      <path d="${line}" fill="none" stroke="var(--series-1)" stroke-width="2" stroke-linejoin="round"/>
      <rect id="${gid}hl" x="0" y="${m.t}" width="${bw}" height="${ih}" fill="var(--series-1)" opacity="0"/>
      ${xl}${hits}
    </svg>
    <div class="chart-foot"><span class="muted-sm">${esc(yLabel || '')}</span>
      <button class="btn sm ghost" data-tbl>${icon('list', 14)} Table</button></div>
    <div class="tbl-wrap hidden" data-tblwrap style="margin-top:8px;max-height:220px">
      <table><thead><tr><th>Period</th><th class="num">${esc(opts.seriesName || 'Value')}</th></tr></thead>
      <tbody>${labels.map((lb, i) => `<tr><td>${esc(lb)}</td><td class="num">${n(values[i])}</td></tr>`).join('')}</tbody></table>
    </div>`;
  const hl = $('#' + gid + 'hl', el);
  $$('.sa-hit', el).forEach(r => {
    r.addEventListener('mousemove', ev => {
      const i = +r.dataset.i;
      hl.setAttribute('x', X(i)); hl.setAttribute('opacity', '.06');
      showTip(`<div class="t-title">${esc(labels[i])}</div><div class="t-row"><span class="k">
        <span class="swatch" style="width:9px;height:9px;border-radius:3px;background:var(--series-1)"></span>
        ${esc(opts.seriesName || 'Value')}</span><span class="v">${n(values[i])}</span></div>`, ev.clientX, ev.clientY);
    });
    r.addEventListener('mouseleave', () => { hideTip(); hl.setAttribute('opacity', '0'); });
  });
  $('[data-tbl]', el).onclick = (e) => {
    const w = $('[data-tblwrap]', el); w.classList.toggle('hidden');
  };
}

/* ------------------------------------------------------------ card headers
   Turns <div class="card"><h2>Title</h2><div class="cap">sub</div> into the
   reference header: outlined icon box, title, and a subtitle. Runs after every
   render through a MutationObserver, so views that repaint stay consistent. */
const CARD_ICON_RULES = [
  [/read|receipt|who read/i, 'eye'], [/member|people|active/i, 'users'],
  [/message|chat|conversation|preview/i, 'message'], [/log|audit|trail/i, 'list'],
  [/campaign|despatch/i, 'megaphone'], [/snapshot|interval/i, 'clock'],
  [/outcome|delivery|reach/i, 'target'], [/governor|rate/i, 'gauge'],
  [/report|export|master/i, 'file'], [/feasib|metric|scope/i, 'check'],
  [/channel|groups api|bridge/i, 'share'], [/permission|role|user/i, 'shield'],
  [/about|detail|profile/i, 'user'], [/type/i, 'hash'], [/progress|activity/i, 'activity'],
];
function iconForTitle(t) {
  for (const [re, ic] of CARD_ICON_RULES) if (re.test(t)) return ic;
  return 'chart';
}
function enhanceCards(root) {
  $$('.card', root).forEach(card => {
    const h = card.firstElementChild;
    if (!h || h.tagName !== 'H2' || card.dataset.enh) return;
    card.dataset.enh = '1';
    const head = document.createElement('div');
    head.className = 'card-head';
    const cap = h.nextElementSibling && h.nextElementSibling.classList.contains('cap') ? h.nextElementSibling : null;
    const ic = h.dataset.icon || iconForTitle(h.textContent);
    head.innerHTML = `<span class="ico-box">${icon(ic, 16)}</span><div class="ch-t"></div><div class="ch-r"></div>`;
    card.insertBefore(head, h);
    $('.ch-t', head).appendChild(h);
    if (cap) $('.ch-t', head).appendChild(cap);
  });
  // tab visibility for views that mark sections with data-tab
  if (S.tab) $$('[data-tab]', root).forEach(el => el.classList.toggle('hidden', el.dataset.tab !== S.tab));
}
