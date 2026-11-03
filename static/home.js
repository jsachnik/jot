/* Home: Jot It Down, Give an Update, and what needs attention. */

const HomeView = {
  groups: [],   // remembered between jots
  render(root) {
    this.root = root;
    root.classList.remove('nopad');
    this.refresh();
  },
  refresh() {
    const root = this.root;
    // keep what the user is typing if a refresh happens mid-jot
    const keep = this.title ? { t: this.title.value, d: this.details.value, open: this.det && this.det.open } : null;
    clear(root);
    const page = h('div', { class: 'page' });
    root.append(page);

    /* Jot It Down */
    this.title = h('textarea', { class: 'title-input', rows: 2, placeholder: "What's the idea? (a few words is plenty)", 'aria-label': 'Your idea', maxlength: 300 });
    this.details = h('textarea', { rows: 4, placeholder: 'Anything else? (optional)', 'aria-label': 'Details' });
    this.det = h('details', {}, h('summary', {}, '+ Add details'), this.details);
    if (keep) { this.title.value = keep.t; this.details.value = keep.d; this.det.open = keep.open; }
    this.picker = groupPicker(this.groups, (ids) => { this.groups = ids; });
    const jot = async () => {
      const r = await attempt(() => api('/api/ideas', 'POST', { title: this.title.value, body: this.details.value, group_ids: this.picker.get() }));
      if (!r) return;
      this.title.value = ''; this.details.value = ''; this.det.open = false;
      toast(`Jotted! +${r.points} pts`);
      await reload();
      this.title.focus();
    };
    this.title.addEventListener('keydown', (e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); jot(); } });
    const jotCard = h('section', { class: 'card', 'aria-labelledby': 'jot-h' },
      h('h2', { id: 'jot-h' }, 'New idea'), this.title, this.det,
      h('label', { class: 'lbl' }, CONFIG.labels.groupWord + ' (check any that fit)'), this.picker.el,
      h('div', { class: 'row', style: { marginTop: '14px' } }, h('button', { class: 'btn primary big', onclick: jot }, CONFIG.labels.jotButton),
        h('span', { class: 'muted small' }, 'Enter to jot · Shift+Enter for a new line')));

    /* Give an Update */
    let filterIds = [];
    const filt = h('div', { class: 'hidden', style: { marginTop: '8px' } });
    const combo = ideaCombo({ placeholder: 'Search for the idea you tried…', groupIds: () => filterIds, filter: (i) => true, onPick: (i) => openUpdateModal(i.id) });
    const filtPicker = groupPicker([], (ids) => { filterIds = ids; combo.redraw(); });
    filt.append(h('p', { class: 'muted small' }, 'Only search inside these groups (leave empty to search everything):'), filtPicker.el);
    const filtBtn = h('button', { class: 'btn', onclick: () => { filt.classList.toggle('hidden'); } }, 'Filter by group');
    const open = S.data.ideas.filter((i) => i.status === 'open' && daysAgo(i.created_at) >= CONFIG.staleDays)
      .sort((a, b) => a.created_at.localeCompare(b.created_at)).slice(0, 4);
    const updCard = h('section', { class: 'card', 'aria-labelledby': 'upd-h' },
      h('h2', { id: 'upd-h' }, CONFIG.labels.updateTitle), h('p', { class: 'muted' }, CONFIG.labels.updateHint),
      combo.el, h('div', { style: { marginTop: '8px' } }, filtBtn), filt,
      open.length ? h('div', { style: { marginTop: '14px' } }, h('h3', {}, 'Still open for a while'),
        h('div', { class: 'idea-list' }, open.map((i) => h('button', { class: 'idea-row', onclick: () => openUpdateModal(i.id) },
          h('span', { class: 'dot', style: { '--c': ideaColor(i) } }), h('span', { class: 'item-title', style: { flex: 1 } }, i.title),
          h('span', { class: 'muted small' }, Math.round(daysAgo(i.created_at)) + 'd'))))) : null);

    page.append(h('div', { class: 'grid2' }, jotCard, updCard));

    /* recent */
    const recent = [...S.data.ideas].sort((a, b) => b.updated_at.localeCompare(a.updated_at)).slice(0, 8);
    const c = S.data.ideas.length, w = S.data.ideas.filter((i) => i.status === 'worked').length, o = S.data.ideas.filter((i) => i.status === 'open').length;
    page.append(h('section', { style: { marginTop: '26px' } },
      h('div', { class: 'row between' }, h('h2', {}, 'Recently touched'),
        h('span', { class: 'muted small' }, `${plural(c, 'idea')} · ${o} open · ${w} worked`)),
      recent.length ? h('div', { class: 'idea-list' }, recent.map((i) => h('button', { class: 'idea-row' + (S.highlight.has(i.id) ? ' hl' : ''), onclick: () => openIdea(i.id) },
        h('span', { class: 'dot', style: { '--c': ideaColor(i) } }),
        h('span', { style: { flex: 1 } }, h('span', { class: 'item-title' }, i.title),
          h('div', { class: 'row', style: { gap: '4px' } }, i.groups.filter((g) => S.gById[g]).map((g) => h('span', { class: 'chip', style: { '--c': S.gById[g].color } }, h('span', { class: 'dot' }), S.gById[g].name)))),
        h('span', { class: 'st ' + i.status }, CONFIG.statuses[i.status].label))))
        : h('div', { class: 'empty' }, 'Nothing here yet. Type an idea above and press ', h('b', {}, CONFIG.labels.jotButton), '.')));
  },
};
