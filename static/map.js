/* The map: an Obsidian-style network of ideas on a canvas, with a small force simulation. */

const MapView = {
  nodes: [], byId: new Map(), edges: [], cam: { x: 0, y: 0, k: 1 }, alpha: 0, raf: 0, dirty: true,
  hover: null, drag: null, fitted: false, theme: {},

  render(root) {
    this.root = root;
    root.classList.add('nopad');
    clear(root);
    Object.assign(this, { nodes: [], byId: new Map(), edges: [], cam: { x: 0, y: 0, k: 1 }, alpha: 0, raf: 0, dirty: true, hover: null, drag: null, fitted: false });
    const f = S.filter;

    this.gbar = h('div');
    this.q = h('input', { type: 'search', placeholder: 'Find on map…', 'aria-label': 'Find on the map', value: f.q,
      oninput: (e) => { f.q = e.target.value; saveFilter(); this.draw(); } });
    const chk = (label, key, extra) => h('label', {}, h('input', { type: 'checkbox', checked: !!f[key], onchange: (e) => { f[key] = e.target.checked; saveFilter(); extra && extra(); this.draw(); } }), label);
    this.cluster = true;
    const stat = Object.entries(CONFIG.statuses).map(([k, v]) =>
      h('label', { title: v.help }, h('input', { type: 'checkbox', checked: !f.hiddenStatuses.includes(k), onchange: (e) => {
        f.hiddenStatuses = f.hiddenStatuses.filter((x) => x !== k); if (!e.target.checked) f.hiddenStatuses.push(k);
        saveFilter(); this.sync(); } }), `${v.glyph} ${v.label}`));
    const tools = h('div', { class: 'tools' }, this.q,
      h('span', { class: 'row', style: { gap: '10px' } }, stat),
      chk('Suggested links', 'showSuggested'),
      chk('Follow lineage of selected', 'focusLineage'),
      h('label', {}, h('input', { type: 'checkbox', checked: true, onchange: (e) => { this.cluster = e.target.checked; this.heat(0.5); } }), 'Cluster by group'),
      h('button', { class: 'btn', onclick: () => this.fit() }, 'Fit'),
      h('button', { class: 'btn', onclick: () => this.scramble() }, 'Re-arrange'));
    this.toolbar = h('div', { class: 'toolbar' }, this.gbar, tools);

    this.canvas = h('canvas', { id: 'map', role: 'img', 'aria-label': 'Map of your ideas. Click an idea to open it.' });
    this.tip = h('div', { class: 'map-tip hidden' });
    this.banner = h('div', { class: 'hl-banner hidden' });
    this.empty = h('div', { class: 'empty hidden', style: { position: 'absolute', inset: 0, display: 'grid', placeItems: 'center', pointerEvents: 'none' } });
    const legend = h('div', { class: 'legend' },
      Object.entries(CONFIG.statuses).map(([k, v]) => h('div', {}, h('span', { class: 'sw' }, v.glyph), `${v.label}`)),
      h('div', {}, h('span', { class: 'sw' }, '→'), 'came from / led to'),
      h('div', {}, h('span', { class: 'sw' }, '—'), 'related'),
      h('div', {}, h('span', { class: 'sw' }, '- -'), 'might be related'),
      h('div', { class: 'muted' }, 'Colour = group · size = activity'));
    this.wrap = h('div', { id: 'mapwrap' }, this.canvas, legend, this.tip, this.banner, this.empty);
    root.append(this.toolbar, this.wrap);
    this.ctx = this.canvas.getContext('2d');
    this.drawGbar();
    this.readTheme();
    this.bind();
    this.ro = new ResizeObserver(() => { this.resize(); });
    this.ro.observe(this.wrap);
    this.resize();
    this.sync(true);
    this.loop();
  },

  destroy() {
    cancelAnimationFrame(this.raf); this.raf = 0;
    if (this.ro) this.ro.disconnect();
    window.removeEventListener('jot-theme', this._theme);
  },

  drawGbar() { clear(this.gbar).append(groupFilterBar(() => this.sync())); },

  readTheme() {
    const cs = getComputedStyle(document.documentElement);
    const g = (n) => cs.getPropertyValue(n).trim();
    this.theme = { bg: g('--map-bg'), edge: g('--map-edge'), text: g('--text'), accent: g('--accent'), hl: g('--hl'), muted: g('--muted'), panel: g('--panel') };
    this._theme = () => { this.readTheme(); this.draw(); };
    window.addEventListener('jot-theme', this._theme, { once: true });
  },

  /* ---- data -> nodes/edges ---- */
  refresh() { this.drawGbar(); this.sync(); },
  select() { this.draw(); },

  sync(first) {
    const vis = S.data.ideas.filter(ideaVisible);
    const old = this.byId;
    const next = new Map();
    const deg = {};
    for (const l of S.data.links) { deg[l.source] = (deg[l.source] || 0) + 1; deg[l.target] = (deg[l.target] || 0) + 1; }
    let added = 0;
    for (const i of vis) {
      let n = old.get(i.id);
      if (!n) {
        added++;
        let x, y;
        if (i.x != null && i.y != null) { x = i.x; y = i.y; }
        else {
          const par = S.data.links.find((l) => l.kind === 'spawned' && l.target === i.id && old.get(l.source));
          const base = par ? old.get(par.source) : null;
          const a = Math.random() * 6.283, d = base ? 50 : 40 + Math.random() * Math.sqrt(vis.length) * 40;
          x = (base ? base.x : 0) + Math.cos(a) * d; y = (base ? base.y : 0) + Math.sin(a) * d;
        }
        n = { id: i.id, x, y, vx: 0, vy: 0 };
      }
      const act = 1 + i.n_notes / 250 + i.n_updates * 2 + i.n_brain + i.n_files + (deg[i.id] || 0);
      n.r = 7 + Math.min(9, 2 * Math.sqrt(act));
      n.idea = i;
      next.set(i.id, n);
    }
    this.byId = next; this.nodes = [...next.values()];
    this.edges = [];
    for (const l of S.data.links) { const a = next.get(l.source), b = next.get(l.target); if (a && b) this.edges.push({ a, b, kind: l.kind }); }
    for (const s of S.data.suggested) { const a = next.get(s.source), b = next.get(s.target); if (a && b) this.edges.push({ a, b, kind: 'suggested' }); }
    this.empty.classList.toggle('hidden', this.nodes.length > 0);
    clear(this.empty).append(S.data.ideas.length ? 'No ideas match the filters above.' : 'Your map is empty. Jot something down on the Home tab!');
    this.heat(first ? 1 : added ? 0.6 : 0.2);
    if (first && !this.fitted && this.nodes.length) { for (let t = 0; t < 120; t++) this.tick(1 - t / 160); this.fit(true); this.fitted = true; }
    this.draw();
  },

  heat(a) { this.alpha = Math.max(this.alpha, a); this.dirty = true; if (!this.raf) this.loop(); },

  scramble() {
    for (const n of this.nodes) { n.x = (Math.random() - .5) * 400; n.y = (Math.random() - .5) * 400; n.vx = n.vy = 0; }
    this.heat(1); setTimeout(() => this.fit(), 900);
  },

  /* ---- simulation ---- */
  tick(alpha) {
    const N = this.nodes, n = N.length;
    for (let i = 0; i < n; i++) {
      const a = N[i];
      for (let j = i + 1; j < n; j++) {
        const b = N[j];
        let dx = a.x - b.x, dy = a.y - b.y, d2 = dx * dx + dy * dy;
        if (d2 > 90000) continue;
        if (d2 < 1) { dx = Math.random() - .5; dy = Math.random() - .5; d2 = 1; }
        const d = Math.sqrt(d2), f = (2600 / d2) * alpha, fx = dx / d * f, fy = dy / d * f;
        a.vx += fx; a.vy += fy; b.vx -= fx; b.vy -= fy;
      }
    }
    for (const e of this.edges) {
      const want = e.kind === 'spawned' ? 80 : e.kind === 'related' ? 110 : 170;
      const k = e.kind === 'suggested' ? 0.015 : 0.06;
      const dx = e.b.x - e.a.x, dy = e.b.y - e.a.y, d = Math.sqrt(dx * dx + dy * dy) || 1;
      const f = (d - want) * k * alpha, fx = dx / d * f, fy = dy / d * f;
      e.a.vx += fx; e.a.vy += fy; e.b.vx -= fx; e.b.vy -= fy;
    }
    if (this.cluster) {
      const cen = {};
      for (const nd of N) { const g = this.primaryGroup(nd.idea); const c = cen[g] || (cen[g] = { x: 0, y: 0, n: 0 }); c.x += nd.x; c.y += nd.y; c.n++; }
      for (const nd of N) { const c = cen[this.primaryGroup(nd.idea)]; nd.vx += (c.x / c.n - nd.x) * 0.012 * alpha; nd.vy += (c.y / c.n - nd.y) * 0.012 * alpha; }
    }
    for (const nd of N) {
      nd.vx -= nd.x * 0.004 * alpha; nd.vy -= nd.y * 0.004 * alpha;
      if (nd === (this.drag && this.drag.node)) { nd.vx = nd.vy = 0; continue; }
      nd.vx *= 0.82; nd.vy *= 0.82;
      nd.x += Math.max(-30, Math.min(30, nd.vx)); nd.y += Math.max(-30, Math.min(30, nd.vy));
    }
  },
  primaryGroup(idea) {
    const gs = (idea.groups || []).filter((g) => S.gById[g]);
    if (!gs.length) return 0;
    return gs.sort((a, b) => groupDepth(b) - groupDepth(a))[0];
  },

  loop() {
    if (!this.root || !this.root.isConnected) { this.raf = 0; return; }
    this.raf = requestAnimationFrame(() => {
      this.raf = 0;
      if (this.alpha > 0.015 || (this.drag && this.drag.node)) {
        this.tick(Math.max(this.alpha, this.drag && this.drag.node ? 0.15 : 0));
        this.alpha *= 0.985; this.dirty = true;
      }
      if (this.dirty) { this.dirty = false; this.paint(); }
      if (this.alpha > 0.015 || this.dirty || this.drag) this.loop();
    });
  },
  draw() { this.dirty = true; if (!this.raf) this.loop(); },

  /* ---- view ---- */
  resize() {
    const r = this.wrap.getBoundingClientRect(), dpr = window.devicePixelRatio || 1;
    if (this.w && this.fitted) { this.cam.x += (r.width - this.w) / 2; this.cam.y += (r.height - this.h) / 2; } // keep the middle in the middle
    this.w = r.width; this.h = r.height;
    this.canvas.width = Math.max(1, r.width * dpr); this.canvas.height = Math.max(1, r.height * dpr);
    this.dpr = dpr;
    if (!this.fitted && this.nodes.length) { this.fit(true); this.fitted = true; }
    this.paint();   // resizing blanks a canvas, so repaint straight away
    this.draw();
  },
  fit(instant) {
    if (!this.nodes.length) { this.cam = { x: 0, y: 0, k: 1 }; this.draw(); return; }
    let x0 = 1e9, y0 = 1e9, x1 = -1e9, y1 = -1e9;
    for (const n of this.nodes) { x0 = Math.min(x0, n.x - n.r); x1 = Math.max(x1, n.x + n.r); y0 = Math.min(y0, n.y - n.r); y1 = Math.max(y1, n.y + n.r); }
    const pad = 70, k = Math.min((this.w - pad * 2) / Math.max(x1 - x0, 60), (this.h - pad * 2) / Math.max(y1 - y0, 60), 1.6);
    this.cam = { k: Math.max(0.15, k), x: this.w / 2 - ((x0 + x1) / 2) * k, y: this.h / 2 - ((y0 + y1) / 2) * k };
    this.draw();
  },
  toWorld(px, py) { return [(px - this.cam.x) / this.cam.k, (py - this.cam.y) / this.cam.k]; },
  nodeAt(px, py) {
    const [wx, wy] = this.toWorld(px, py);
    for (let i = this.nodes.length - 1; i >= 0; i--) {
      const n = this.nodes[i], r = n.r + 4 / this.cam.k;
      if ((n.x - wx) ** 2 + (n.y - wy) ** 2 <= r * r) return n;
    }
    return null;
  },

  /* ---- input ---- */
  bind() {
    const c = this.canvas;
    const pos = (e) => { const r = c.getBoundingClientRect(); return [e.clientX - r.left, e.clientY - r.top]; };
    c.addEventListener('pointerdown', (e) => {
      const [px, py] = pos(e); c.setPointerCapture(e.pointerId);
      const node = this.nodeAt(px, py);
      this.drag = { node, sx: px, sy: py, moved: false, cx: this.cam.x, cy: this.cam.y };
    });
    c.addEventListener('pointermove', (e) => {
      const [px, py] = pos(e), d = this.drag;
      if (d) {
        if (Math.abs(px - d.sx) + Math.abs(py - d.sy) > 4) d.moved = true;
        if (d.moved) {
          if (d.node) { [d.node.x, d.node.y] = this.toWorld(px, py); this.alpha = Math.max(this.alpha, 0.2); }
          else { this.cam.x = d.cx + px - d.sx; this.cam.y = d.cy + py - d.sy; }
          this.draw();
        }
        return;
      }
      const n = this.nodeAt(px, py);
      if (n !== this.hover) { this.hover = n; c.style.cursor = n ? 'pointer' : 'grab'; this.showTip(n, px, py); this.draw(); }
      else if (n) this.showTip(n, px, py);
    });
    const up = () => {
      const d = this.drag; this.drag = null;
      if (d && d.node) {
        if (!d.moved) openIdea(d.node.id);
        else api(`/api/ideas/${d.node.id}`, 'PATCH', { x: d.node.x, y: d.node.y }).catch(() => {});
      }
      this.draw();
    };
    c.addEventListener('pointerup', up); c.addEventListener('pointercancel', up);
    c.addEventListener('pointerleave', () => { if (!this.drag) { this.hover = null; this.tip.classList.add('hidden'); this.draw(); } });
    c.addEventListener('wheel', (e) => {
      e.preventDefault();
      const [px, py] = pos(e), z = Math.exp(-e.deltaY * 0.0015), k = Math.max(0.1, Math.min(4, this.cam.k * z));
      const [wx, wy] = this.toWorld(px, py);
      this.cam.k = k; this.cam.x = px - wx * k; this.cam.y = py - wy * k; this.draw();
    }, { passive: false });
    c.addEventListener('keydown', () => {});
  },

  showTip(n, px, py) {
    if (!n) { this.tip.classList.add('hidden'); return; }
    const i = n.idea, st = CONFIG.statuses[i.status];
    clear(this.tip).append(h('b', {}, i.title), h('div', { class: 'muted small' }, `${st.glyph} ${st.label} · ${i.groups.filter((g) => S.gById[g]).map((g) => S.gById[g].name).join(', ') || 'ungrouped'}`),
      i.snippet ? h('div', { class: 'small' }, i.snippet.slice(0, 90) + (i.snippet.length > 90 ? '…' : '')) : null);
    this.tip.classList.remove('hidden');
    this.tip.style.left = Math.min(px + 14, this.w - 290) + 'px'; this.tip.style.top = (py + 14) + 'px';
  },

  /* ---- painting ---- */
  activeSet() {
    // which nodes stay bright. null = all of them.
    if (S.highlight.size) return S.highlight;
    const q = S.filter.q.trim().toLowerCase();
    if (q) return new Set(this.nodes.filter((n) => (n.idea.title + ' ' + n.idea.snippet).toLowerCase().includes(q)).map((n) => n.id));
    if (S.filter.focusLineage && S.selected) return lineageOf(S.selected);
    return null;
  },

  paint() {
    const ctx = this.ctx, t = this.theme, { k, x, y } = this.cam, dpr = this.dpr || 1;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.fillStyle = t.bg; ctx.fillRect(0, 0, this.w, this.h);
    ctx.save(); ctx.translate(x, y); ctx.scale(k, k);
    const act = this.activeSet();
    const dim = (n) => act && !act.has(n.id);
    const showSug = S.filter.showSuggested;

    for (const e of this.edges) {
      if (e.kind === 'suggested' && !showSug) continue;
      const faded = act && !(act.has(e.a.id) && act.has(e.b.id));
      ctx.globalAlpha = faded ? 0.07 : e.kind === 'suggested' ? 0.5 : 0.85;
      ctx.beginPath(); ctx.moveTo(e.a.x, e.a.y); ctx.lineTo(e.b.x, e.b.y);
      ctx.setLineDash(e.kind === 'suggested' ? [4 / k, 5 / k] : []);
      ctx.strokeStyle = e.kind === 'spawned' ? t.accent : t.edge;
      ctx.lineWidth = (e.kind === 'spawned' ? 2.2 : 1.4) / Math.sqrt(k);
      ctx.stroke(); ctx.setLineDash([]);
      if (e.kind === 'spawned') {
        const dx = e.b.x - e.a.x, dy = e.b.y - e.a.y, d = Math.hypot(dx, dy) || 1, ux = dx / d, uy = dy / d;
        const tx = e.b.x - ux * (e.b.r + 3), ty = e.b.y - uy * (e.b.r + 3), s = 7 / Math.sqrt(k);
        ctx.beginPath(); ctx.moveTo(tx, ty); ctx.lineTo(tx - ux * s - uy * s * .5, ty - uy * s + ux * s * .5); ctx.lineTo(tx - ux * s + uy * s * .5, ty - uy * s - ux * s * .5); ctx.closePath();
        ctx.fillStyle = t.accent; ctx.fill();
      }
    }
    ctx.globalAlpha = 1;

    const labelAll = k >= 0.75;
    for (const n of this.nodes) this.drawNode(ctx, n, dim(n), labelAll, k, act);
    ctx.restore();

    if (S.highlight.size) {
      this.banner.classList.remove('hidden');
      clear(this.banner).append(`${S.highlightLabel || 'Librarian'}: ${plural(S.highlight.size, 'idea')}`,
        h('button', { onclick: () => setHighlight([]) }, 'Clear'));
    } else this.banner.classList.add('hidden');
  },

  drawNode(ctx, n, dimmed, labelAll, k, act) {
    const i = n.idea, col = ideaColor(i), r = n.r, st = i.status;
    ctx.globalAlpha = dimmed ? 0.14 : st === 'failed' ? 0.62 : st === 'shelved' ? 0.8 : 1;
    const hl = S.highlight.has(n.id), sel = S.selected === n.id, hov = this.hover === n;
    if (hl) { ctx.beginPath(); ctx.arc(n.x, n.y, r + 7, 0, 6.283); ctx.fillStyle = this.theme.hl + '55'; ctx.fill(); ctx.strokeStyle = this.theme.hl; ctx.lineWidth = 3; ctx.stroke(); }
    ctx.beginPath();
    if (st === 'partial') { ctx.moveTo(n.x, n.y - r * 1.2); ctx.lineTo(n.x + r * 1.2, n.y); ctx.lineTo(n.x, n.y + r * 1.2); ctx.lineTo(n.x - r * 1.2, n.y); ctx.closePath(); }
    else ctx.arc(n.x, n.y, r, 0, 6.283);
    if (st === 'shelved') { ctx.fillStyle = this.theme.bg; ctx.fill(); ctx.strokeStyle = col; ctx.lineWidth = 3; ctx.stroke(); }
    else { ctx.fillStyle = col; ctx.fill(); }
    if (st === 'failed') { ctx.setLineDash([3, 3]); ctx.strokeStyle = this.theme.text; ctx.lineWidth = 1.5; ctx.stroke(); ctx.setLineDash([]); }
    if (st === 'worked') { ctx.beginPath(); ctx.arc(n.x, n.y, r + 3.5, 0, 6.283); ctx.strokeStyle = col; ctx.lineWidth = 2; ctx.stroke(); }
    // more than one group: a ring of segments
    const cols = ideaGroupColors(i);
    if (cols.length > 1 && st !== 'worked') {
      const seg = 6.283 / cols.length;
      cols.forEach((c, m) => { ctx.beginPath(); ctx.arc(n.x, n.y, r + 3.5, m * seg - 1.57, (m + 1) * seg - 1.57 - 0.08); ctx.strokeStyle = c; ctx.lineWidth = 2.5; ctx.stroke(); });
    }
    // glyph inside
    const glyph = st === 'worked' ? '✔' : st === 'failed' ? '✖' : st === 'shelved' ? '' : '';
    if (glyph) { ctx.fillStyle = '#fff'; ctx.font = `bold ${Math.round(r)}px system-ui`; ctx.textAlign = 'center'; ctx.textBaseline = 'middle'; ctx.fillText(glyph, n.x, n.y + 1); }
    if (sel) { ctx.beginPath(); ctx.arc(n.x, n.y, r + 7, 0, 6.283); ctx.strokeStyle = this.theme.text; ctx.lineWidth = 2.5; ctx.stroke(); }
    if (labelAll || sel || hov || hl || (act && act.has(n.id) && act.size < 25)) {
      const label = i.title.length > 30 ? i.title.slice(0, 28) + '…' : i.title;
      ctx.font = `${Math.max(11, 12 / Math.sqrt(k))}px system-ui, sans-serif`; ctx.textAlign = 'center'; ctx.textBaseline = 'top';
      ctx.lineWidth = 4; ctx.strokeStyle = this.theme.bg; ctx.strokeText(label, n.x, n.y + r + 5);
      ctx.fillStyle = this.theme.text; ctx.fillText(label, n.x, n.y + r + 5);
    }
    ctx.globalAlpha = 1;
  },
};
