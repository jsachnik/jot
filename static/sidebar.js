/* The idea sidebar: notes, files, connections, results, brainstorming. */

const sb = { id: null, bsEl: null, bsPrev: null };
const sbEl = () => $('#sidebar');

function openIdea(id) {
  if (sb.id !== id) { sb.id = id; sb.bsEl = h('div'); sb.bsPrev = null; }
  S.selected = id;
  sbEl().classList.add('open');
  if (S.view && S.view.select) S.view.select();
  return sidebarRender();
}
function closeSidebar() {
  S.selected = null; sb.id = null;
  sbEl().classList.remove('open');
  if (S.view && S.view.select) S.view.select();
}
function sidebarRefresh() {
  const a = document.activeElement;
  if (a && sbEl().contains(a) && /^(TEXTAREA|INPUT)$/.test(a.tagName)) return; // never clobber typing
  return sidebarRender();
}

async function sidebarRender() {
  const id = sb.id;
  if (!id) return;
  const box = $('.inner', sbEl());
  let d;
  try { d = await api(`/api/ideas/${id}`); }
  catch (e) { closeSidebar(); toast(e.message, true); return; }
  if (sb.id !== id) return;
  const scroll = box.scrollTop;
  clear(box);
  const ai = S.data.ai.configured && S.data.ai.enabled;

  /* header */
  const title = h('input', { class: 'sb-title', type: 'text', value: d.title, 'aria-label': 'Idea title',
    onchange: async () => { if (title.value.trim()) { await attempt(() => api(`/api/ideas/${id}`, 'PATCH', { title: title.value })); await refresh(); S.view.refresh && S.view.refresh(); } } });
  const status = h('select', { 'aria-label': 'Status', style: { width: 'auto', padding: '3px 8px' },
    onchange: async () => { await attempt(() => api(`/api/ideas/${id}`, 'PATCH', { status: status.value })); await reload(); } },
    Object.entries(CONFIG.statuses).map(([k, v]) => h('option', { value: k, selected: k === d.status }, v.label)));
  box.append(
    h('div', { class: 'row between' },
      h('div', { class: 'row' }, status, h('span', { class: 'muted small' }, 'Jotted ' + dateLabel(d.created_at))),
      h('button', { class: 'icon-btn', onclick: closeSidebar, 'aria-label': 'Close details' }, '✕')),
    title,
    h('div', { class: 'row', style: { margin: '8px 0' } },
      h('button', { class: 'btn primary', onclick: () => brainstormStart(false) }, ai ? CONFIG.labels.brainstormAI : CONFIG.labels.brainstormOffline),
      h('button', { class: 'btn', onclick: () => openUpdateModal(id) }, CONFIG.labels.updateTitle)),
    sb.bsEl);

  /* groups */
  const gSec = h('div', { class: 'sec' });
  const showGroups = () => {
    clear(gSec).append(h('h3', {}, CONFIG.labels.groupWord, h('button', { class: 'btn', onclick: editGroups }, 'Edit')),
      h('div', { class: 'row' }, d.groups.length ? d.groups.filter((g) => S.gById[g]).map((g) => h('span', { class: 'chip', style: { '--c': S.gById[g].color } }, h('span', { class: 'dot' }), groupPath(g))) : h('span', { class: 'muted small' }, 'Not in any group yet')));
  };
  const editGroups = () => {
    const picker = groupPicker(d.groups, debounce(async (ids) => { d.groups = ids; await attempt(() => api(`/api/ideas/${id}`, 'PATCH', { group_ids: ids })); await refresh(); S.view.refresh && S.view.refresh(); }, 300));
    clear(gSec).append(h('h3', {}, CONFIG.labels.groupWord, h('button', { class: 'btn', onclick: () => { showGroups(); } }, 'Done')), picker.el);
  };
  showGroups();
  box.append(gSec);

  /* notes */
  const notes = h('textarea', { rows: 8, placeholder: 'Write whatever you like about this idea. You can use **bold**, # headings, - lists and ![images](...). Paste or drop an image to embed it.', 'aria-label': 'Notes' }, d.body);
  const preview = h('div', { class: 'hidden' });
  const save = debounce(async () => { await attempt(() => api(`/api/ideas/${id}`, 'PATCH', { body: notes.value })); await refresh(); }, 700);
  notes.addEventListener('input', save);
  notes.addEventListener('blur', () => { save(); });
  let previewing = false;
  const toggle = h('button', { class: 'btn', onclick: () => {
    previewing = !previewing;
    notes.classList.toggle('hidden', previewing); preview.classList.toggle('hidden', !previewing);
    if (previewing) { clear(preview).append(notes.value.trim() ? mdBox(notes.value) : h('p', { class: 'muted' }, 'Nothing written yet.')); }
    toggle.textContent = previewing ? 'Edit' : 'Preview';
  } }, 'Preview');
  const insertAtCursor = (text) => {
    const s = notes.selectionStart ?? notes.value.length;
    notes.value = notes.value.slice(0, s) + text + notes.value.slice(notes.selectionEnd ?? s);
    notes.dispatchEvent(new Event('input'));
  };
  const sendFiles = async (files, embed) => {
    for (const f of files) {
      const fd = new FormData(); fd.append('file', f, f.name || 'pasted-image.png');
      const r = await attempt(() => api(`/api/ideas/${id}/attachments`, 'POST', fd));
      if (r && embed && r.mime.startsWith('image/')) insertAtCursor(`\n![${r.name}](${r.url})\n`);
    }
    await reload();
  };
  notes.addEventListener('paste', (e) => {
    const imgs = [...(e.clipboardData?.files || [])].filter((f) => f.type.startsWith('image/'));
    if (imgs.length) { e.preventDefault(); sendFiles(imgs, true); }
  });
  box.append(h('div', { class: 'sec' }, h('h3', {}, 'Notes', toggle), notes, preview));

  /* files */
  const fileInput = h('input', { type: 'file', multiple: true, class: 'sr', id: 'fileinp', onchange: () => sendFiles([...fileInput.files], false) });
  const fSec = h('div', { class: 'sec', ondragover: (e) => { e.preventDefault(); fSec.classList.add('dropping'); }, ondragleave: () => fSec.classList.remove('dropping'),
    ondrop: (e) => { e.preventDefault(); fSec.classList.remove('dropping'); sendFiles([...e.dataTransfer.files], false); } },
    h('h3', {}, 'Files & images', h('label', { class: 'btn', for: 'fileinp', style: { cursor: 'pointer' } }, '+ Attach')), fileInput,
    d.attachments.length ? h('div', { class: 'files' }, d.attachments.map((a) => {
      const isImg = (a.mime || '').startsWith('image/');
      return h('div', { class: 'file' },
        isImg ? h('img', { src: '/files/' + a.stored, alt: a.name }) : null,
        h('a', { href: '/files/' + a.stored, target: '_blank', rel: 'noopener', title: a.name }, a.name.length > 20 ? a.name.slice(0, 18) + '…' : a.name),
        isImg ? h('div', {}, h('button', { class: 'btn', style: { padding: '1px 8px', marginTop: '4px' }, onclick: () => { if (previewing) toggle.click(); insertAtCursor(`\n![${a.name}](/files/${a.stored})\n`); } }, 'Insert in notes')) : null,
        h('button', { class: 'x', 'aria-label': 'Remove file', onclick: async () => { if (await confirmBox(`Remove ${a.name}?`, 'Remove')) { await attempt(() => api(`/api/attachments/${a.id}`, 'DELETE')); await reload(); } } }, '×'));
    })) : h('p', { class: 'muted small' }, 'Drop files here or click Attach.'));
  box.append(fSec);

  /* connections */
  box.append(connectionsSection(d, ai));

  /* results */
  if (d.updates.length) {
    box.append(h('div', { class: 'sec' }, h('h3', {}, 'How it went'), d.updates.map((u) => h('div', { class: 'upd ' + u.outcome },
      h('span', { class: 'st ' + u.outcome }, CONFIG.statuses[u.outcome].label), ' ', h('span', { class: 'muted small' }, dateLabel(u.created_at)),
      u.went_well ? h('p', { class: 'small' }, h('b', {}, 'Went well: '), u.went_well) : null,
      u.went_poorly ? h('p', { class: 'small' }, h('b', {}, 'Went poorly: '), u.went_poorly) : null,
      u.improve ? h('p', { class: 'small' }, h('b', {}, 'Improve: '), u.improve) : null))));
  }

  /* brainstorm log */
  if (d.brainstorm.length) {
    box.append(h('div', { class: 'sec' }, h('details', {}, h('summary', {}, `Brainstorm log (${d.brainstorm.length})`),
      d.brainstorm.map((b) => h('div', { class: 'upd' }, h('div', { class: 'small muted' }, b.question), h('div', {}, b.answer), h('div', { class: 'small pts-pop' }, `+${b.points} pts`))),
      h('button', { class: 'btn', onclick: () => { insertLog(d); } }, 'Copy log into notes'))));
  }

  box.append(h('div', { class: 'sec' }, h('button', { class: 'btn danger', onclick: async () => {
    if (await confirmBox(`Delete “${d.title}” and everything attached to it? This can't be undone.`)) {
      await attempt(() => api(`/api/ideas/${id}`, 'DELETE')); closeSidebar(); await reload();
    }
  } }, 'Delete this idea')));
  box.scrollTop = scroll;

  function insertLog(dd) {
    const text = '\n\n## Brainstorm\n' + dd.brainstorm.map((b) => `**${b.question}**\n${b.answer}`).join('\n\n');
    notes.value += text; notes.dispatchEvent(new Event('input')); toast('Added to notes.');
  }
}

/* ---- connections ---- */
function connectionsSection(d, ai) {
  const id = d.id;
  const sec = h('div', { class: 'sec' }, h('h3', {}, 'Connections'));
  const from = d.links.filter((l) => l.kind === 'spawned' && l.target === id);
  const to = d.links.filter((l) => l.kind === 'spawned' && l.source === id);
  const rel = d.links.filter((l) => l.kind === 'related');
  const rowFor = (l, tag) => h('div', { class: 'link-row' }, h('span', { class: 'muted small', style: { width: '78px' } }, tag),
    h('a', { onclick: () => openIdea(l.other_id) }, l.other_title), h('span', { class: 'st ' + l.other_status }, CONFIG.statuses[l.other_status].glyph),
    h('button', { class: 'icon-btn', title: 'Remove this connection', 'aria-label': 'Remove connection', onclick: async () => { await attempt(() => api(`/api/links/${l.id}`, 'DELETE')); await reload(); } }, '×'));
  from.forEach((l) => sec.append(rowFor(l, 'Came from')));
  to.forEach((l) => sec.append(rowFor(l, 'Led to')));
  rel.forEach((l) => sec.append(rowFor(l, 'Related')));
  if (!d.links.length) sec.append(h('p', { class: 'muted small' }, 'Not connected to other ideas yet.'));

  const linkedIds = new Set(d.links.map((l) => l.other_id));
  const combo = ideaCombo({ placeholder: 'Link to another idea…', filter: (i) => i.id !== id && !linkedIds.has(i.id),
    onPick: async (i) => { await attempt(() => api('/api/links', 'POST', { source: id, target: i.id, kind: 'related' })); await reload(); } });
  const sug = h('div');
  const run = async (mode) => {
    clear(sug).append(h('p', { class: 'muted small' }, mode === 'ai' ? 'Asking the AI…' : 'Looking…'));
    const r = await attempt(() => api(`/api/ideas/${id}/suggest?mode=${mode}`));
    clear(sug);
    if (!r) return;
    if (!r.suggestions.length) { sug.append(h('p', { class: 'muted small' }, 'Nothing obvious. Try different wording in your notes, or link one by hand.')); return; }
    r.suggestions.forEach((s) => sug.append(h('div', { class: 'link-row' },
      h('div', { style: { flex: 1 } }, h('a', { onclick: () => openIdea(s.id) }, s.title), h('div', { class: 'muted small' }, s.why)),
      h('button', { class: 'btn', onclick: async () => { await attempt(() => api('/api/links', 'POST', { source: id, target: s.id, kind: 'related', note: s.why })); await reload(); } }, 'Link'))));
  };
  sec.append(h('div', { style: { marginTop: '8px' } }, combo.el),
    h('div', { class: 'row', style: { margin: '8px 0' } },
      h('button', { class: 'btn', onclick: () => run('keywords') }, 'Suggest connections'),
      ai ? h('button', { class: 'btn', onclick: () => run('ai') }, 'Ask the AI') : null), sug);
  return sec;
}

/* ---- brainstorming ---- */
async function brainstormStart(fromNext) {
  const id = sb.id, box = sb.bsEl;
  clear(box).append(h('div', { class: 'bs' }, h('p', { class: 'muted' }, S.data.ai.configured && S.data.ai.enabled ? 'Thinking of a good question…' : 'Picking a question…')));
  const q = await attempt(() => api(`/api/ideas/${id}/brainstorm/next`, 'POST', { prev_id: sb.bsPrev }));
  if (!q) { clear(box); return; }
  if (q.bonus) toast(`Depth bonus on your last answer: +${q.bonus} pts`);
  if (q.notice) toast(q.notice, true);
  $('#pts').textContent = `⭐ ${q.total} pts`;
  const text = h('textarea', { rows: 3, placeholder: 'E. Something else, or say more… (more thought earns more points)', 'aria-label': 'Write your own answer' });
  const answer = async (choice) => {
    const r = await attempt(() => api(`/api/brainstorm/${q.id}/answer`, 'POST', { choice, text: text.value }));
    if (!r) return;
    sb.bsPrev = q.id;
    $('#pts').textContent = `⭐ ${r.total} pts`;
    clear(box).append(h('div', { class: 'bs' },
      h('p', {}, h('span', { class: 'pts-pop' }, `+${r.points} pts`), ' · ', r.note),
      h('div', { class: 'row' }, h('button', { class: 'btn primary', onclick: () => brainstormStart(true) }, 'Next question'),
        h('button', { class: 'btn', onclick: () => { clear(box); sb.bsPrev = null; } }, 'Done'))));
    await refresh(); sidebarRender();
  };
  const letters = 'ABCD';
  clear(box).append(h('div', { class: 'bs' },
    h('div', { class: 'q' }, q.question),
    q.options.map((o, i) => h('button', { class: 'opt', onclick: () => answer(i) }, h('b', {}, letters[i] + '.'), o)),
    text,
    h('div', { class: 'row', style: { marginTop: '8px' } },
      h('button', { class: 'btn primary', onclick: () => answer(4) }, 'Submit my answer'),
      h('button', { class: 'btn', onclick: () => { clear(box); sb.bsPrev = null; } }, 'Stop'),
      h('span', { class: 'muted small' }, q.source === 'ai' ? 'AI question' : 'Guided prompt'))));
  box.scrollIntoView({ block: 'nearest' });
}
