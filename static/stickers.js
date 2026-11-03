/* Stickers: spend points to mint a random sticker, then collect, sort and filter them. */

const TIER_NAMES = ['COMMON', 'UNCOMMON', 'RARE', 'LEGENDARY', 'MYTHICAL'];
const RARITY_CLASS = { '': 'r0', 'COMMON': 'r0', 'UNCOMMON': 'r1', 'RARE': 'r2', 'LEGENDARY': 'r3', 'MYTHICAL': 'r4', 'ULTRA RARE': 'r3' };
const tierOf = (s) => (s.recipe && s.recipe.tier != null ? s.recipe.tier : Math.max(0, TIER_NAMES.indexOf(s.rarity)));
const DAMAGE_WORDS = ['Scuffed', 'Ripped', 'Shredded', 'Torn-Off'];
const ADJ_LABEL = { color: 'Colour', modifier: 'Size / age', look: 'Look', style_of: 'Style of' };

function stickerHex(s) { const r = s.recipe; return r ? (r.art_hex || (r.color && r.color.hex) || null) : null; }
function hueKey(s) {
  const hex = stickerHex(s);
  if (!hex) return [3, 0, 0];
  const n = parseInt(hex.slice(1), 16), r = (n >> 16) / 255, g = ((n >> 8) & 255) / 255, b = (n & 255) / 255;
  const mx = Math.max(r, g, b), mn = Math.min(r, g, b), d = mx - mn, l = (mx + mn) / 2;
  if (d < 0.08) return [2, 0, l];                         // greys and whites, by lightness
  let hh = mx === r ? ((g - b) / d) % 6 : mx === g ? (b - r) / d + 2 : (r - g) / d + 4;
  return [1, ((hh * 60) + 360) % 360, l];
}

/* The picture. Holographic stickers get a rainbow layer that follows the pointer. */
function stickerFig(s) {
  const q = (s.recipe && s.recipe.quality) || {};
  const fig = h('div', { class: 'stk r' + tierOf(s) + (q.holographic ? ' holo-on' : '') },
    h('img', { src: `/stickers/${s.id}.svg`, alt: s.name, loading: 'lazy' }));
  if (q.holographic) {
    fig.append(h('div', { class: 'holo', style: { '--m': `url(/stickers/${s.id}.svg)` } }));
    fig.addEventListener('pointermove', (e) => {
      const r = fig.getBoundingClientRect();
      fig.classList.add('tilting');
      fig.style.setProperty('--mx', ((e.clientX - r.left) / r.width * 100).toFixed(0) + '%');
      fig.style.setProperty('--my', ((e.clientY - r.top) / r.height * 100).toFixed(0) + '%');
    });
    fig.addEventListener('pointerleave', () => fig.classList.remove('tilting'));
  }
  return fig;
}

const SORTS = {
  rarity: ['Rarity (rarest first)', (a, b) => tierOf(b) - tierOf(a) || ((b.recipe && b.recipe.bits) || 0) - ((a.recipe && a.recipe.bits) || 0) || b.id - a.id],
  newest: ['Newest first', (a, b) => b.id - a.id],
  oldest: ['Oldest first', (a, b) => a.id - b.id],
  az: ['A to Z', (a, b) => ((a.recipe && a.recipe.specific) || a.name).localeCompare((b.recipe && b.recipe.specific) || b.name)],
  color: ['Colour', (a, b) => { const x = hueKey(a), y = hueKey(b); return x[0] - y[0] || x[1] - y[1] || x[2] - y[2]; }],
  category: ['Category', (a, b) => ((a.recipe && a.recipe.theme) || 'zzz').localeCompare((b.recipe && b.recipe.theme) || 'zzz') || a.name.localeCompare(b.name)],
};
const QUALITY_FILTERS = {
  any: ['Any quality', () => true],
  holographic: ['Holographic', (s) => s.recipe && s.recipe.quality.holographic],
  puffy: ['Puffy', (s) => s.recipe && s.recipe.quality.puffy],
  damaged: ['Damaged or torn', (s) => s.recipe && s.recipe.quality.damage > 0],
  verb: ['Doing something', (s) => s.recipe && s.recipe.verb],
  multi: ['Two or more adjectives', (s) => s.recipe && (s.recipe.adjectives || []).length >= 2],
  painter: ['In the style of a painter', (s) => s.recipe && s.recipe.painter],
};

const StickersView = {
  chosen: [], list: [],
  view: { sort: 'rarity', quality: 'any', tiers: [0, 1, 2, 3, 4], q: '' },
  render(root) {
    this.root = root; root.classList.remove('nopad');
    try { const sv = JSON.parse(localStorage.getItem('jot.stickerview') || '{}'); if (SORTS[sv.sort]) this.view.sort = sv.sort; } catch (e) { /* ignore */ }
    this.refresh();
  },
  async refresh() {
    this.list = await attempt(() => api('/api/stickers')) || [];
    this.col = await attempt(() => api('/api/stickers/collection')) || { owned: 0, total: 0 };
    const cost = S.data.costs.sticker, pts = S.data.points, ai = S.data.ai.configured && S.data.ai.enabled;
    const page = h('div', { class: 'page' });
    const useAi = h('input', { type: 'checkbox', checked: true });
    const chips = h('div', { class: 'row', style: { margin: '8px 0' } });
    const drawChips = () => {
      clear(chips).append(this.chosen.map((id) => S.iById[id] && h('span', { class: 'chip' }, S.iById[id].title.slice(0, 40),
        h('button', { class: 'icon-btn', style: { padding: '0 6px' }, 'aria-label': 'Remove', onclick: () => { this.chosen = this.chosen.filter((x) => x !== id); drawChips(); } }, '×'))));
    };
    const combo = ideaCombo({ placeholder: 'Optional: pick ideas to nudge what your sticker is about…', filter: (i) => !this.chosen.includes(i.id), onPick: (i) => { this.chosen.push(i.id); drawChips(); combo.redraw(); } });
    let busy = false;
    const mint = async (btn) => {
      if (busy) return;
      busy = true; const label = btn.textContent; btn.textContent = ai && useAi.checked ? 'Drawing…' : 'Minting…'; btn.disabled = true;
      const r = await attempt(() => api('/api/stickers', 'POST', { idea_ids: this.chosen, use_ai: useAi.checked }));
      busy = false; btn.textContent = label; btn.disabled = false;
      if (!r) return;
      this.chosen = [];
      await refresh();
      this.refresh();
      this.show(r, true);
    };
    const b1 = h('button', { class: 'btn primary', disabled: pts < cost, onclick: () => mint(b1) }, this.chosen.length ? `Mint from chosen ideas (${cost} pts)` : `Mint a sticker (${cost} pts)`);
    page.append(h('div', { class: 'card' }, h('h2', {}, 'Sticker shop'),
      h('p', { class: 'muted' }, `You have ${pts} points. A sticker costs ${cost}. ` + (ai ? 'Each one is a surprise: a thing, usually one adjective, sometimes doing something. The weirder the roll, the rarer the sticker, and very rarely one comes out puffy, holographic or torn.' : 'Each one is a surprise picture. Everyday things are common, odd ones are rare, and very rarely one comes out puffy, holographic or torn.')),
      combo.el, chips,
      h('div', { class: 'row' }, b1,
        ai ? h('label', { class: 'small' }, useAi, ' Let the AI draw it') : h('span', { class: 'muted small' }, 'No AI: you get a plain clipart sticker, like a Cat Sticker. Collect every picture! Connect an AI in Settings for drawn ones.'))));
    drawChips();
    this.book = h('div');
    page.append(this.book);
    clear(this.root).append(page);
    this.drawBook();
  },

  drawBook() {
    const v = this.view, all = this.list;
    const counts = TIER_NAMES.map((_, t) => all.filter((s) => tierOf(s) === t).length);
    const save = () => { try { localStorage.setItem('jot.stickerview', JSON.stringify({ sort: v.sort })); } catch (e) { /* ignore */ } };
    const sortSel = h('select', { 'aria-label': 'Sort stickers', style: { width: 'auto' }, onchange: () => { v.sort = sortSel.value; save(); this.drawBook(); } },
      Object.entries(SORTS).map(([k, [label]]) => h('option', { value: k, selected: k === v.sort }, label)));
    const qSel = h('select', { 'aria-label': 'Filter by quality', style: { width: 'auto' }, onchange: () => { v.quality = qSel.value; this.drawBook(); } },
      Object.entries(QUALITY_FILTERS).map(([k, [label]]) => h('option', { value: k, selected: k === v.quality }, label)));
    const search = h('input', { type: 'search', placeholder: 'Search names…', 'aria-label': 'Search stickers', value: v.q, style: { width: '170px' },
      oninput: debounce(() => { v.q = search.value; this.drawBook(); }, 150) });
    const tierBtns = TIER_NAMES.map((n, t) => h('button', { class: 'tierbtn r' + t, 'aria-pressed': String(v.tiers.includes(t)), title: `Show or hide ${n.toLowerCase()} stickers`,
      onclick: () => { v.tiers = v.tiers.includes(t) ? v.tiers.filter((x) => x !== t) : [...v.tiers, t]; this.drawBook(); } }, `${n[0] + n.slice(1).toLowerCase()} ${counts[t]}`));

    const q = v.q.trim().toLowerCase();
    const shown = all.filter((s) => v.tiers.includes(tierOf(s)) && QUALITY_FILTERS[v.quality][1](s) && (!q || s.name.toLowerCase().includes(q)))
      .sort(SORTS[v.sort][1]);
    clear(this.book).append(
      h('div', { class: 'row between', style: { marginTop: '26px' } }, h('h2', {}, `Your collection (${all.length})`),
        h('span', { class: 'muted small' }, (this.col && this.col.total ? `${this.col.owned} of ${this.col.total} pictures collected` : '') + (shown.length === all.length ? '' : `  ·  Showing ${shown.length}`))),
      all.length ? h('div', { class: 'row', style: { margin: '6px 0 12px' } }, tierBtns, h('span', { class: 'spacer' }), qSel, sortSel, search) : null,
      shown.length ? h('div', { class: 'sticker-grid' }, shown.map((s) => h('button', { class: 'sticker r' + tierOf(s), onclick: () => this.show(s), 'aria-label': s.name },
        stickerFig(s), tierOf(s) ? h('span', { class: 'rbadge r' + tierOf(s) }, TIER_NAMES[tierOf(s)]) : null, h('div', { class: 'sname' }, s.name))))
        : h('div', { class: 'empty' }, all.length ? 'No stickers match these filters.' : 'No stickers yet. Keep jotting and brainstorming to earn points!'));
  },

  show(s, isNew) {
    modal((box, close) => {
      const r = s.recipe, q = (r && r.quality) || {}, tier = tierOf(s);
      const tags = [];
      if (r) {
        tags.push(['Thing', r.specific, r.area]);
        if (r.adjectives && r.adjectives.length) {
          for (const a of r.adjectives) tags.push([ADJ_LABEL[a.type] || a.type, a.type === 'style_of' ? a.text : a.text, null, a.hex]);
        } else {                                     // stickers made before adjectives existed
          if (r.color) tags.push(['Colour', r.color.name, null, r.color.hex]);
          if (r.modifier) tags.push(['Size / age', r.modifier]);
          if (r.style) tags.push(['Style', r.style.text]);
        }
        if (r.verb) tags.push(['Doing', r.verb]);
        if (q.damage) tags.push(['Damage', DAMAGE_WORDS[q.damage - 1]]);
        if (q.puffy) tags.push(['Special', 'Puffy']);
        if (q.holographic) tags.push(['Special', 'Holographic']);
      }
      box.append(
        isNew ? h('p', { class: 'pts-pop', style: { textAlign: 'center', margin: 0 } }, 'New sticker!') : null,
        h('div', { class: 'stk-big' }, stickerFig(s)),
        tier ? h('div', { style: { textAlign: 'center' } }, h('span', { class: 'rbadge big r' + tier }, TIER_NAMES[tier])) : null,
        h('h2', { style: { textAlign: 'center', marginTop: '10px' } }, s.name),
        tags.length ? h('div', { class: 'row', style: { justifyContent: 'center' } }, tags.map(([k, v, sub, hex]) =>
          h('span', { class: 'chip', title: sub || k }, h('b', {}, k + ':'), hex ? h('span', { class: 'dot', style: { '--c': hex } }) : null, ' ' + v))) : null,
        r && r.bits ? h('p', { class: 'muted small', style: { textAlign: 'center', margin: '8px 0 0' } }, `Rarity score ${r.bits} · the weirder the rolls, the higher it goes`) : null,
        h('p', { class: 'muted small', style: { textAlign: 'center' } }, s.source === 'ai' ? 'Drawn by the AI' : (r ? 'Made from an emoji. Connect an AI for real drawings.' : 'Generated from your ideas')),
        (s.idea_ids || []).filter((i) => S.iById[i]).length ? h('div', {}, h('div', { class: 'muted small' }, 'Inspired by:'),
          s.idea_ids.filter((i) => S.iById[i]).map((i) => h('div', { class: 'link-row' }, h('a', { onclick: () => { close(); openIdea(i); } }, S.iById[i].title)))) : null,
        h('div', { class: 'row between', style: { marginTop: '12px' } },
          h('button', { class: 'btn danger', onclick: async () => { if (await confirmBox('Delete this sticker? Points are not refunded.')) { await attempt(() => api(`/api/stickers/${s.id}`, 'DELETE')); close(); this.refresh(); } } }, 'Delete'),
          h('button', { class: 'btn', autofocus: true, onclick: close }, 'Close')));
    });
  },
};
