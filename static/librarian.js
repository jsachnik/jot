/* The librarian: ask whether an idea already exists, and see where. */

const Librarian = {
  history: [], open: false, busy: false,
  init() {
    const el = $('#librarian');
    this.body = h('div', { class: 'lib-body' });
    this.input = h('textarea', { rows: 2, placeholder: 'e.g. I have an idea about wildfire smoke and clouds. Do I already have something like it?', 'aria-label': 'Ask the librarian' });
    this.input.addEventListener('keydown', (e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); this.ask(); } });
    this.sendBtn = h('button', { class: 'btn primary', onclick: () => this.ask() }, 'Ask');
    el.append(
      h('div', { class: 'lib-head' }, h('div', {}, h('b', {}, 'Librarian'), h('div', { class: 'muted small', id: 'lib-mode' })),
        h('button', { class: 'icon-btn', onclick: () => this.toggle(false), 'aria-label': 'Close librarian' }, '✕')),
      this.body,
      h('div', { class: 'lib-form' }, this.input, h('div', { class: 'row between', style: { marginTop: '6px' } },
        h('span', { class: 'muted small' }, 'Enter to ask'), this.sendBtn)));
    this.intro();
  },
  intro() {
    clear(this.body).append(h('div', { class: 'msg bot' },
      "Hi! Describe an idea or ask me to find something. I'll tell you which of your Jots are related, what groups they're in, and whether it deserves a new Jot."),
      h('div', { class: 'row' }, ['Do I have any ideas about…', 'Which ideas have I tried that failed?', 'What are my open ideas?'].map((s) =>
        h('button', { class: 'chip', onclick: () => { this.input.value = s; this.input.focus(); } }, s))));
  },
  toggle(on) {
    this.open = on === undefined ? !this.open : on;
    $('#librarian').classList.toggle('open', this.open);
    $('#libbtn').classList.toggle('on', this.open);
    $('#libbtn').setAttribute('aria-expanded', this.open);
    $('#lib-mode').textContent = S.data.ai.configured && S.data.ai.enabled ? 'Using AI: ' + S.data.ai.label : 'Offline mode: searching by keywords';
    if (this.open) setTimeout(() => this.input.focus(), 200);
  },
  async ask() {
    const q = this.input.value.trim();
    if (!q || this.busy) return;
    this.busy = true; this.input.value = '';
    if (!this.history.length) clear(this.body);
    this.body.append(h('div', { class: 'msg user' }, q));
    const wait = h('div', { class: 'msg bot muted' }, 'Looking through your ideas…');
    this.body.append(wait); this.body.scrollTop = this.body.scrollHeight;
    const r = await attempt(() => api('/api/librarian', 'POST', { question: q, history: this.history }));
    wait.remove(); this.busy = false;
    if (!r) return;
    this.history.push({ role: 'user', text: q }, { role: 'bot', text: r.answer });
    const ids = r.matches.map((m) => m.id);
    const verdictText = { new: 'Looks new', covered: 'Already covered', extend: 'Could extend an existing idea', browse: 'Here is what I found' }[r.verdict];
    const msg = h('div', { class: 'msg bot' }, h('div', { class: 'verdict' }, verdictText), h('p', {}, r.answer),
      r.matches.map((m) => h('div', { class: 'match', tabindex: 0, onclick: () => openIdea(m.id), onkeydown: (e) => e.key === 'Enter' && openIdea(m.id) },
        h('div', {}, h('b', {}, m.title), ' ', h('span', { class: 'st ' + m.status }, CONFIG.statuses[m.status].label)),
        h('div', { class: 'muted small' }, m.groups.join(' · ') || 'ungrouped'),
        m.why ? h('div', { class: 'small' }, m.why) : null)),
      h('div', { class: 'row', style: { marginTop: '10px' } },
        ids.length ? h('button', { class: 'btn', onclick: () => { setHighlight(ids, 'Librarian'); go('map'); } }, 'Show on map') : null,
        ids.length ? h('button', { class: 'btn', onclick: () => { setHighlight(ids, 'Librarian'); go('timeline'); } }, 'Show in timeline') : null,
        r.verdict === 'new' || r.verdict === 'extend' ? h('button', { class: 'btn primary', onclick: () => { HomeView.prefill = q; go('home'); this.toggle(false); } }, 'Jot it as new') : null));
    this.body.append(msg);
    if (ids.length) setHighlight(ids, 'Librarian');
    this.body.scrollTop = this.body.scrollHeight;
  },
};
