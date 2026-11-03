/* Group checkboxes: a picker (for binning an idea) and a filter bar (for map/timeline). */

function groupNode(gid, opts, depth = 0) {
  const g = S.gById[gid];
  const cb = h('input', { type: 'checkbox', checked: opts.checked(gid), onchange: (e) => opts.toggle(gid, e.target.checked) });
  const label = h('label', { class: 'gchk' + (depth === 0 ? ' top' : ''), style: { '--c': g.color } }, cb, h('span', { class: 'dot' }), g.name);
  if (opts.reg) opts.reg(gid, cb, label);
  const kids = S.kids[gid] || [];
  return h('div', { class: 'gblock' }, label, kids.length ? h('div', { class: 'kids' }, kids.map((k) => groupNode(k, opts, depth + 1))) : null);
}

/* Picker with an inline "+ New group". Returns {el, get(), set(ids)}. */
function groupPicker(initial, onChange) {
  let chosen = new Set(initial || []);
  const el = h('div');
  function draw() {
    clear(el);
    chosen = new Set([...chosen].filter((g) => S.gById[g]));
    // Groups above a ticked group are shown as included (dimmed) but are not stored.
    const boxes = new Map();
    const showImplied = () => {
      const implied = new Set();
      for (const g of chosen) { let p = S.gById[g] && S.gById[g].parent_id, n = 0; while (p && S.gById[p] && n++ < 20) { implied.add(p); p = S.gById[p].parent_id; } }
      for (const [gid, { cb, label }] of boxes) {
        const on = implied.has(gid) && !chosen.has(gid);
        label.classList.toggle('implied', on);
        label.title = on ? 'Included automatically, because a group inside it is ticked' : '';
        cb.checked = chosen.has(gid) || on; cb.disabled = on;
      }
    };
    const tree = h('div', { class: 'gtree' }, S.tops.map((t) => groupNode(t, {
      checked: (g) => chosen.has(g),
      reg: (gid, cb, label) => boxes.set(gid, { cb, label }),
      toggle: (g, on) => { on ? chosen.add(g) : chosen.delete(g); showImplied(); onChange && onChange([...chosen]); },
    })));
    setTimeout(showImplied, 0);
    const add = h('div', { class: 'add-group' });
    const showAdd = () => {
      clear(add);
      const name = h('input', { type: 'text', placeholder: 'New group name', 'aria-label': 'New group name', style: { maxWidth: '200px' } });
      const parent = h('select', { 'aria-label': 'Inside which group', style: { maxWidth: '200px', width: 'auto' } },
        h('option', { value: '' }, 'Top level'),
        S.data.groups.map((g) => h('option', { value: g.id }, groupPath(g.id))));
      const go = async () => {
        if (!name.value.trim()) return;
        const r = await attempt(() => api('/api/groups', 'POST', { name: name.value, parent_id: parent.value ? +parent.value : null }));
        if (!r) return;
        await refresh(); chosen.add(r.id); onChange && onChange([...chosen]); draw();
      };
      name.addEventListener('keydown', (e) => { if (e.key === 'Enter') { e.preventDefault(); go(); } });
      add.append(h('div', { class: 'row' }, name, parent, h('button', { class: 'btn', type: 'button', onclick: go }, 'Add'),
        h('button', { class: 'btn', type: 'button', onclick: draw }, 'Cancel')));
      name.focus();
    };
    add.append(h('button', { class: 'btn', type: 'button', onclick: showAdd }, '+ New group'));
    el.append(tree, add);
  }
  draw();
  return { el, get: () => [...chosen], set: (ids) => { chosen = new Set(ids); draw(); }, redraw: draw };
}

/* Filter bar shared by Map and Timeline. `onChange` fires after the shared filter changes. */
function groupFilterBar(onChange) {
  const el = h('div', { class: 'gtree' });
  function draw() {
    clear(el);
    const f = S.filter;
    const opts = {
      checked: (g) => !f.hiddenGroups.includes(g),
      toggle: (g, on) => {
        const ids = descendants(g);
        f.hiddenGroups = f.hiddenGroups.filter((x) => !ids.includes(x));
        if (!on) f.hiddenGroups.push(...ids);
        saveFilter(); draw(); onChange();
      },
    };
    for (const t of S.tops) el.append(groupNode(t, opts));
    const un = h('input', { type: 'checkbox', checked: !f.hideUngrouped, onchange: (e) => { f.hideUngrouped = !e.target.checked; saveFilter(); onChange(); } });
    el.append(h('div', { class: 'gblock' }, h('label', { class: 'gchk top', style: { '--c': '#8b8f9a' } }, un, h('span', { class: 'dot' }), 'Ungrouped')));
  }
  draw();
  return el;
}
