/* Small helpers: DOM builder, API calls, toasts, modals, markdown. */

/* h('div', {class:'x', onclick: fn}, 'text', childNode, [more]) -> element. Text is never parsed as HTML. */
function h(tag, attrs, ...kids) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v == null || v === false) continue;
    if (k.startsWith('on') && typeof v === 'function') el.addEventListener(k.slice(2), v);
    else if (k === 'class') el.className = v;
    else if (k === 'style' && typeof v === 'object') {
      for (const [p, val] of Object.entries(v)) { if (p.startsWith('--')) el.style.setProperty(p, val); else el.style[p] = val; }
    }
    else if (k === 'value') el.value = v;
    else if (k === 'checked' || k === 'disabled' || k === 'selected') el[k] = !!v;
    else el.setAttribute(k, v === true ? '' : v);
  }
  (function add(list) {
    for (const k of list) {
      if (Array.isArray(k)) add(k);
      else if (k != null && k !== false) el.append(k.nodeType ? k : document.createTextNode(String(k)));
    }
  })(kids);
  return el;
}
/* Make el.append() accept arrays and skip null/false, like h() does. */
(function () {
  const native = Element.prototype.append;
  Element.prototype.append = function (...items) {
    return native.apply(this, items.flat(Infinity).filter((x) => x != null && x !== false));
  };
})();
const $ = (sel, root = document) => root.querySelector(sel);
function clear(el) { while (el.firstChild) el.removeChild(el.firstChild); return el; }
function debounce(fn, ms) { let t; return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); }; }

async function api(path, method = 'GET', body) {
  const opt = { method, headers: {} };
  if (body instanceof FormData) opt.body = body;
  else if (body !== undefined) { opt.headers['Content-Type'] = 'application/json'; opt.body = JSON.stringify(body); }
  let res;
  try { res = await fetch(path, opt); }
  catch (e) { throw new Error('Cannot reach Jot. Is the Jot window still running?'); }
  let data = {};
  try { data = await res.json(); } catch (e) { /* non-JSON */ }
  if (!res.ok || data.error) throw new Error(data.error || `Something went wrong (${res.status}).`);
  return data;
}

function toast(msg, isErr) {
  const t = h('div', { class: 'toast' + (isErr ? ' err' : '') }, msg);
  $('#toasts').append(t);
  setTimeout(() => t.remove(), isErr ? 5500 : 3000);
}
/* run an async action, toast any error */
async function attempt(fn) { try { return await fn(); } catch (e) { toast(e.message, true); return null; } }

function modal(build) {
  const bg = h('div', { class: 'modal-bg', onmousedown: (e) => { if (e.target === bg) close(); } });
  const box = h('div', { class: 'modal', role: 'dialog', 'aria-modal': 'true' });
  bg.append(box);
  const onKey = (e) => { if (e.key === 'Escape') close(); };
  function close() { document.removeEventListener('keydown', onKey); bg.remove(); }
  document.addEventListener('keydown', onKey);
  build(box, close);
  document.body.append(bg);
  const first = box.querySelector('[autofocus]') || box.querySelector('input,textarea,button');
  if (first) first.focus();
  return close;
}
function confirmBox(message, okLabel = 'Delete') {
  return new Promise((resolve) => {
    modal((box, close) => {
      box.append(h('p', {}, message), h('div', { class: 'row', style: { justifyContent: 'flex-end' } },
        h('button', { class: 'btn', onclick: () => { close(); resolve(false); } }, 'Cancel'),
        h('button', { class: 'btn danger', onclick: () => { close(); resolve(true); } }, okLabel)));
    });
  });
}

/* ---- dates ---- */
const parseTs = (s) => new Date(s);
function dayKey(s) { const d = parseTs(s); return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`; }
function dayLabel(s) {
  const d = parseTs(s), t = new Date(), y = new Date(Date.now() - 864e5);
  if (dayKey(s) === dayKey(t.toISOString())) return 'Today';
  if (dayKey(s) === dayKey(y.toISOString())) return 'Yesterday';
  return d.toLocaleDateString(undefined, { weekday: 'long', month: 'long', day: 'numeric', year: d.getFullYear() === t.getFullYear() ? undefined : 'numeric' });
}
const timeLabel = (s) => parseTs(s).toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit' });
const dateLabel = (s) => parseTs(s).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' });
const daysAgo = (s) => (Date.now() - parseTs(s).getTime()) / 864e5;

/* ---- tiny, safe markdown ---- */
function esc(s) { return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;'); }
function inlineMd(s) {
  s = esc(s);
  s = s.replace(/!\[([^\]]*)\]\((\/files\/[^)\s]+|https?:\/\/[^)\s]+)\)/g, '<img alt="$1" src="$2">');
  s = s.replace(/\[([^\]]+)\]\((https?:\/\/[^)\s]+|\/files\/[^)\s]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>');
  s = s.replace(/`([^`]+)`/g, '<code>$1</code>');
  s = s.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>').replace(/(^|[^*])\*([^*\n]+)\*/g, '$1<em>$2</em>');
  return s;
}
function renderMd(text) {
  const out = []; let list = null, code = null;
  const flush = () => { if (list) { out.push(`</${list}>`); list = null; } };
  for (const line of (text || '').split('\n')) {
    if (line.trim().startsWith('```')) {
      if (code === null) { flush(); code = []; } else { out.push('<pre>' + esc(code.join('\n')) + '</pre>'); code = null; }
      continue;
    }
    if (code !== null) { code.push(line); continue; }
    let m;
    if ((m = line.match(/^(#{1,3})\s+(.*)/))) { flush(); out.push(`<h${m[1].length + 1}>${inlineMd(m[2])}</h${m[1].length + 1}>`); }
    else if ((m = line.match(/^\s*[-*]\s+(.*)/))) { if (list !== 'ul') { flush(); out.push('<ul>'); list = 'ul'; } out.push(`<li>${inlineMd(m[1])}</li>`); }
    else if ((m = line.match(/^\s*\d+\.\s+(.*)/))) { if (list !== 'ol') { flush(); out.push('<ol>'); list = 'ol'; } out.push(`<li>${inlineMd(m[1])}</li>`); }
    else if ((m = line.match(/^>\s?(.*)/))) { flush(); out.push(`<blockquote>${inlineMd(m[1])}</blockquote>`); }
    else if (!line.trim()) { flush(); }
    else { flush(); out.push(`<p>${inlineMd(line)}</p>`); }
  }
  if (code !== null) out.push('<pre>' + esc(code.join('\n')) + '</pre>');
  flush();
  return out.join('');
}
function mdBox(text) { const d = h('div', { class: 'md' }); d.innerHTML = renderMd(text); return d; }

function plural(n, w) { return `${n} ${w}${n === 1 ? '' : 's'}`; }
