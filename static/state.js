/* App state: the data from the server, derived lookups, and the shared filter. */

const S = {
  data: { groups: [], ideas: [], links: [], suggested: [], points: 0, ai: {}, costs: {} },
  gById: {}, iById: {}, kids: {}, tops: [],
  selected: null,          // idea id shown in the sidebar
  highlight: new Set(),    // ids the librarian picked
  highlightLabel: '',
  view: null,              // the active view object {render, refresh, destroy}
  viewName: 'home',
  filter: loadFilter(),
};

function loadFilter() {
  const base = { hiddenGroups: [], hideUngrouped: false, hiddenStatuses: [], showSuggested: true, focusLineage: false, q: '' };
  try { return Object.assign(base, JSON.parse(localStorage.getItem('jot.filter') || '{}')); } catch (e) { return base; }
}
function saveFilter() { try { localStorage.setItem('jot.filter', JSON.stringify(S.filter)); } catch (e) { /* private mode */ } }

async function refresh() {
  S.data = await api('/api/all');
  S.gById = {}; S.iById = {}; S.kids = {};
  for (const g of S.data.groups) { S.gById[g.id] = g; }
  for (const g of S.data.groups) { const p = g.parent_id && S.gById[g.parent_id] ? g.parent_id : 0; (S.kids[p] = S.kids[p] || []).push(g.id); }
  S.tops = S.kids[0] || [];
  for (const i of S.data.ideas) S.iById[i.id] = i;
  if (S.selected && !S.iById[S.selected]) S.selected = null;
  $('#pts').textContent = `⭐ ${S.data.points} pts`;
  return S.data;
}

function descendants(gid) {
  const out = [gid];
  for (const k of S.kids[gid] || []) out.push(...descendants(k));
  return out;
}
function groupPath(gid) {
  const parts = []; let g = S.gById[gid], guard = 0;
  while (g && guard++ < 20) { parts.unshift(g.name); g = S.gById[g.parent_id]; }
  return parts.join(' › ');
}
/* an idea's colour is its deepest group's colour (first one if several) */
function groupDepth(gid) { let d = 0, g = S.gById[gid]; while (g && g.parent_id && d < 20) { d++; g = S.gById[g.parent_id]; } return d; }
function ideaColor(idea) {
  const gs = (idea.groups || []).filter((g) => S.gById[g]);
  if (!gs.length) return '#8b8f9a';
  gs.sort((a, b) => groupDepth(b) - groupDepth(a));
  return S.gById[gs[0]].color;
}
function ideaGroupColors(idea) { return (idea.groups || []).filter((g) => S.gById[g]).map((g) => S.gById[g].color); }

function ideaVisible(idea) {
  const f = S.filter;
  if (f.hiddenStatuses.includes(idea.status)) return false;
  const gs = (idea.groups || []).filter((g) => S.gById[g]);
  if (!gs.length) return !f.hideUngrouped;
  return gs.some((g) => !f.hiddenGroups.includes(g));
}

/* lineage = ancestors and descendants along 'spawned' links */
function lineageOf(id) {
  const out = new Set([id]);
  const walk = (start, dir) => {
    const stack = [start];
    while (stack.length) {
      const cur = stack.pop();
      for (const l of S.data.links) {
        if (l.kind !== 'spawned') continue;
        const next = dir === 'down' ? (l.source === cur ? l.target : null) : (l.target === cur ? l.source : null);
        if (next && !out.has(next)) { out.add(next); stack.push(next); }
      }
    }
  };
  walk(id, 'down'); walk(id, 'up');
  return out;
}

function setHighlight(ids, label) {
  S.highlight = new Set(ids || []);
  S.highlightLabel = label || '';
  if (S.view && S.view.refresh) S.view.refresh();
}

/* Re-fetch and let the current view and sidebar update. */
async function reload() {
  await refresh();
  if (S.view && S.view.refresh) S.view.refresh();
  if (S.selected && typeof sidebarRefresh === 'function') sidebarRefresh();
}
