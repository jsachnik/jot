/* Settings: appearance, groups, AI, backup. */

const SettingsView = {
  render(root) { this.root = root; root.classList.remove('nopad'); this.refresh(); },
  refresh() {
    const page = h('div', { class: 'page' });
    page.append(h('h1', {}, 'Settings'), this.appearance(), this.groupsCard(), this.aiCard(), this.dataCard());
    clear(this.root).append(page);
  },

  appearance() {
    const mode = localStorage.getItem('jot.mode') || 'auto', pal = localStorage.getItem('jot.palette') || 'ocean';
    const modes = [['light', 'Light'], ['dark', 'Dark'], ['auto', 'Match my computer']];
    return h('section', { class: 'card', style: { marginBottom: '18px' } }, h('h2', {}, 'Appearance'),
      h('label', { class: 'lbl' }, 'Mode'),
      h('div', { class: 'row' }, modes.map(([k, l]) => h('button', { class: 'btn' + (mode === k ? ' primary' : ''), onclick: () => { setTheme(k, null); this.refresh(); } }, l))),
      h('label', { class: 'lbl' }, 'Colour theme'),
      h('div', { class: 'row' }, CONFIG.palettes.map(([k, l, c]) => h('button', { class: 'sw-pal', style: { background: c }, title: l, 'aria-label': l, 'aria-pressed': String(pal === k), onclick: () => { setTheme(null, k); this.refresh(); } }))),
      h('p', { class: 'muted small' }, 'Want your own colours? See "Make it yours" in the README.'));
  },

  groupsCard() {
    const card = h('section', { class: 'card', style: { marginBottom: '18px' } }, h('h2', {}, CONFIG.labels.groupWord),
      h('p', { class: 'muted small' }, 'Groups can sit inside other groups (like Work › Wildfire research). Ideas can belong to several.'));
    const row = (gid, depth) => {
      const g = S.gById[gid];
      const color = h('input', { type: 'color', value: g.color, 'aria-label': 'Colour for ' + g.name, onchange: async () => { await attempt(() => api(`/api/groups/${gid}`, 'PATCH', { color: color.value })); await refresh(); } });
      const name = h('input', { type: 'text', value: g.name, 'aria-label': 'Group name', onchange: async () => { await attempt(() => api(`/api/groups/${gid}`, 'PATCH', { name: name.value })); await refresh(); } });
      const bad = new Set(descendants(gid));
      const move = h('select', { 'aria-label': 'Move ' + g.name, style: { width: 'auto', maxWidth: '150px' }, onchange: async () => { await attempt(() => api(`/api/groups/${gid}`, 'PATCH', { parent_id: move.value ? +move.value : null })); await refresh(); this.refresh(); } },
        h('option', { value: '' }, 'Top level'), S.data.groups.filter((x) => !bad.has(x.id)).map((x) => h('option', { value: x.id, selected: x.id === g.parent_id }, groupPath(x.id))));
      const inside = new Set(descendants(gid));   // an idea counts for every group above the ones it's ticked in
      const n = S.data.ideas.filter((i) => i.groups.some((x) => inside.has(x))).length;
      return [h('div', { class: 'tree-edit', style: { paddingLeft: depth * 24 + 'px' } }, color, name, h('span', { class: 'muted small' }, plural(n, 'idea')), move,
        h('button', { class: 'btn', onclick: () => subGroup(gid) }, '+ Sub'),
        h('button', { class: 'btn danger', onclick: async () => { if (await confirmBox(`Delete the group “${g.name}”? Its ideas are kept but lose this group. Sub-groups move up one level.`)) { await attempt(() => api(`/api/groups/${gid}`, 'DELETE')); await refresh(); this.refresh(); } } }, 'Delete')),
        ...(S.kids[gid] || []).flatMap((k) => row(k, depth + 1))];
    };
    const subGroup = (parent) => modal((box, close) => {
      const name = h('input', { type: 'text', placeholder: 'Group name' });
      const go = async () => { if (!name.value.trim()) return; await attempt(() => api('/api/groups', 'POST', { name: name.value, parent_id: parent })); close(); await refresh(); this.refresh(); };
      name.addEventListener('keydown', (e) => e.key === 'Enter' && go());
      box.append(h('h2', {}, parent ? `New group inside “${S.gById[parent].name}”` : 'New top-level group'), name, h('div', { class: 'row', style: { marginTop: '12px', justifyContent: 'flex-end' } }, h('button', { class: 'btn', onclick: close }, 'Cancel'), h('button', { class: 'btn primary', onclick: go }, 'Add')));
    });
    S.tops.forEach((t) => card.append(...row(t, 0)));
    card.append(h('button', { class: 'btn', style: { marginTop: '10px' }, onclick: () => subGroup(null) }, '+ New top-level group'));
    return card;
  },

  aiCard() {
    const ai = S.data.ai, on = ai.configured && ai.enabled;
    const out = h('span', { class: 'small' });
    return h('section', { class: 'card', style: { marginBottom: '18px' } }, h('h2', {}, 'AI features'),
      h('p', {}, ai.configured ? h('span', {}, 'Connected to ', h('b', {}, ai.label), '.') : 'Running in offline mode. Everything works except AI-written questions, AI librarian answers, AI connections; Jot uses guided prompts and keyword matching instead.'),
      ai.configured ? h('label', { class: 'row' }, h('input', { type: 'checkbox', checked: ai.enabled, onchange: async (e) => { await attempt(() => api('/api/settings', 'POST', { use_ai: e.target.checked })); await refresh(); this.refresh(); } }), 'Use AI features') : null,
      ai.configured ? h('div', { class: 'row', style: { marginTop: '8px' } }, h('button', { class: 'btn', onclick: async () => { out.textContent = 'Testing…'; const r = await api('/api/llm/test', 'POST', {}); out.textContent = r.ok ? `✔ Working (${r.label})` : `✖ ${r.error}`; } }, 'Test connection'), out) : null,
      !ai.configured ? h('p', { class: 'muted small' }, 'To connect one: copy ".env.example" to ".env", set JOT_PROVIDER, restart Jot. Details in the README. ', ai.reason || '') : null);
  },

  dataCard() {
    const file = h('input', { type: 'file', accept: '.zip', class: 'sr', id: 'impfile', onchange: async () => {
      if (!file.files[0]) return;
      if (!(await confirmBox('Restoring replaces ALL current ideas with the backup. Continue?', 'Restore'))) return;
      const fd = new FormData(); fd.append('file', file.files[0]);
      if (await attempt(() => api('/api/import', 'POST', fd))) { toast('Backup restored.'); await refresh(); this.refresh(); }
    } });
    return h('section', { class: 'card' }, h('h2', {}, 'Your data'),
      h('p', { class: 'muted small' }, 'Everything lives in the jot_data folder next to the app. It never leaves your computer (except text sent to your AI provider, if you turn that on).'),
      h('div', { class: 'row' }, h('a', { class: 'btn', href: '/api/export', download: '' }, 'Download a backup'),
        h('label', { class: 'btn', for: 'impfile', style: { cursor: 'pointer' } }, 'Restore from backup'), file));
  },
};
