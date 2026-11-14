/* Code Review Assistant – shared components and SVG diagram renderers.
   Vanilla JS, no dependencies, no build step. Inlined into every report.
   Every input may be missing, null or of the wrong type: all accessors are defensive. */
(function (global) {
  'use strict';

  var CRA = {};
  var SVGNS = 'http://www.w3.org/2000/svg';
  var uid = 0;

  /* ------------------------------------------------------------------ */
  /* safe accessors                                                     */
  /* ------------------------------------------------------------------ */
  var arr = function (x) { return Array.isArray(x) ? x : []; };
  var obj = function (x) { return x && typeof x === 'object' && !Array.isArray(x) ? x : {}; };
  var str = function (x) { return x == null ? '' : String(x); };
  var num = function (x, d) { var n = Number(x); return isFinite(n) ? n : (d === undefined ? 0 : d); };
  var strs = function (x) { return arr(x).filter(function (v) { return v != null && v !== ''; }).map(String); };
  CRA.arr = arr; CRA.obj = obj; CRA.str = str; CRA.num = num; CRA.strs = strs;
  CRA.clampPts = function (p) { var n = Math.round(num(p, 0)); return n < 0 ? 0 : n > 5 ? 5 : n; };
  CRA.fmt = function (n) { return num(n, 0).toLocaleString('en-US'); };
  CRA.plural = function (n, one, many) { return CRA.fmt(n) + ' ' + (num(n) === 1 ? one : (many || one + 's')); };

  var ESC = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' };
  CRA.esc = function (s) { return str(s).replace(/[&<>"']/g, function (c) { return ESC[c]; }); };

  /* ------------------------------------------------------------------ */
  /* DOM builder                                                        */
  /* ------------------------------------------------------------------ */
  function append(el, c) {
    if (c == null || c === false || c === true) return;
    if (Array.isArray(c)) { for (var i = 0; i < c.length; i++) append(el, c[i]); return; }
    el.appendChild(c instanceof Node ? c : document.createTextNode(String(c)));
  }
  function h(tag, attrs, children) {
    var el = document.createElement(tag);
    setAttrs(el, attrs);
    append(el, children);
    return el;
  }
  function setAttrs(el, attrs) {
    if (!attrs) return;
    Object.keys(attrs).forEach(function (k) {
      var v = attrs[k];
      if (v == null || v === false) return;
      if (k === 'class') el.setAttribute('class', v);
      else if (k === 'text') el.textContent = v;
      else if (k === 'html') el.innerHTML = v;
      else if (k === 'style' && typeof v === 'object') Object.keys(v).forEach(function (s) { el.style.setProperty(s, v[s]); });
      else if (k.slice(0, 2) === 'on' && typeof v === 'function') el.addEventListener(k.slice(2), v);
      else el.setAttribute(k, v === true ? '' : String(v));
    });
  }
  function s(tag, attrs, children) {
    var el = document.createElementNS(SVGNS, tag);
    setAttrs(el, attrs);
    append(el, children);
    return el;
  }
  CRA.h = h; CRA.s = s; CRA.append = append;
  CRA.$ = function (sel, root) { return (root || document).querySelector(sel); };
  CRA.$$ = function (sel, root) { return Array.prototype.slice.call((root || document).querySelectorAll(sel)); };

  /* ------------------------------------------------------------------ */
  /* enumerations                                                       */
  /* ------------------------------------------------------------------ */
  CRA.FAMILIES = [
    { id: 'logic', label: 'Logic', short: 'Logic' },
    { id: 'security_data', label: 'Security & Data', short: 'Sec & Data' },
    { id: 'contracts_integration', label: 'Contracts & Integration', short: 'Contracts' },
    { id: 'quality', label: 'Quality & Structure', short: 'Quality' }
  ];
  CRA.DIMENSIONS = [
    { id: 'core_logic', label: 'Core Logic', short: 'Logic', family: 'logic' },
    { id: 'error_handling', label: 'Error Handling', short: 'Errors', family: 'logic' },
    { id: 'concurrency', label: 'Concurrency & State', short: 'Concur', family: 'logic' },
    { id: 'security', label: 'Security', short: 'Security', family: 'security_data' },
    { id: 'data_integrity', label: 'Data Integrity', short: 'Data', family: 'security_data' },
    { id: 'contracts', label: 'Contracts', short: 'Contract', family: 'contracts_integration' },
    { id: 'integration', label: 'Integration', short: 'Integr', family: 'contracts_integration' },
    { id: 'config_infra', label: 'Configuration & Infrastructure', short: 'Config', family: 'contracts_integration' },
    { id: 'architecture', label: 'Architecture', short: 'Arch', family: 'quality' },
    { id: 'performance', label: 'Performance & Resources', short: 'Perf', family: 'quality' },
    { id: 'conventions', label: 'Convention Deviation', short: 'Conv', family: 'quality' },
    { id: 'tests', label: 'Tests & Verification', short: 'Tests', family: 'quality' }
  ];
  CRA.DIM = {};
  CRA.DIMENSIONS.forEach(function (d) { CRA.DIM[d.id] = d; });
  CRA.dimLabel = function (id) { return CRA.DIM[id] ? CRA.DIM[id].label : (str(id) || 'Unspecified'); };
  CRA.dimShort = function (id) { return CRA.DIM[id] ? CRA.DIM[id].short : (str(id) || '?'); };
  CRA.dimColor = function (id) { return CRA.DIM[id] ? 'var(--d-' + id + ')' : 'var(--text-3)'; };

  CRA.MODES = [
    { id: 'build+tests+static', key: 'static', label: 'Build + tests + static analysis', short: 'Build/tests/static',
      hint: 'Mechanical or trivial change: rely on the pipeline.' },
    { id: 'ai-review-only', key: 'ai', label: 'AI review only', short: 'AI review',
      hint: 'Standard change: an AI reviewer with the focus list below is enough.' },
    { id: 'ai+human-critical-paths', key: 'aih', label: 'AI + human on critical paths', short: 'AI + human',
      hint: 'A human reads the critical files and flows; AI reviews the rest.' },
    { id: 'human-only', key: 'human', label: 'Human review', short: 'Human only',
      hint: 'Critical security, data-integrity or core mechanisms affected broadly.' }
  ];
  CRA.mode = function (id) {
    for (var i = 0; i < CRA.MODES.length; i++) if (CRA.MODES[i].id === id) return CRA.MODES[i];
    return { id: str(id), key: 'unknown', label: id ? str(id) : 'Mode not determined', short: '?', hint: '' };
  };

  /* ------------------------------------------------------------------ */
  /* small visual atoms                                                 */
  /* ------------------------------------------------------------------ */
  CRA.splitPath = function (p) {
    p = str(p);
    var i = p.lastIndexOf('/');
    return i < 0 ? { dir: '', base: p } : { dir: p.slice(0, i + 1), base: p.slice(i + 1) };
  };
  CRA.basename = function (p) { return CRA.splitPath(p).base; };
  CRA.pathEl = function (p, extraClass) {
    var sp = CRA.splitPath(p);
    return h('span', { class: 'fpath' + (extraClass ? ' ' + extraClass : ''), 'data-tip': str(p) },
      [sp.dir ? h('span', { class: 'dir', text: sp.dir }) : null, h('span', { class: 'base', text: sp.base || '(unnamed)' })]);
  };
  CRA.pts = function (p, tip) {
    var n = CRA.clampPts(p);
    return h('span', { class: 'pts p' + n, 'data-tip': tip || (n + ' point' + (n === 1 ? '' : 's')) }, String(n));
  };
  CRA.critFlag = function (tip) { return h('span', { class: 'crit-flag', 'data-tip': tip || 'Critical finding on this file' }, 'Critical'); };
  CRA.conf = function (c) {
    var v = c === 'verified' ? 'verified' : 'inferred';
    var tip = v === 'verified' ? 'Verified: directly visible in the diff or code' :
      (c === 'inferred' ? 'Inferred: model reasoning, not directly visible' : 'Confidence not stated: treated as inferred');
    return h('span', { class: 'conf ' + v, 'data-tip': tip }, v);
  };
  CRA.dimChip = function (id, points) {
    var d = CRA.DIM[id];
    return h('span', { class: 'dchip', style: { '--dc': CRA.dimColor(id) },
      'data-tip': CRA.dimLabel(id) + (points != null ? ': max ' + CRA.clampPts(points) + ' pts' : '') },
      [h('span', { class: 'dot' }), d ? d.short : str(id), points != null ? CRA.pts(points, '') : null]);
  };
  var STATUS = { added: 'A', modified: 'M', deleted: 'D', renamed: 'R' };
  CRA.statusEl = function (st) {
    st = str(st);
    return h('span', { class: 'status s-' + (STATUS[st] ? st : 'unknown'), 'data-tip': st || 'status unknown' }, STATUS[st] || '?');
  };
  CRA.stTag = function (status, text) { return h('span', { class: 'st-tag ' + str(status) }, text || str(status)); };

  /* "path#heading-slug" → path › heading slug */
  CRA.parseRef = function (ref) {
    ref = str(ref).trim();
    var i = ref.indexOf('#');
    var path = i < 0 ? ref : ref.slice(0, i);
    var slug = i < 0 ? '' : ref.slice(i + 1);
    var section = slug.replace(/[-_]+/g, ' ').trim();
    return { path: path, section: section, raw: ref };
  };
  /* kinds: optional map path → 'spec' | 'plan' | ... */
  CRA.refEl = function (ref, kinds) {
    if (!ref) return null;
    var r = CRA.parseRef(ref);
    var kind = kinds && r.path ? kinds[r.path] : null;
    return h('span', { class: 'ref', 'data-tip': r.raw },
      [kind ? h('span', { class: 'rk' }, kind) : null,
       r.path ? h('span', { class: 'rp' }, CRA.basename(r.path)) : null,
       r.path && r.section ? h('span', null, '›') : null,
       r.section ? h('span', { class: 'rs' }, r.section) : null]);
  };
  CRA.refsEl = function (refs, kinds) {
    var list = strs(refs);
    if (!list.length) return null;
    return h('span', { class: 'refs' },
      list.map(function (r) { return CRA.refEl(r, kinds); }));
  };

  /* ------------------------------------------------------------------ */
  /* clipboard, toast, tooltip, theme                                   */
  /* ------------------------------------------------------------------ */
  CRA.toast = function (msg) {
    var t = document.getElementById('cra-toast');
    if (!t) { t = h('div', { id: 'cra-toast', role: 'status' }); document.body.appendChild(t); }
    t.textContent = msg; t.classList.add('on');
    clearTimeout(t._t); t._t = setTimeout(function () { t.classList.remove('on'); }, 1400);
  };
  function fallbackCopy(text) {
    var ta = h('textarea', { style: { position: 'fixed', top: '-1000px', opacity: '0' } });
    ta.value = text; document.body.appendChild(ta); ta.select();
    var ok = false;
    try { ok = document.execCommand('copy'); } catch (e) { ok = false; }
    document.body.removeChild(ta);
    return ok;
  }
  CRA.copy = function (text) {
    text = str(text);
    var done = function (ok) { CRA.toast(ok ? 'Copied to clipboard' : 'Copy failed: select the text manually'); };
    try {
      if (navigator.clipboard && navigator.clipboard.writeText && global.isSecureContext !== false) {
        navigator.clipboard.writeText(text).then(function () { done(true); }, function () { done(fallbackCopy(text)); });
        return;
      }
    } catch (e) { /* fall through */ }
    done(fallbackCopy(text));
  };
  CRA.copyBtn = function (getText, label) {
    return h('button', { class: 'btn sm copy', type: 'button', 'data-tip': 'Copy to clipboard',
      onclick: function (e) { e.stopPropagation(); CRA.copy(typeof getText === 'function' ? getText() : getText); } }, label || 'Copy');
  };

  CRA.initTooltip = function () {
    var tip = h('div', { id: 'cra-tip', role: 'tooltip' });
    document.body.appendChild(tip);
    var cur = null;
    function place(e) {
      var pad = 12, w = tip.offsetWidth, ht = tip.offsetHeight;
      var x = e.clientX + pad, y = e.clientY + pad;
      if (x + w > window.innerWidth - 4) x = Math.max(4, e.clientX - w - pad);
      if (y + ht > window.innerHeight - 4) y = Math.max(4, e.clientY - ht - pad);
      tip.style.left = x + 'px'; tip.style.top = y + 'px';
    }
    document.addEventListener('mouseover', function (e) {
      var t = e.target && e.target.closest ? e.target.closest('[data-tip]') : null;
      if (t === cur) return;
      cur = t;
      if (!t || !t.getAttribute('data-tip')) { tip.classList.remove('on'); return; }
      tip.textContent = t.getAttribute('data-tip');
      tip.classList.add('on'); place(e);
    });
    document.addEventListener('mousemove', function (e) { if (cur) place(e); });
    document.addEventListener('scroll', function () { tip.classList.remove('on'); cur = null; }, true);
  };

  CRA.themeToggle = function () {
    var root = document.documentElement;
    var order = ['auto', 'light', 'dark'];
    var stored = null;
    try { stored = localStorage.getItem('cra-theme'); } catch (e) { stored = null; }
    var cur = order.indexOf(stored) >= 0 ? stored : 'auto';
    var btn = h('button', { class: 'btn', type: 'button', 'data-tip': 'Theme: auto follows the OS setting' });
    function apply() {
      if (cur === 'auto') root.removeAttribute('data-theme'); else root.setAttribute('data-theme', cur);
      btn.textContent = (cur === 'auto' ? '◐ Auto' : cur === 'light' ? '○ Light' : '● Dark');
      try { localStorage.setItem('cra-theme', cur); } catch (e) { /* storage unavailable */ }
      document.dispatchEvent(new CustomEvent('cra-theme'));
    }
    btn.addEventListener('click', function () { cur = order[(order.indexOf(cur) + 1) % order.length]; apply(); });
    apply();
    return btn;
  };

  CRA.readJson = function (id) {
    var el = document.getElementById(id);
    if (!el) return null;
    try { return JSON.parse(el.textContent || 'null'); } catch (e) { return { __error: e.message }; }
  };
  CRA.fatal = function (root, msg) {
    root.innerHTML = '';
    root.appendChild(h('div', { class: 'err-box' }, [h('strong', null, 'Report could not be rendered. '), msg]));
  };

  /* ------------------------------------------------------------------ */
  /* ranking                                                            */
  /* ------------------------------------------------------------------ */
  CRA.rankCompare = function (a, b) {
    if (a.rank != null && b.rank != null) return a.rank - b.rank;
    var ca = a.critical ? 1 : 0, cb = b.critical ? 1 : 0;
    if (ca !== cb) return cb - ca;
    var sa = a.severity != null ? a.severity : 0, sb = b.severity != null ? b.severity : 0;
    if (sa !== sb) return sb - sa;
    if (a.score !== b.score) return b.score - a.score;
    if (a.size !== b.size) return b.size - a.size;
    return a.path < b.path ? -1 : a.path > b.path ? 1 : 0;
  };

  /* ------------------------------------------------------------------ */
  /* text measuring for SVG                                             */
  /* ------------------------------------------------------------------ */
  var ctx = null;
  CRA.textW = function (text, size, weight) {
    text = str(text);
    if (!ctx) { try { ctx = document.createElement('canvas').getContext('2d'); } catch (e) { ctx = null; } }
    if (!ctx) return text.length * (size || 12) * 0.58;
    ctx.font = (weight || 400) + ' ' + (size || 12) + 'px system-ui, -apple-system, "Segoe UI", Roboto, Arial, sans-serif';
    return ctx.measureText(text).width;
  };
  CRA.fit = function (text, maxW, size, weight) {
    text = str(text);
    if (CRA.textW(text, size, weight) <= maxW) return text;
    var lo = 0, hi = text.length;
    while (lo < hi) {
      var mid = (lo + hi + 1) >> 1;
      if (CRA.textW(text.slice(0, mid) + '…', size, weight) <= maxW) lo = mid; else hi = mid - 1;
    }
    return lo > 0 ? text.slice(0, lo) + '…' : '…';
  };
  /* word wrap into at most maxLines lines; the last line is ellipsised */
  CRA.wrap = function (text, maxW, size, weight, maxLines) {
    var words = str(text).split(/\s+/).filter(Boolean);
    var lines = [], line = '';
    maxLines = maxLines || 2;
    for (var i = 0; i < words.length; i++) {
      var test = line ? line + ' ' + words[i] : words[i];
      if (CRA.textW(test, size, weight) <= maxW || !line) { line = test; continue; }
      lines.push(line); line = words[i];
      if (lines.length === maxLines - 1) { line = words.slice(i).join(' '); break; }
    }
    if (line) lines.push(line);
    return lines.map(function (l) { return CRA.fit(l, maxW, size, weight); });
  };
  function textLines(lines, x, y, lh, attrs) {
    var t = s('text', Object.assign({ x: x, y: y }, attrs || {}));
    lines.forEach(function (l, i) { t.appendChild(s('tspan', { x: x, dy: i === 0 ? 0 : lh }, l)); });
    return t;
  }

  function arrowDefs(svg) {
    var id = 'cra-a' + (++uid);
    var defs = s('defs');
    ['', 'chg', 'new', 'modified', 'existing', 'removed'].forEach(function (k) {
      defs.appendChild(s('marker', { id: id + k, viewBox: '0 0 10 10', refX: 9, refY: 5, markerWidth: 7, markerHeight: 7, orient: 'auto-start-reverse' },
        s('path', { d: 'M0,0 L10,5 L0,10 z', class: 'arrow ' + k })));
    });
    svg.appendChild(defs);
    return function (k) { return 'url(#' + id + (k || '') + ')'; };
  }
  function svgRoot(w, ht, cls) {
    return s('svg', { class: 'dg ' + (cls || ''), width: Math.ceil(w), height: Math.ceil(ht), viewBox: '0 0 ' + Math.ceil(w) + ' ' + Math.ceil(ht),
      role: 'img' });
  }
  function bez(x1, y1, x2, y2, horizontal) {
    if (horizontal) {
      var dx = Math.max(30, Math.abs(x2 - x1) * 0.45) * (x2 >= x1 ? 1 : -1);
      return 'M' + x1 + ',' + y1 + ' C' + (x1 + dx) + ',' + y1 + ' ' + (x2 - dx) + ',' + y2 + ' ' + x2 + ',' + y2;
    }
    var dy = Math.max(20, Math.abs(y2 - y1) * 0.5);
    return 'M' + x1 + ',' + y1 + ' C' + x1 + ',' + (y1 + dy) + ' ' + x2 + ',' + (y2 - dy) + ' ' + x2 + ',' + y2;
  }

  /* ------------------------------------------------------------------ */
  /* interaction diagram: called_by → file → calls, contracts below     */
  /* ------------------------------------------------------------------ */
  function contractKind(label) {
    var l = label.toLowerCase();
    if (/^(table|db|sql|column|view|schema|migration|index)\b/.test(l)) return 'db';
    if (/^(kafka|event|topic|queue|amqp|rabbit|sns|sqs|bus|message|servicebus)\b/.test(l)) return 'event';
    if (/^(rest|http|https|get|post|put|patch|delete|api|grpc|graphql|endpoint|route)\b/.test(l)) return 'api';
    if (/^(config|property|properties|env|setting|appsettings|yaml|feature)\b/.test(l)) return 'config';
    return 'other';
  }
  function shapePath(kind, x, y, w, ht) {
    var r = 6;
    if (kind === 'db') {
      var e = 5;
      return 'M' + x + ',' + (y + e) + ' a' + (w / 2) + ',' + e + ' 0 0 1 ' + w + ',0 v' + (ht - 2 * e) +
        ' a' + (w / 2) + ',' + e + ' 0 0 1 ' + (-w) + ',0 z M' + x + ',' + (y + e) + ' a' + (w / 2) + ',' + e + ' 0 0 0 ' + w + ',0';
    }
    if (kind === 'event') {
      var n = 9;
      return 'M' + x + ',' + y + ' h' + (w - n) + ' l' + n + ',' + (ht / 2) + ' l' + (-n) + ',' + (ht / 2) + ' h' + (-(w - n)) + ' l' + n + ',' + (-ht / 2) + ' z';
    }
    if (kind === 'api') {
      var rr = ht / 2;
      return 'M' + (x + rr) + ',' + y + ' h' + (w - 2 * rr) + ' a' + rr + ',' + rr + ' 0 0 1 0,' + ht + ' h' + (-(w - 2 * rr)) + ' a' + rr + ',' + rr + ' 0 0 1 0,' + (-ht) + ' z';
    }
    if (kind === 'config') {
      return 'M' + x + ',' + y + ' h' + w + ' v' + ht + ' h' + (-w) + ' z';
    }
    return 'M' + (x + r) + ',' + y + ' h' + (w - 2 * r) + ' q' + r + ',0 ' + r + ',' + r + ' v' + (ht - 2 * r) + ' q0,' + r + ' ' + (-r) + ',' + r +
      ' h' + (-(w - 2 * r)) + ' q' + (-r) + ',0 ' + (-r) + ',' + (-r) + ' v' + (-(ht - 2 * r)) + ' q0,' + (-r) + ' ' + r + ',' + (-r) + ' z';
  }
  var KIND_LABEL = { db: 'data', event: 'event', api: 'API', config: 'config', other: 'contract' };

  /* interactions: {called_by, calls, contracts, changed_edges}
     opts: {center, centerTip, fanIn, fanInFiles, max} */
  CRA.renderInteraction = function (interactions, opts) {
    opts = opts || {};
    var it = obj(interactions);
    var max = opts.max || 6;
    var changed = {};
    strs(it.changed_edges).forEach(function (c) { changed[c.trim().toLowerCase()] = true; });
    var isChg = function (l) { return !!changed[str(l).trim().toLowerCase()]; };
    var fanFiles = strs(opts.fanInFiles);
    var callers = strs(it.called_by), callersFromFanIn = false;
    if (!callers.length && fanFiles.length) {
      callers = fanFiles.map(function (p) { return CRA.basename(p).replace(/\.[^.]+$/, ''); });
      callersFromFanIn = true;
    }
    var calls = strs(it.calls), contracts = strs(it.contracts);

    var NW = 168, NH = 26, VG = 8, GAP = 76, CW = 210, FS = 11.5;
    var leftShown = callers.slice(0, max);
    var leftMore = 0;
    var knownTotal = Math.max(callers.length, fanFiles.length);
    if (knownTotal > leftShown.length) leftMore = knownTotal - leftShown.length;
    var rightShown = calls.slice(0, max), rightMore = Math.max(0, calls.length - rightShown.length);
    var nL = leftShown.length + (leftMore ? 1 : 0), nR = rightShown.length + (rightMore ? 1 : 0);
    var colH = function (n) { return n ? n * NH + (n - 1) * VG : 0; };
    var topPad = 22;
    var bodyH = Math.max(colH(nL), colH(nR), 56);
    var xL = 0, xC = NW + GAP, xR = xC + CW + GAP, W = xR + NW;
    var cH = 56, cY = topPad + (bodyH - cH) / 2;

    // contracts layout: rows under the center, wrapping
    var cNodes = [], rowW = W, cx = 0, cy = topPad + bodyH + 46, rows = 0;
    var cw = contracts.map(function (c) { return Math.min(200, Math.max(90, CRA.textW(c, FS) + 30)); });
    var rowsArr = [], cur = [], curW = 0;
    contracts.forEach(function (c, i) {
      if (cur.length && curW + cw[i] + 12 > rowW) { rowsArr.push({ items: cur, w: curW }); cur = []; curW = 0; }
      cur.push(i); curW += (cur.length > 1 ? 12 : 0) + cw[i];
    });
    if (cur.length) rowsArr.push({ items: cur, w: curW });
    rowsArr.forEach(function (row, ri) {
      cx = (W - row.w) / 2;
      row.items.forEach(function (i) {
        cNodes.push({ label: contracts[i], x: cx, y: cy + ri * (NH + 22), w: cw[i] });
        cx += cw[i] + 12;
      });
      rows++;
    });
    var H = (rows ? cy + rows * (NH + 22) - 14 : topPad + bodyH + 8);

    var svg = svgRoot(W, H, 'interaction');
    var mk = arrowDefs(svg);
    svg.appendChild(s('text', { x: xL, y: 12, class: 'col-h' }, callersFromFanIn ? 'Referenced by (fan-in)' : 'Called by'));
    svg.appendChild(s('text', { x: xR, y: 12, class: 'col-h' }, 'Calls'));
    var edges = s('g'), nodes = s('g');
    svg.appendChild(edges); svg.appendChild(nodes);

    function box(x, y, w, label, cls, tip, kind) {
      var g = s('g', { class: 'node ' + (cls || ''), 'data-tip': tip || label });
      if (kind && kind !== 'other') g.appendChild(s('path', { class: 'shape', d: shapePath(kind, x, y, w, NH) }));
      else g.appendChild(s('rect', { x: x, y: y, width: w, height: NH, rx: 5 }));
      g.appendChild(s('text', { x: x + w / 2, y: y + NH / 2 + 4, 'text-anchor': 'middle', 'font-size': FS }, CRA.fit(label, w - 16, FS)));
      nodes.appendChild(g);
    }
    function edge(d, chg) {
      edges.appendChild(s('path', { d: d, class: 'edge' + (chg ? ' chg' : ''), 'marker-end': mk(chg ? 'chg' : '') }));
    }
    var startY = function (n) { return topPad + (bodyH - colH(n)) / 2; };

    var ly = startY(nL);
    leftShown.forEach(function (l, i) {
      var y = ly + i * (NH + VG), chg = isChg(l);
      box(xL, y, NW, l, chg ? 'chg' : '', l + (chg ? '\n(changed edge)' : ''));
      edge(bez(xL + NW, y + NH / 2, xC - 2, cY + cH / 2, true), chg);
    });
    if (leftMore) {
      var my = ly + leftShown.length * (NH + VG);
      var tip = fanFiles.length ? 'Referenced by ' + fanFiles.length + ' files:\n' + fanFiles.slice(0, 25).join('\n') + (fanFiles.length > 25 ? '\n…' : '') : '';
      box(xL, my, NW, '+' + leftMore + ' more', 'more', tip);
      edges.appendChild(s('path', { d: bez(xL + NW, my + NH / 2, xC - 2, cY + cH / 2, true), class: 'edge', 'stroke-dasharray': '3 3' }));
    }
    var ry = startY(nR);
    rightShown.forEach(function (l, i) {
      var y = ry + i * (NH + VG), chg = isChg(l);
      box(xR, y, NW, l, chg ? 'chg' : '', l + (chg ? '\n(changed edge)' : ''));
      edge(bez(xC + CW, cY + cH / 2, xR - 2, y + NH / 2, true), chg);
    });
    if (rightMore) box(xR, ry + rightShown.length * (NH + VG), NW, '+' + rightMore + ' more', 'more', calls.slice(max).join('\n'));

    cNodes.forEach(function (c) {
      var chg = isChg(c.label), kind = contractKind(c.label);
      box(c.x, c.y, c.w, c.label, chg ? 'chg' : '', c.label + '\n' + KIND_LABEL[kind] + (chg ? ' · changed edge' : ''), kind);
      edge(bez(xC + CW / 2, cY + cH, c.x + c.w / 2, c.y - 2, false), chg);
    });
    if (cNodes.length) svg.appendChild(s('text', { x: xL, y: cNodes[0].y - 12, class: 'col-h' }, 'Contracts · events · tables'));

    // center node
    var g = s('g', { class: 'node center', 'data-tip': opts.centerTip || opts.center || '' });
    g.appendChild(s('rect', { x: xC, y: cY, width: CW, height: cH, rx: 7 }));
    var lines = CRA.wrap(opts.center || 'this file', CW - 20, 12.5, 650, 2);
    g.appendChild(textLines(lines, xC + CW / 2, cY + (lines.length > 1 ? 22 : 30), 15, { 'text-anchor': 'middle', 'font-size': 12.5 }));
    nodes.appendChild(g);
    if (opts.fanIn != null && num(opts.fanIn, -1) >= 0) {
      var ft = 'fan-in ' + CRA.fmt(opts.fanIn), fw = CRA.textW(ft, 10.5, 700) + 14;
      var fg = s('g', { 'data-tip': 'Number of files referencing the changed symbols' });
      fg.appendChild(s('rect', { x: xC + CW / 2 - fw / 2, y: cY + cH - 9, width: fw, height: 18, rx: 9, class: 'fanin' }));
      fg.appendChild(s('text', { x: xC + CW / 2, y: cY + cH + 4, 'text-anchor': 'middle', class: 'fanin-t' }, ft));
      nodes.appendChild(fg);
    }
    if (!nL && !nR && !cNodes.length) {
      svg.appendChild(s('text', { x: W / 2, y: cY + cH + 26, class: 't3', 'text-anchor': 'middle' }, 'No interaction data for this file'));
      svg.setAttribute('height', cY + cH + 36);
      svg.setAttribute('viewBox', '0 0 ' + W + ' ' + (cY + cH + 36));
    }
    return svg;
  };

  /* ------------------------------------------------------------------ */
  /* component / dependency diagram                                     */
  /* ------------------------------------------------------------------ */
  CRA.LAYERS = ['api', 'application', 'domain', 'data', 'messaging', 'external'];
  var LAYER_LABEL = { api: 'API', application: 'Application', domain: 'Domain', data: 'Data', messaging: 'Messaging', external: 'External', other: 'Other' };
  var STATUS_TAG = { new: 'NEW', modified: 'MOD', removed: 'DEL' };
  CRA.diagramLegend = function (withChanged) {
    return h('div', { class: 'legend' }, [
      h('span', { class: 'li' }, [h('span', { class: 'sw new' }), 'new']),
      h('span', { class: 'li' }, [h('span', { class: 'sw modified' }), 'modified']),
      h('span', { class: 'li' }, [h('span', { class: 'sw existing' }), 'existing (unchanged)']),
      withChanged ? h('span', { class: 'li' }, [h('span', { class: 'ln-sw' }), 'changed edge']) : null
    ]);
  };

  /* graph: {nodes:[{id,label,layer?,status}], edges:[{from,to,label,status}]}
     opts: {byLayer: true|false|'auto'} */
  CRA.renderComponentDiagram = function (graph, opts) {
    opts = opts || {};
    graph = obj(graph);
    var nodes = [], byId = {};
    arr(graph.nodes).forEach(function (n) {
      n = obj(n);
      var id = str(n.id || n.label);
      if (!id || byId[id]) return;
      var node = { id: id, label: str(n.label || n.id), layer: str(n.layer), status: str(n.status) || 'existing', tip: str(n.description || '') };
      byId[id] = node; nodes.push(node);
    });
    var edges = [];
    arr(graph.edges).forEach(function (e) {
      e = obj(e);
      var f = str(e.from), t = str(e.to);
      if (!f || !t) return;
      [f, t].forEach(function (id) {
        if (!byId[id]) { var nn = { id: id, label: id, layer: '', status: 'existing', implicit: true }; byId[id] = nn; nodes.push(nn); }
      });
      edges.push({ from: f, to: t, label: str(e.label), status: str(e.status) || 'existing' });
    });
    if (!nodes.length) return null;

    // column assignment
    var useLayers = opts.byLayer === false ? false : nodes.some(function (n) { return CRA.LAYERS.indexOf(n.layer) >= 0; });
    var cols = [], colKeys = [];
    if (useLayers) {
      var present = CRA.LAYERS.filter(function (l) { return nodes.some(function (n) { return n.layer === l; }); });
      if (nodes.some(function (n) { return CRA.LAYERS.indexOf(n.layer) < 0; })) present.push('other');
      colKeys = present;
      nodes.forEach(function (n) { n.col = present.indexOf(CRA.LAYERS.indexOf(n.layer) >= 0 ? n.layer : 'other'); });
    } else {
      nodes.forEach(function (n) { n.col = 0; });
      for (var iter = 0; iter < nodes.length; iter++) {
        var moved = false;
        edges.forEach(function (e) {
          if (e.from === e.to) return;
          var a = byId[e.from], b = byId[e.to];
          if (b.col < a.col + 1 && a.col + 1 < nodes.length) { b.col = a.col + 1; moved = true; }
        });
        if (!moved) break;
      }
      var maxCol = 0; nodes.forEach(function (n) { maxCol = Math.max(maxCol, n.col); });
      for (var c = 0; c <= maxCol; c++) colKeys.push(null);
    }
    colKeys.forEach(function () { cols.push([]); });
    nodes.forEach(function (n) { cols[n.col].push(n); });
    // drop empty columns (auto layering can leave gaps)
    var kept = [], keptKeys = [];
    cols.forEach(function (c, i) { if (c.length) { kept.push(c); keptKeys.push(colKeys[i]); } });
    cols = kept; colKeys = keptKeys;
    cols.forEach(function (c, i) { c.forEach(function (n, j) { n.col = i; n.row = j; }); });

    // barycenter ordering, two sweeps
    var nb = {};
    nodes.forEach(function (n) { nb[n.id] = []; });
    edges.forEach(function (e) { if (e.from !== e.to) { nb[e.from].push(e.to); nb[e.to].push(e.from); } });
    for (var sweep = 0; sweep < 3; sweep++) {
      cols.forEach(function (col) {
        col.forEach(function (n) {
          var ps = nb[n.id].map(function (id) { return byId[id]; }).filter(function (m) { return m.col !== n.col; });
          n.bc = ps.length ? ps.reduce(function (acc, m) { return acc + m.row; }, 0) / ps.length : n.row;
        });
        col.sort(function (a, b) { return a.bc - b.bc || a.row - b.row; });
        col.forEach(function (n, j) { n.row = j; });
      });
    }

    var FS = 12, NH = 34, NH2 = 48, VG = 18, HG = 96, top = colKeys.some(Boolean) ? 30 : 8;
    var colW = cols.map(function (col) {
      return Math.max.apply(null, col.map(function (n) { return Math.min(200, Math.max(116, CRA.textW(n.label, FS, 600) + 34)); }));
    });
    cols.forEach(function (col) {
      col.forEach(function (n) {
        n.lines = CRA.wrap(n.label, colW[n.col] - 24, FS, 600, 2);
        n.h = n.lines.length > 1 ? NH2 : NH;
      });
    });
    var colHeight = cols.map(function (col) { return col.reduce(function (a, n) { return a + n.h; }, 0) + (col.length - 1) * VG; });
    var maxH = Math.max.apply(null, colHeight);
    var x = 0;
    cols.forEach(function (col, i) {
      var y = top + (maxH - colHeight[i]) / 2;
      col.forEach(function (n) { n.x = x; n.y = y; n.w = colW[i]; y += n.h + VG; });
      x += colW[i] + HG;
    });
    var W = x - HG, H = top + maxH + 14;
    // same-column edges route to the right: leave room
    if (edges.some(function (e) { return byId[e.from].col === byId[e.to].col && e.from !== e.to; })) W += 40;
    // edges skipping columns would cross intermediate nodes: route them below the diagram
    var detourBase = top + maxH + 18, detours = 0;
    edges.forEach(function (e) {
      var a = byId[e.from], b = byId[e.to];
      if (Math.abs(b.col - a.col) < 2) return;
      var fwd = b.col > a.col, lo = Math.min(a.col, b.col), hi = Math.max(a.col, b.col);
      var x1 = fwd ? a.x + a.w : a.x, x2 = fwd ? b.x : b.x + b.w, y1 = a.y + a.h / 2, y2 = b.y + b.h / 2, hit = false;
      for (var c = lo + 1; c < hi; c++) {
        cols[c].forEach(function (n) {
          [n.x, n.x + n.w].forEach(function (nx) {
            var yy = y1 + (y2 - y1) * ((nx - x1) / (x2 - x1));
            if (yy > n.y - 6 && yy < n.y + n.h + 6) hit = true;
          });
        });
      }
      if (hit) { e.detourY = detourBase + detours * 12; detours++; }
    });
    if (detours) H = detourBase + (detours - 1) * 12 + 14;

    var svg = svgRoot(W, H, 'components');
    var mk = arrowDefs(svg);
    if (colKeys.some(Boolean)) {
      cols.forEach(function (col, i) {
        var n0 = col[0];
        svg.appendChild(s('rect', { x: n0.x - 8, y: 0, width: colW[i] + 16, height: H, rx: 6, class: 'col-bg' }));
        svg.appendChild(s('text', { x: n0.x + colW[i] / 2, y: 17, class: 'col-h', 'text-anchor': 'middle' }, LAYER_LABEL[colKeys[i]] || str(colKeys[i])));
      });
    }
    var gE = s('g'), gL = s('g'), gN = s('g');
    svg.appendChild(gE); svg.appendChild(gN); svg.appendChild(gL);

    var pairCount = {};
    edges.forEach(function (e) {
      var a = byId[e.from], b = byId[e.to];
      var key = [e.from, e.to].sort().join('\u0001');
      var k = pairCount[key] = (pairCount[key] || 0) + 1;
      var off = (k - 1) * 8;
      var d, mx, my, ay = a.y + a.h / 2 + off, by = b.y + b.h / 2 + off;
      if (a === b) {
        d = 'M' + (a.x + a.w) + ',' + (a.y + 8) + ' c30,-14 30,' + (a.h + 4) + ' 0,' + (a.h - 16);
        mx = a.x + a.w + 24; my = a.y + a.h / 2;
      } else if (e.detourY != null) {
        var fw = b.col > a.col, dx = fw ? 1 : -1, sx = fw ? a.x + a.w : a.x, ex = fw ? b.x - 2 : b.x + b.w + 2, wy = e.detourY;
        d = 'M' + sx + ',' + ay + ' C' + (sx + dx * 50) + ',' + ay + ' ' + (sx + dx * 30) + ',' + wy + ' ' + (sx + dx * 80) + ',' + wy +
          ' L' + (ex - dx * 80) + ',' + wy + ' C' + (ex - dx * 30) + ',' + wy + ' ' + (ex - dx * 50) + ',' + by + ' ' + ex + ',' + by;
        mx = (sx + ex) / 2; my = wy;
      } else if (b.col > a.col) {
        d = bez(a.x + a.w, ay, b.x - 2, by, true); mx = (a.x + a.w + b.x) / 2; my = (ay + by) / 2;
      } else if (b.col < a.col) {
        d = bez(a.x, ay, b.x + b.w + 2, by, true); mx = (a.x + b.x + b.w) / 2; my = (ay + by) / 2;
      } else {
        var rx = a.x + a.w, bulge = 34 + Math.min(40, Math.abs(by - ay) * 0.15);
        d = 'M' + rx + ',' + ay + ' C' + (rx + bulge) + ',' + ay + ' ' + (rx + bulge) + ',' + by + ' ' + (rx + 2) + ',' + by;
        mx = rx + bulge * 0.75; my = (ay + by) / 2;
      }
      var st = ['new', 'modified', 'existing', 'removed'].indexOf(e.status) >= 0 ? e.status : 'existing';
      var path = s('path', { d: d, class: 'edge ' + st, 'marker-end': mk(st), 'data-tip': a.label + ' → ' + b.label + (e.label ? '\n' + e.label : '') + '\n(' + st + ')' });
      gE.appendChild(path);
      if (e.label) {
        var lt = CRA.fit(e.label, 130, 10.5);
        var lw = CRA.textW(lt, 10.5) + 8;
        gL.appendChild(s('rect', { x: mx - lw / 2, y: my - 8, width: lw, height: 15, rx: 3, class: 'elabel-bg' }));
        gL.appendChild(s('text', { x: mx, y: my + 3.5, class: 'elabel', 'text-anchor': 'middle', 'data-tip': e.label }, lt));
      }
    });
    nodes.forEach(function (n) {
      var st = ['new', 'modified', 'existing', 'removed'].indexOf(n.status) >= 0 ? n.status : 'existing';
      var g = s('g', { class: 'node ' + st + (n.implicit ? ' implicit' : ''),
        'data-tip': n.label + '\n' + st + (n.layer ? ' · ' + n.layer : '') + (n.implicit ? '\n(referenced by an edge, not declared as a node)' : '') + (n.tip ? '\n' + n.tip : '') });
      g.appendChild(s('rect', { x: n.x, y: n.y, width: n.w, height: n.h, rx: 6 }));
      g.appendChild(textLines(n.lines, n.x + n.w / 2, n.y + (n.lines.length > 1 ? 20 : 21), 14, { 'text-anchor': 'middle', 'font-size': FS, 'font-weight': 600 }));
      if (STATUS_TAG[st]) g.appendChild(s('text', { x: n.x + n.w - 5, y: n.y + 10, class: 'tag', 'text-anchor': 'end' }, STATUS_TAG[st]));
      gN.appendChild(g);
    });
    return svg;
  };

  /* ------------------------------------------------------------------ */
  /* sequence diagram                                                   */
  /* ------------------------------------------------------------------ */
  CRA.renderSequence = function (seq) {
    seq = obj(seq);
    var parts = [], pIdx = {};
    function addPart(id, label) {
      id = str(id);
      if (!id || pIdx[id] != null) return;
      pIdx[id] = parts.length; parts.push({ id: id, label: str(label || id) });
    }
    arr(seq.participants).forEach(function (p) { p = obj(p); addPart(p.id || p.label, p.label || p.id); });
    var steps = arr(seq.steps).map(obj).filter(function (st) { return st.from != null || st.to != null; });
    steps.forEach(function (st) { addPart(st.from || st.to); addPart(st.to || st.from); });
    if (!parts.length) return null;

    var FS = 11.5, PH = 30;
    var partW = parts.map(function (p) { return Math.min(170, Math.max(84, CRA.textW(p.label, 12, 650) + 22)); });
    // spacing: enough for the widest label between neighbours, bounded
    var gaps = [];
    for (var i = 0; i < parts.length - 1; i++) gaps.push(Math.max(70, (partW[i] + partW[i + 1]) / 2 + 24));
    steps.forEach(function (st) {
      var a = pIdx[str(st.from || st.to)], b = pIdx[str(st.to || st.from)];
      var lo = Math.min(a, b), hi = Math.max(a, b);
      var need = Math.min(300, CRA.textW(str(st.label), FS) + 46);
      if (lo === hi) { if (lo < gaps.length) gaps[lo] = Math.max(gaps[lo], Math.min(240, need * 0.8)); return; }
      var span = 0; for (var g = lo; g < hi; g++) span += gaps[g];
      if (span < need) { var add = (need - span) / (hi - lo); for (g = lo; g < hi; g++) gaps[g] += add; }
    });
    var xs = [partW[0] / 2 + 4];
    gaps.forEach(function (gp, j) { xs.push(xs[j] + gp); });
    var W = xs[xs.length - 1] + partW[partW.length - 1] / 2 + 4;
    // self-messages on the last participant need room on the right
    if (steps.some(function (st) { return str(st.from) === str(st.to) && pIdx[str(st.from)] === parts.length - 1; })) W += 90;

    var y = PH + 26, layout = [];
    steps.forEach(function (st, k) {
      var a = pIdx[str(st.from || st.to)], b = pIdx[str(st.to || st.from)];
      var self = a === b;
      var span = self ? 150 : Math.abs(xs[b] - xs[a]) - 30;
      var lines = CRA.wrap((k + 1) + '. ' + str(st.label), Math.max(60, span), FS, 400, 2);
      var ly = y + (lines.length - 1) * 13;
      var item = { a: a, b: b, self: self, lines: lines, labelY: y, arrowY: ly + 8, n: k + 1, st: st };
      y = item.arrowY + (self ? 26 : 14);
      if (st.note) {
        var nx1 = self ? xs[a] : Math.min(xs[a], xs[b]), nx2 = self ? xs[a] + 160 : Math.max(xs[a], xs[b]);
        var nw = Math.max(140, nx2 - nx1);
        var nl = CRA.wrap(str(st.note), nw - 14, 10.5, 400, 3);
        item.note = { x: nx1 + (nx2 - nx1 - nw) / 2, y: y, w: nw, h: nl.length * 13 + 8, lines: nl };
        y += item.note.h + 10;
      }
      y += 10;
      layout.push(item);
    });
    var H = y + 6;
    var svg = svgRoot(W, H, 'sequence');
    var mk = arrowDefs(svg);
    parts.forEach(function (p, i) {
      svg.appendChild(s('line', { x1: xs[i], y1: PH + 4, x2: xs[i], y2: H - 4, class: 'lifeline' }));
      var g = s('g', { class: 'part', 'data-tip': p.label });
      g.appendChild(s('rect', { x: xs[i] - partW[i] / 2, y: 4, width: partW[i], height: PH, rx: 5 }));
      g.appendChild(s('text', { x: xs[i], y: 4 + PH / 2 + 4, 'text-anchor': 'middle', 'font-size': 12 }, CRA.fit(p.label, partW[i] - 12, 12, 650)));
      svg.appendChild(g);
    });
    layout.forEach(function (it) {
      var x1 = xs[it.a], x2 = xs[it.b];
      var tip = str(it.st.label) + (it.st.note ? '\nNote: ' + str(it.st.note) : '');
      if (it.self) {
        svg.appendChild(s('path', { d: 'M' + x1 + ',' + (it.arrowY - 6) + ' h34 v18 h-32', class: 'msg', 'marker-end': mk(''), 'data-tip': tip }));
        svg.appendChild(textLines(it.lines, x1 + 40, it.labelY + 4, 13, { 'font-size': FS, 'data-tip': tip }));
      } else {
        var dir = x2 > x1 ? 1 : -1;
        svg.appendChild(s('line', { x1: x1, y1: it.arrowY, x2: x2 - dir * 2, y2: it.arrowY, class: 'msg', 'marker-end': mk(''), 'data-tip': tip }));
        svg.appendChild(textLines(it.lines, (x1 + x2) / 2, it.labelY, 13, { 'font-size': FS, 'text-anchor': 'middle', 'data-tip': tip }));
      }
      if (it.note) {
        var g = s('g', { class: 'note', 'data-tip': str(it.st.note) });
        g.appendChild(s('rect', { x: it.note.x, y: it.note.y, width: it.note.w, height: it.note.h, rx: 3 }));
        g.appendChild(textLines(it.note.lines, it.note.x + 7, it.note.y + 13, 13, {}));
        svg.appendChild(g);
      }
    });
    if (!steps.length) svg.appendChild(s('text', { x: W / 2, y: PH + 30, class: 't3', 'text-anchor': 'middle' }, 'No steps'));
    return svg;
  };

  /* ------------------------------------------------------------------ */
  /* squarified treemap                                                 */
  /* ------------------------------------------------------------------ */
  /* items: [{value, ...}] (value > 0); returns [{item, x, y, w, h}] */
  CRA.squarify = function (items, x, y, w, h) {
    var list = items.filter(function (it) { return it.value > 0; }).sort(function (a, b) { return b.value - a.value; });
    var total = list.reduce(function (a, it) { return a + it.value; }, 0);
    var out = [];
    if (!total || w <= 0 || h <= 0) return out;
    var scale = (w * h) / total;
    var areas = list.map(function (it) { return it.value * scale; });
    function worst(row, side) {
      var sum = 0, mx = 0, mn = Infinity;
      row.forEach(function (a) { sum += a; if (a > mx) mx = a; if (a < mn) mn = a; });
      var s2 = side * side, sum2 = sum * sum;
      return Math.max(s2 * mx / sum2, sum2 / (s2 * mn));
    }
    var i = 0;
    while (i < list.length) {
      var side = Math.min(w, h);
      var row = [areas[i]], j = i + 1, wPrev = worst(row, side);
      while (j < list.length) {
        var cand = row.concat(areas[j]), wc = worst(cand, side);
        if (wc > wPrev) break;
        row = cand; wPrev = wc; j++;
      }
      var rowSum = row.reduce(function (a, b) { return a + b; }, 0), k;
      if (w >= h) {
        var cw = rowSum / h, yy = y;
        for (k = 0; k < row.length; k++) { var rh = row[k] / cw; out.push({ item: list[i + k], x: x, y: yy, w: cw, h: rh }); yy += rh; }
        x += cw; w -= cw;
      } else {
        var rhh = rowSum / w, xx = x;
        for (k = 0; k < row.length; k++) { var rw = row[k] / rhh; out.push({ item: list[i + k], x: xx, y: y, w: rw, h: rhh }); xx += rw; }
        y += rhh; h -= rhh;
      }
      i = j;
    }
    return out;
  };

  /* groups: [{id, label, value, maxPts, critical, children:[{id,label,value,maxPts,critical,tip}]}]
     opts: {width, height, selected, onGroup(id), onItem(id)} */
  CRA.renderTreemap = function (groups, opts) {
    opts = opts || {};
    var W = Math.max(240, opts.width || 600), H = opts.height || 300;
    var svg = s('svg', { class: 'tm', width: W, height: H, viewBox: '0 0 ' + W + ' ' + H, role: 'img' });
    var rects = CRA.squarify(groups, 0, 0, W, H);
    rects.forEach(function (r) {
      var gr = r.item;
      var g = s('g', { class: 'tm-mod' + (opts.selected === gr.id ? ' sel' : '') });
      var tip = gr.label + (gr.deleted ? ' (deleted)' : '') + '\n' + CRA.fmt(gr.lines != null ? gr.lines : gr.value) + ' changed lines · ' + CRA.plural(gr.children.length, 'file') + '\nmax ' + gr.maxPts + ' pts' + (gr.critical ? ' · CRITICAL' : '') + '\nClick to filter the file list';
      g.appendChild(s('rect', { class: 'mbg' + (gr.deleted ? ' mdel' : ''), x: r.x, y: r.y, width: Math.max(0, r.w), height: Math.max(0, r.h) }));
      var header = r.h > 36 && r.w > 54 ? 17 : 0;
      var inner = { x: r.x + 2, y: r.y + 1 + header, w: r.w - 4, h: r.h - 3 - header };
      if (inner.w > 10 && inner.h > 10 && gr.children.length) {
        CRA.squarify(gr.children, inner.x, inner.y, inner.w, inner.h).forEach(function (c) {
          var it = c.item, p = CRA.clampPts(it.maxPts);
          var rc = s('rect', { class: 'tf ' + (it.deleted ? 'fdel' : 'fp' + p) + (it.critical ? ' crit' : ''), x: c.x, y: c.y, width: Math.max(0, c.w), height: Math.max(0, c.h),
            'data-tip': it.tip || it.label });
          rc.addEventListener('click', function (e) { e.stopPropagation(); if (opts.onItem) opts.onItem(it.id); });
          g.appendChild(rc);
          if (c.w > 46 && c.h > 15) {
            g.appendChild(s('text', { x: c.x + 4, y: c.y + 12, class: 'tf-l ' + (it.deleted ? 'ldel' : 'lp' + p) }, CRA.fit(it.label, c.w - 8, 10)));
          }
        });
      } else {
        g.appendChild(s('rect', { class: 'tf ' + (gr.deleted ? 'fdel' : 'fp' + CRA.clampPts(gr.maxPts)) + (gr.critical ? ' crit' : ''), x: r.x + 1, y: r.y + 1, width: Math.max(0, r.w - 2), height: Math.max(0, r.h - 2), 'data-tip': tip }));
      }
      if (header) {
        var label = CRA.fit(gr.label, r.w - 10, 11, 650);
        g.appendChild(s('text', { x: r.x + 5, y: r.y + 12.5, class: 'tm-ml' }, label));
        var lw = CRA.textW(label, 11, 650);
        if (r.w - lw > 70) g.appendChild(s('text', { x: r.x + 10 + lw, y: r.y + 12.5, class: 'tm-ms' }, CRA.fmt(gr.value) + ' lines'));
      }
      g.addEventListener('click', function () { if (opts.onGroup) opts.onGroup(gr.id); });
      if (header) g.appendChild(s('rect', { class: 'mh', x: r.x, y: r.y, width: Math.max(0, r.w), height: header, 'data-tip': tip }));
      svg.appendChild(g);
    });
    return svg;
  };

  /* ------------------------------------------------------------------ */
  /* diff viewer                                                        */
  /* ------------------------------------------------------------------ */
  /* text: unified diff. opts: {truncated, totalLines, shownLines} */
  CRA.renderDiff = function (text, opts) {
    opts = opts || {};
    text = str(text);
    var lines = text.split('\n');
    if (lines.length && lines[lines.length - 1] === '') lines.pop();
    var o = 0, n = 0, out = [];
    var E = CRA.esc;
    lines.forEach(function (l) {
      var cls, a = '', b = '', sg = '', code = l;
      var m = /^@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@/.exec(l);
      if (m) { o = +m[1]; n = +m[2]; cls = 'hunk'; code = l; }
      else if (/^(diff --git|index |--- |\+\+\+ |new file mode|deleted file mode|similarity index|rename from|rename to|old mode|new mode|Binary files)/.test(l)) { cls = 'meta'; }
      else if (l.charAt(0) === '+') { cls = 'add'; b = n++; sg = '+'; code = l.slice(1); }
      else if (l.charAt(0) === '-') { cls = 'del'; a = o++; sg = '-'; code = l.slice(1); }
      else if (l.charAt(0) === '\\') { cls = 'note'; }
      else { cls = 'ctx'; a = o++; b = n++; code = l.charAt(0) === ' ' ? l.slice(1) : l; }
      out.push('<div class="dl ' + cls + '"><span class="ln">' + a + '</span><span class="ln">' + b + '</span><span class="sg">' + sg +
        '</span><span>' + (E(code) || ' ') + '</span></div>');
    });
    var box = h('div', { class: 'diff' });
    box.innerHTML = out.join('') || '<div class="dl note"><span class="ln"></span><span class="ln"></span><span class="sg"></span><span>(empty diff)</span></div>';
    if (opts.truncated) {
      box.appendChild(h('div', { class: 'diff-trunc' },
        'Truncated: showing the first ' + CRA.fmt(opts.shownLines || lines.length) + (opts.totalLines ? ' of ' + CRA.fmt(opts.totalLines) : '') + ' lines. Open the full diff from the report directory.'));
    }
    return box;
  };

  /* ------------------------------------------------------------------ */
  /* misc page helpers                                                  */
  /* ------------------------------------------------------------------ */
  CRA.card = function (title, hint, body, opts) {
    opts = opts || {};
    return h('section', { class: 'card ' + (opts.cls || ''), id: opts.id || null }, [
      h('div', { class: 'card-h' }, [h('h2', null, title), hint ? h('span', { class: 'hint' }, hint) : null, opts.tools ? h('span', { class: 'spacer' }) : null, opts.tools || null]),
      h('div', { class: 'card-b' + (opts.flush ? ' flush' : '') }, body)
    ]);
  };
  /* wrapper that scales a wide SVG down to the container (down to 70 %), and scrolls beyond that */
  CRA.fitWrap = function (svg, minScale) {
    var wrap = h('div', { class: 'dg-wrap' }, svg);
    if (!svg) return wrap;
    var natural = num(svg.getAttribute('width'), 0), ms = minScale || 0.7;
    function check() {
      var w = wrap.clientWidth;
      if (!w || !natural) return;
      wrap.classList.toggle('fit', natural * ms <= w);
    }
    requestAnimationFrame(check);
    window.addEventListener('resize', CRA.debounce(check, 120));
    return wrap;
  };
  CRA.ptsLegend = function () {
    return h('span', { class: 'pts-legend', 'data-tip': 'Points per finding: 0 observed … 5 critical impact' },
      ['0', CRA.pts(0), CRA.pts(1), CRA.pts(2), CRA.pts(3), CRA.pts(4), CRA.pts(5), '5']);
  };
  CRA.debounce = function (fn, ms) {
    var t; return function () { var a = arguments, self = this; clearTimeout(t); t = setTimeout(function () { fn.apply(self, a); }, ms); };
  };

  global.CRA = CRA;
})(window);
