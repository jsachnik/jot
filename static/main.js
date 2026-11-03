/* Startup, tabs and theme. */

const VIEWS = { home: HomeView, map: MapView, timeline: TimelineView, stickers: StickersView, settings: SettingsView };

function setTheme(mode, palette) {
  if (mode) localStorage.setItem('jot.mode', mode);
  if (palette) localStorage.setItem('jot.palette', palette);
  let m = localStorage.getItem('jot.mode') || 'auto';
  if (m === 'auto') m = matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  document.documentElement.dataset.mode = m;
  document.documentElement.dataset.palette = localStorage.getItem('jot.palette') || 'ocean';
  window.dispatchEvent(new Event('jot-theme'));
}
matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => { if ((localStorage.getItem('jot.mode') || 'auto') === 'auto') setTheme(); });

function go(name) {
  if (S.view && S.view.destroy) S.view.destroy();
  S.viewName = name; S.view = VIEWS[name];
  try { localStorage.setItem('jot.tab', name); } catch (e) { /* ignore */ }
  [...$('#nav').children].forEach((b) => b.setAttribute('aria-current', b.dataset.view === name ? 'page' : 'false'));
  const root = $('#view'); clear(root);
  S.view.render(root);
  if (name === 'home' && HomeView.prefill) { HomeView.title.value = HomeView.prefill; HomeView.prefill = null; HomeView.title.focus(); }
}

async function start() {
  setTheme();
  document.title = CONFIG.appName;
  $('#appname').textContent = CONFIG.appName;
  $('#nav').append(CONFIG.tabs.map(([k, l]) => h('button', { 'data-view': k, onclick: () => go(k) }, l)));
  $('#libbtn').addEventListener('click', () => Librarian.toggle());
  Librarian.init();
  try { await refresh(); }
  catch (e) { $('#view').append(h('div', { class: 'empty' }, e.message)); return; }
  let tab = 'home';
  try { tab = localStorage.getItem('jot.tab') || 'home'; } catch (e) { /* ignore */ }
  go(VIEWS[tab] ? tab : 'home');
}
start();
