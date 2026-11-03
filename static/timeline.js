/* Timeline: everything you've done with your ideas, newest first. */

const TimelineView = {
  events: [],
  render(root) {
    this.root = root;
    root.classList.add('nopad');
    S.filter.hiddenEvents = S.filter.hiddenEvents || [];
    clear(root);
    this.gbar = h('div');
    const f = S.filter;
    const types = Object.entries(CONFIG.eventTypes).map(([k, [ic, verb]]) =>
      h('label', {}, h('input', { type: 'checkbox', checked: !f.hiddenEvents.includes(k), onchange: (e) => {
        f.hiddenEvents = f.hiddenEvents.filter((x) => x !== k); if (!e.target.checked) f.hiddenEvents.push(k); saveFilter(); this.paint(); } }), `${ic} ${verb.replace(/ (on|to)$/, '')}`));
    this.toolbar = h('div', { class: 'toolbar' }, this.gbar, h('div', { class: 'tools' }, types));
    this.body = h('div', { style: { flex: 1, overflow: 'auto' } });
    root.append(this.toolbar, this.body);
    this.refresh();
  },
  async refresh() {
    clear(this.gbar).append(groupFilterBar(() => this.paint()));
    try { this.events = await api('/api/events'); } catch (e) { toast(e.message, true); }
    this.paint();
  },
  select() { this.paint(); },
  paint() {
    const f = S.filter, hl = S.highlight;
    const evs = this.events.filter((e) => {
      if (f.hiddenEvents.includes(e.type)) return false;
      if (hl.size) return e.idea_id && hl.has(e.idea_id);
      if (e.idea_id) { const i = S.iById[e.idea_id]; return i && ideaVisible(i); }
      return true;
    });
    const page = h('div', { class: 'page' });
    if (hl.size) page.append(h('div', { class: 'hl-banner', style: { position: 'static', transform: 'none', display: 'inline-flex', marginBottom: '10px' } },
      `${S.highlightLabel || 'Librarian'}: ${plural(hl.size, 'idea')}`, h('button', { onclick: () => setHighlight([]) }, 'Clear')));

    // last 30 days of activity
    const days = []; for (let n = 29; n >= 0; n--) days.push(dayKey(new Date(Date.now() - n * 864e5).toISOString()));
    const count = Object.fromEntries(days.map((d) => [d, 0]));
    evs.forEach((e) => { const k = dayKey(e.created_at); if (k in count) count[k]++; });
    const max = Math.max(1, ...Object.values(count));
    page.append(h('div', { class: 'card' }, h('div', { class: 'row between' }, h('b', {}, 'Last 30 days'), h('span', { class: 'muted small' }, plural(evs.length, 'event') + ' shown')),
      h('div', { class: 'bars', 'aria-hidden': 'true' }, days.map((d) => h('i', { title: `${d}: ${count[d]}`, style: { height: Math.max(4, count[d] / max * 100) + '%' } })))));

    if (!evs.length) page.append(h('div', { class: 'empty' }, 'Nothing to show yet. Jot an idea, brainstorm or give an update and it will appear here.'));
    let day = '';
    for (const e of evs) {
      const k = dayKey(e.created_at);
      if (k !== day) { day = k; page.append(h('div', { class: 'tl-day' }, dayLabel(e.created_at))); }
      const [ic, verb] = CONFIG.eventTypes[e.type] || ['•', e.type];
      const idea = e.idea_id ? S.iById[e.idea_id] : null;
      let extra = '';
      if (e.type === 'update') extra = ' → ' + (CONFIG.statuses[e.detail] ? CONFIG.statuses[e.detail].label : e.detail);
      else if (e.type === 'brainstorm') extra = e.detail;
      else if (e.type === 'jot' && e.detail) extra = e.detail;
      page.append(h('div', { class: 'tl-item' + (idea && hl.has(idea.id) ? ' hl' : ''), tabindex: 0, role: idea ? 'button' : null,
        onclick: () => idea && openIdea(idea.id), onkeydown: (ev) => { if (ev.key === 'Enter' && idea) openIdea(idea.id); } },
        h('div', { class: 'tl-ic' }, ic),
        h('div', {}, h('div', {}, verb + ' ', idea ? h('b', {}, idea.title) : e.type === 'sticker' ? h('b', {}, e.detail) : ''),
          extra && e.type !== 'sticker' ? h('div', { class: 'muted small' }, extra) : null,
          idea ? h('div', { class: 'row', style: { gap: '4px', marginTop: '3px' } }, idea.groups.filter((g) => S.gById[g]).map((g) => h('span', { class: 'chip', style: { '--c': S.gById[g].color } }, h('span', { class: 'dot' }), S.gById[g].name))) : null),
        h('div', { class: 'tl-time' }, timeLabel(e.created_at))));
    }
    clear(this.body).append(page);
  },
};
