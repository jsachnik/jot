/* Idea search dropdown (used for linking and for "Give an Update") and the update dialog. */

function ideaCombo(opts) {
  const input = h('input', { type: 'text', placeholder: opts.placeholder || 'Search your ideas…', 'aria-label': opts.placeholder || 'Search ideas', autocomplete: 'off' });
  const list = h('div', { class: 'list hidden', role: 'listbox' });
  const el = h('div', { class: 'combo' }, input, list);
  let items = [], sel = 0;

  function matches() {
    const terms = input.value.toLowerCase().split(/\s+/).filter(Boolean);
    const gids = opts.groupIds ? opts.groupIds() : null;          // null = any group
    let pool = S.data.ideas.filter((i) => !opts.filter || opts.filter(i));
    if (gids && gids.length) {
      const allowed = new Set(gids.flatMap(descendants));
      pool = pool.filter((i) => (i.groups || []).some((g) => allowed.has(g)));
    }
    if (terms.length) {
      pool = pool.filter((i) => { const t = (i.title + ' ' + i.snippet).toLowerCase(); return terms.every((w) => t.includes(w)); });
      pool.sort((a, b) => (b.title.toLowerCase().includes(terms[0]) ? 1 : 0) - (a.title.toLowerCase().includes(terms[0]) ? 1 : 0));
    } else pool.sort((a, b) => b.updated_at.localeCompare(a.updated_at));
    return pool.slice(0, 12);
  }
  function draw() {
    items = matches(); sel = Math.min(sel, Math.max(items.length - 1, 0));
    clear(list);
    if (!items.length) list.append(h('div', { class: 'item muted' }, S.data.ideas.length ? 'No matching ideas' : 'No ideas yet'));
    items.forEach((i, n) => list.append(h('div', { class: 'item' + (n === sel ? ' sel' : ''), role: 'option', onmousedown: (e) => { e.preventDefault(); pick(i); } },
      h('div', {}, h('div', { class: 'item-title' }, i.title),
        h('div', { class: 'row', style: { gap: '4px' } }, (i.groups || []).filter((g) => S.gById[g]).map((g) => h('span', { class: 'chip', style: { '--c': S.gById[g].color } }, h('span', { class: 'dot' }), S.gById[g].name)))),
      h('span', { class: 'st ' + i.status }, CONFIG.statuses[i.status].label))));
    list.classList.remove('hidden');
  }
  function pick(i) { list.classList.add('hidden'); input.value = ''; opts.onPick(i); }
  input.addEventListener('input', () => { sel = 0; draw(); });
  input.addEventListener('focus', draw);
  input.addEventListener('blur', () => setTimeout(() => list.classList.add('hidden'), 120));
  input.addEventListener('keydown', (e) => {
    if (e.key === 'ArrowDown') { sel = Math.min(sel + 1, items.length - 1); draw(); e.preventDefault(); }
    else if (e.key === 'ArrowUp') { sel = Math.max(sel - 1, 0); draw(); e.preventDefault(); }
    else if (e.key === 'Enter' && items[sel] && !list.classList.contains('hidden')) { e.preventDefault(); pick(items[sel]); }
    else if (e.key === 'Escape') list.classList.add('hidden');
  });
  return { el, input, redraw: draw };
}

function openUpdateModal(id) {
  const idea = S.iById[id];
  if (!idea) return;
  let outcome = null;
  modal((box, close) => {
    const btns = Object.entries(CONFIG.statuses).filter(([k]) => k !== 'open').map(([k, v]) =>
      h('button', { type: 'button', 'aria-pressed': 'false', title: v.help, onclick: () => { outcome = k; btns.forEach((b) => b.setAttribute('aria-pressed', b.dataset.k === k)); } }, `${v.glyph} ${v.label}`));
    btns.forEach((b, n) => { b.dataset.k = Object.keys(CONFIG.statuses).filter((k) => k !== 'open')[n]; });
    const well = h('textarea', { rows: 3, placeholder: 'What went well?' });
    const poor = h('textarea', { rows: 3, placeholder: 'What went poorly?' });
    const imp = h('textarea', { rows: 3, placeholder: 'What should be improved or done differently?' });
    const spawn = [];
    const spawnBox = h('div');
    const spawnIn = h('input', { type: 'text', placeholder: 'A new idea that came from this (press Enter to add)' });
    const drawSpawn = () => { clear(spawnBox).append(spawn.map((s, n) => h('div', { class: 'link-row' }, h('span', { style: { flex: 1 } }, '• ' + s), h('button', { class: 'icon-btn', onclick: () => { spawn.splice(n, 1); drawSpawn(); } }, '×')))); };
    spawnIn.addEventListener('keydown', (e) => { if (e.key === 'Enter') { e.preventDefault(); if (spawnIn.value.trim()) { spawn.push(spawnIn.value.trim()); spawnIn.value = ''; drawSpawn(); } } });
    const save = async () => {
      if (spawnIn.value.trim()) { spawn.push(spawnIn.value.trim()); spawnIn.value = ''; }
      if (!outcome) return toast('Pick how it went first.', true);
      const r = await attempt(() => api(`/api/ideas/${id}/update`, 'POST', { outcome, went_well: well.value, went_poorly: poor.value, improve: imp.value, spawn }));
      if (!r) return;
      close(); toast(`Update saved. +${r.points} pts${r.spawned.length ? ` · ${plural(r.spawned.length, 'new idea')} added` : ''}`);
      await reload();
    };
    box.append(h('h2', {}, CONFIG.labels.updateTitle),
      h('p', { class: 'muted' }, h('b', {}, idea.title)),
      h('label', { class: 'lbl' }, 'How did it go?'), h('div', { class: 'outcomes' }, btns),
      h('label', { class: 'lbl' }, 'Went well'), well,
      h('label', { class: 'lbl' }, 'Went poorly'), poor,
      h('label', { class: 'lbl' }, 'To improve'), imp,
      h('label', { class: 'lbl' }, 'Ideas that came out of this'), spawnIn, spawnBox,
      h('p', { class: 'muted small' }, 'New ideas join the same groups and are linked back to this one, so you can follow the lineage on the map.'),
      h('div', { class: 'row', style: { justifyContent: 'flex-end', marginTop: '12px' } },
        h('button', { class: 'btn', onclick: close }, 'Cancel'), h('button', { class: 'btn primary', onclick: save }, 'Save update')));
  });
}
