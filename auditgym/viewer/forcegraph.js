/* auditgym ForceGraph: a dependency-free, canvas-based force-directed graph view in the
 * spirit of the Obsidian and Anytype graph views. Barnes-Hut repulsion, link springs,
 * centre gravity, zoom at cursor, pan, node drag, neighbour highlight, label fade-in,
 * type filters, colour groups, forces panel hooks, evidence highlighting.
 */
(function (global) {
  'use strict';

  var TYPES = ['invoice', 'payment', 'row', 'fx', 'entity', 'account'];
  var BASE_R = { account: 7.5, invoice: 5.2, payment: 5.2, entity: 4.4, fx: 3.6, row: 2.7 };

  function cap(s) { return s ? s.charAt(0).toUpperCase() + s.slice(1) : s; }

  // ------------------------------------------------------------------ episode -> graph
  function offsetAt(schedule, ms) {
    var off = 0;
    for (var i = 0; i < schedule.length; i++) {
      if (schedule[i].ms <= ms) off = schedule[i].off; else break;
    }
    return off;
  }

  function buildEpisodeGraph(ep, opts) {
    opts = opts || {};
    var nodes = [], links = [], index = new Map(), docByDocId = new Map();
    function add(id, type, label, rec) {
      var i = index.get(id);
      if (i !== undefined) return i;
      i = nodes.length;
      index.set(id, i);
      nodes.push({ id: id, type: type, label: label, rec: rec || null, deg: 0, issues: [], nb: [], x: 0, y: 0, vx: 0, vy: 0, fx: null, fy: null });
      return i;
    }
    function link(a, b, kind) {
      if (a === undefined || b === undefined || a === b) return;
      links.push({ s: a, t: b, kind: kind });
      nodes[a].deg++; nodes[b].deg++;
    }
    var policy = ep.policy || {};
    var acc = policy.accounts || {};
    var base = policy.base_currency || (ep.manifest && ep.manifest.base_currency);
    var schedule = (policy.utc_offset_schedule || []).map(function (e) {
      var m = /^([+-])(\d\d):(\d\d)$/.exec(e.offset);
      return { ms: Date.parse(e.from_utc), off: m ? (m[1] === '-' ? -1 : 1) * (Number(m[2]) * 60 + Number(m[3])) : 0 };
    }).sort(function (a, b) { return a.ms - b.ms; });

    ep.invoices.forEach(function (d) {
      var i = add('doc:' + d.invoice_id, 'invoice', (d.kind === 'sales' ? 'Sales invoice ' : 'Purchase invoice ') + d.invoice_id, d);
      docByDocId.set(d.doc_id, i);
    });
    ep.payments.forEach(function (d) {
      var i = add('doc:' + d.payment_id, 'payment', cap(d.kind) + ' ' + d.payment_id, d);
      docByDocId.set(d.doc_id, i);
    });
    ep.invoices.concat(ep.payments).forEach(function (d) {
      if (d.entity_id) link(index.get('doc:' + (d.invoice_id || d.payment_id)), add('ent:' + d.entity_id, 'entity', 'Entity ' + d.entity_id), 'entity');
    });
    ep.payments.forEach(function (p) {
      (p.invoice_refs || []).forEach(function (r) { link(index.get('doc:' + p.payment_id), index.get('doc:' + r), 'ref'); });
    });
    ep.ledger.forEach(function (r) {
      var i = add('row:' + r.row_id, 'row', r.row_id + ' · ' + r.account, r);
      if (opts.accounts !== false) link(i, add('acc:' + r.account, 'account', r.account + ' ' + (acc[r.account] || '')), 'account');
      if (r.invoice_id) link(i, index.get('doc:' + r.invoice_id), 'posting');
      if (r.payment_id) link(i, index.get('doc:' + r.payment_id), 'posting');
    });
    var fxKey = new Map();
    ep.fx.forEach(function (f) {
      var id = f.date + ':' + f.source_currency + ':' + f.target_currency;
      var i = add('fx:' + id, 'fx', 'FX ' + f.date + ' ' + f.source_currency + '→' + f.target_currency, f);
      if (f.target_currency === base) fxKey.set(f.date + '|' + f.source_currency, i);
    });
    // each foreign document links to the rate the policy prescribes (local date, else latest earlier)
    ep.invoices.concat(ep.payments).forEach(function (d) {
      if (!base || d.currency === base) return;
      var ms = Date.parse(d.issued_at || d.timestamp);
      if (isNaN(ms)) return;
      var local = ms + offsetAt(schedule, ms) * 60000;
      for (var back = 0; back < 15; back++) {
        var day = new Date(local - back * 86400000).toISOString().slice(0, 10);
        var hit = fxKey.get(day + '|' + d.currency);
        if (hit !== undefined) { link(index.get('doc:' + (d.invoice_id || d.payment_id)), hit, 'rate'); break; }
      }
    });
    // strict lookups (doc, docId, row, fx) flag truth issues, so obsidian/anytype output stays as before
    function resolveStrict(id) {
      var v = index.get('doc:' + id);
      if (v === undefined) v = docByDocId.get(id);
      if (v === undefined) v = index.get('row:' + id);
      if (v === undefined) v = index.get('fx:' + id);
      return v;
    }
    function resolve(id) {
      var v = resolveStrict(id);
      if (v === undefined) v = index.get('ent:' + id);
      if (v === undefined) v = index.get('acc:' + id);
      return v;
    }
    ((ep.truth && ep.truth.issues) || []).forEach(function (t) {
      var ids = t.affected_ids.slice();
      t.evidence_sets.forEach(function (s) { ids = ids.concat(s); });
      ids.forEach(function (id) {
        var n = resolveStrict(id);
        if (n !== undefined && nodes[n].issues.indexOf(t.issue_id) < 0) nodes[n].issues.push(t.issue_id);
      });
    });
    links.forEach(function (l) { nodes[l.s].nb.push(l.t); nodes[l.t].nb.push(l.s); });
    var graph = { nodes: nodes, links: links, index: index, resolve: resolve };
    if (typeof opts.label === 'function') relabel(graph, opts.label);
    return graph;
  }

  function relabel(graph, fn) {
    for (var i = 0; i < graph.nodes.length; i++) graph.nodes[i].label = fn(graph.nodes[i]);
  }

  // PageRank on the undirected graph (d = 0.85, 40 iterations), cached on the graph as n.prn in 0..1
  function ensurePageRank(g) {
    var nodes = g.nodes, N = nodes.length;
    if (g.prN === N) return;
    var pr = new Array(N), nx = new Array(N), d = 0.85, i, j, it, nb;
    for (i = 0; i < N; i++) pr[i] = 1 / N;
    for (it = 0; it < 40; it++) {
      var dangling = 0;
      for (i = 0; i < N; i++) if (!nodes[i].nb.length) dangling += pr[i];
      var base = (1 - d) / N + d * dangling / N;
      for (i = 0; i < N; i++) nx[i] = base;
      for (i = 0; i < N; i++) {
        nb = nodes[i].nb;
        if (!nb.length) continue;
        var share = d * pr[i] / nb.length;
        for (j = 0; j < nb.length; j++) nx[nb[j]] += share;
      }
      var tmp = pr; pr = nx; nx = tmp;
    }
    var max = 0;
    for (i = 0; i < N; i++) if (pr[i] > max) max = pr[i];
    for (i = 0; i < N; i++) nodes[i].prn = max > 0 ? pr[i] / max : 0;
    g.prN = N;
  }

  // communities: n.group if numeric, else deterministic label propagation; sets n.cl = size rank, -1 for singletons
  function ensureCommunities(g) {
    var nodes = g.nodes, N = nodes.length;
    if (g.commN === N) return;
    var lab = new Array(N), i, j, numeric = false;
    for (i = 0; i < N; i++) if (typeof nodes[i].group === 'number') { numeric = true; break; }
    if (numeric) {
      for (i = 0; i < N; i++) lab[i] = typeof nodes[i].group === 'number' ? nodes[i].group : 1e9 + i;
    } else {
      for (i = 0; i < N; i++) lab[i] = i;
      for (var round = 0; round < 25; round++) {
        var changed = false;
        for (i = 0; i < N; i++) {
          var nb = nodes[i].nb;
          if (!nb.length) continue;
          var cnt = new Map(), best = lab[i], bc = 0;
          for (j = 0; j < nb.length; j++) cnt.set(lab[nb[j]], (cnt.get(lab[nb[j]]) || 0) + 1);
          cnt.forEach(function (c, l) { if (c > bc || (c === bc && l < best)) { bc = c; best = l; } });
          if (best !== lab[i]) { lab[i] = best; changed = true; }
        }
        if (!changed) break;
      }
    }
    var size = new Map();
    for (i = 0; i < N; i++) size.set(lab[i], (size.get(lab[i]) || 0) + 1);
    var order = [];
    size.forEach(function (c, l) { if (c > 1) order.push(l); });
    order.sort(function (a, b) { return size.get(b) - size.get(a) || a - b; });
    var rank = new Map();
    order.forEach(function (l, r) { rank.set(l, r); });
    for (i = 0; i < N; i++) nodes[i].cl = rank.has(lab[i]) ? rank.get(lab[i]) : -1;
    g.commN = N; g.commCount = order.length;
  }

  // ------------------------------------------------------------------ physics
  function QuadNode(x0, y0, x1, y1) {
    this.x0 = x0; this.y0 = y0; this.x1 = x1; this.y1 = y1;
    this.body = -1; this.kids = null; this.mass = 0; this.cx = 0; this.cy = 0;
  }

  function insert(q, nodes, i, depth) {
    var n = nodes[i];
    if (q.kids === null && q.body < 0 && q.mass === 0) { q.body = i; q.mass = 1; return; }
    if (q.kids === null) {
      if (depth > 40) { q.mass++; return; } // coincident points
      var mx = (q.x0 + q.x1) / 2, my = (q.y0 + q.y1) / 2;
      q.kids = [new QuadNode(q.x0, q.y0, mx, my), new QuadNode(mx, q.y0, q.x1, my), new QuadNode(q.x0, my, mx, q.y1), new QuadNode(mx, my, q.x1, q.y1)];
      var old = q.body; q.body = -1;
      if (old >= 0) insert(q.kids[quadrant(q, nodes[old])], nodes, old, depth + 1);
    }
    insert(q.kids[quadrant(q, n)], nodes, i, depth + 1);
  }

  function quadrant(q, n) {
    var mx = (q.x0 + q.x1) / 2, my = (q.y0 + q.y1) / 2;
    return (n.x >= mx ? 1 : 0) + (n.y >= my ? 2 : 0);
  }

  function accumulate(q, nodes) {
    if (q.kids === null) {
      if (q.body >= 0) { q.cx = nodes[q.body].x; q.cy = nodes[q.body].y; }
      return q.mass;
    }
    var m = 0, cx = 0, cy = 0;
    for (var k = 0; k < 4; k++) {
      var c = q.kids[k], cm = accumulate(c, nodes);
      if (cm) { m += cm; cx += c.cx * cm; cy += c.cy * cm; }
    }
    q.mass = m; q.cx = m ? cx / m : 0; q.cy = m ? cy / m : 0;
    return m;
  }

  function Simulation(graph, params, keep) {
    this.g = graph;
    this.p = params;
    this.alpha = 1; this.alphaMin = 0.002; this.alphaDecay = 1 - Math.pow(0.002, 1 / 320); this.alphaTarget = 0;
    this.active = [];
    if (keep && graph.laidOut) this.alpha = 0.04; else this.seed();
  }

  Simulation.prototype.seed = function () {
    var nodes = this.g.nodes;
    for (var i = 0; i < nodes.length; i++) {
      var r = 9 * Math.sqrt(0.5 + i), a = i * Math.PI * (3 - Math.sqrt(5));
      nodes[i].x = r * Math.cos(a); nodes[i].y = r * Math.sin(a); nodes[i].vx = 0; nodes[i].vy = 0;
    }
  };

  Simulation.prototype.setActive = function (visible) {
    this.active = [];
    for (var i = 0; i < visible.length; i++) if (visible[i]) this.active.push(i);
    this.visible = visible;
  };

  Simulation.prototype.tick = function () {
    var g = this.g, nodes = g.nodes, P = this.p, alpha = this.alpha, vis = this.visible, i, n;
    // springs
    for (i = 0; i < g.links.length; i++) {
      var l = g.links[i];
      if (!vis[l.s] || !vis[l.t]) continue;
      var s = nodes[l.s], t = nodes[l.t];
      var dx = t.x + t.vx - s.x - s.vx, dy = t.y + t.vy - s.y - s.vy;
      var d = Math.sqrt(dx * dx + dy * dy) || 1e-6;
      var strength = P.linkForce / Math.min(s.deg, t.deg);
      var k = (d - P.linkDistance) / d * alpha * strength;
      dx *= k; dy *= k;
      var bias = s.deg / (s.deg + t.deg);
      t.vx -= dx * bias; t.vy -= dy * bias;
      s.vx += dx * (1 - bias); s.vy += dy * (1 - bias);
    }
    // Barnes-Hut repulsion
    var act = this.active;
    if (act.length) {
      var x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
      for (i = 0; i < act.length; i++) {
        n = nodes[act[i]];
        if (n.x < x0) x0 = n.x; if (n.x > x1) x1 = n.x; if (n.y < y0) y0 = n.y; if (n.y > y1) y1 = n.y;
      }
      var size = Math.max(x1 - x0, y1 - y0) + 1;
      var root = new QuadNode(x0, y0, x0 + size, y0 + size);
      for (i = 0; i < act.length; i++) insert(root, nodes, act[i], 0);
      accumulate(root, nodes);
      var theta2 = 0.81, charge = -P.repel;
      for (i = 0; i < act.length; i++) {
        n = nodes[act[i]];
        var stack = [root];
        while (stack.length) {
          var q = stack.pop();
          if (!q.mass) continue;
          var qx = q.cx - n.x, qy = q.cy - n.y, w = q.x1 - q.x0, l2 = qx * qx + qy * qy;
          if (q.kids === null || (w * w) / theta2 < l2) {
            if (q.kids === null && q.body === act[i] && q.mass === 1) continue;
            if (l2 < 1) l2 = 1;
            var f = charge * alpha * q.mass / l2;
            n.vx += qx * f; n.vy += qy * f;
          } else {
            stack.push(q.kids[0], q.kids[1], q.kids[2], q.kids[3]);
          }
        }
      }
    }
    // centre gravity and integration
    for (i = 0; i < act.length; i++) {
      n = nodes[act[i]];
      n.vx -= n.x * P.center * alpha; n.vy -= n.y * P.center * alpha;
      if (n.fx !== null) { n.x = n.fx; n.y = n.fy; n.vx = 0; n.vy = 0; continue; }
      n.vx *= 0.58; n.vy *= 0.58;
      n.x += n.vx; n.y += n.vy;
    }
    this.alpha += (this.alphaTarget - this.alpha) * this.alphaDecay;
  };

  // ------------------------------------------------------------------ palettes
  var STYLES = {
    obsidian: {
      bg: '#1e1e1e', edge: 'rgba(200,200,200,0.16)', edgeHi: 'rgba(168,130,255,0.9)', text: '#dadada', textDim: 'rgba(218,218,218,0.25)',
      hi: '#a882ff', ring: '#a882ff', issue: '#e5534b', outline: null,
      mono: '#9aa0a6', monoHub: '#d4d4d4', monoRow: '#6e737a',
      groups: { invoice: '#a882ff', payment: '#4fc1a1', row: '#6b8fd6', fx: '#e0b45a', entity: '#e06c9f', account: '#e8e8e8' },
      clusters: ['#a882ff', '#4fc1a1', '#6b8fd6', '#e0b45a', '#e06c9f', '#e5876b', '#7fbf6a', '#58b6d6', '#c78fd9', '#d1c25a', '#8a97e6', '#d97a7a']
    },
    anytype: {
      bg: '#fbfbfa', edge: 'rgba(37,37,37,0.13)', edgeHi: 'rgba(62,123,250,0.85)', text: '#252525', textDim: 'rgba(37,37,37,0.22)',
      hi: '#3e7bfa', ring: '#3e7bfa', issue: '#e5484d', outline: '#ffffff',
      mono: '#b6b6b6', monoHub: '#6b6b6b', monoRow: '#cfcfcf',
      groups: { invoice: '#8c6cf0', payment: '#21b38a', row: '#8fb0ff', fx: '#f5a524', entity: '#ee5d8f', account: '#3e7bfa' },
      clusters: ['#3e7bfa', '#21b38a', '#f5a524', '#ee5d8f', '#8c6cf0', '#12a5c4', '#e5484d', '#7ab51d', '#d9692b', '#5b6cd9', '#c24fb3', '#8a8f98']
    },
    // glow on ink: nodes glow, the space around them stays plain (no nebula wash, no starfield)
    galaxy: {
      bg: '#0b0d14', edge: 'rgba(163,169,184,0.09)', edgeHi: 'rgba(157,188,255,0.9)', text: '#e3e7ef', textDim: 'rgba(227,231,239,0.22)',
      hi: '#ffffff', ring: '#9dbcff', issue: '#ff4d6d', outline: null,
      mono: '#7a8296', monoHub: '#eef0f5', monoRow: '#4a5164',
      groups: { invoice: '#9b6bff', payment: '#2fe0d0', row: '#4f8cff', fx: '#ffb938', entity: '#ff5fb0', account: '#f4f6ff' },
      glow: true, nebula: null, stars: false,
      clusters: ['#ff6a3d', '#2fe0d0', '#9b6bff', '#ff5fb0', '#ffd23f', '#4f8cff', '#5dff9b', '#ff3d6e', '#38d9f5', '#c77dff',
        '#ff9f43', '#7be0a0', '#f06292', '#8ab4ff', '#e6ff5c', '#ff7ad9']
    }
  };

  // ------------------------------------------------------------------ glow sprites
  function hexRgb(c) {
    var m = /^#([0-9a-f]{2})([0-9a-f]{2})([0-9a-f]{2})$/i.exec(c);
    if (m) return [parseInt(m[1], 16), parseInt(m[2], 16), parseInt(m[3], 16)];
    m = /^#([0-9a-f])([0-9a-f])([0-9a-f])$/i.exec(c);
    return m ? [parseInt(m[1] + m[1], 16), parseInt(m[2] + m[2], 16), parseInt(m[3] + m[3], 16)] : [200, 200, 220];
  }

  // 64x64 radial sprite: hot core, body in the colour, soft transparent halo
  function makeSprite(colour) {
    var cv = document.createElement('canvas'), x;
    cv.width = cv.height = 64;
    x = cv.getContext('2d');
    var c = hexRgb(colour), rgb = c[0] + ',' + c[1] + ',' + c[2];
    var hot = 'rgba(' + Math.round((c[0] + 255) / 2) + ',' + Math.round((c[1] + 255) / 2) + ',' + Math.round((c[2] + 255) / 2) + ',1)';
    var gr = x.createRadialGradient(32, 32, 0, 32, 32, 32);
    gr.addColorStop(0, hot);
    gr.addColorStop(0.14, 'rgba(' + rgb + ',1)');
    gr.addColorStop(0.3, 'rgba(' + rgb + ',0.85)');
    gr.addColorStop(0.5, 'rgba(' + rgb + ',0.48)');
    gr.addColorStop(0.72, 'rgba(' + rgb + ',0.16)');
    gr.addColorStop(1, 'rgba(' + rgb + ',0)');
    x.fillStyle = gr; x.fillRect(0, 0, 64, 64);
    return cv;
  }

  function mulberry(seed) {
    return function () {
      seed = (seed + 0x6D2B79F5) | 0;
      var t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }

  // ------------------------------------------------------------------ view
  function ForceGraph(canvas, graph, options) {
    var self = this;
    this.canvas = canvas; this.ctx = canvas.getContext('2d'); this.g = graph;
    this.opt = Object.assign({ style: 'obsidian', groups: true, labels: 1.15, nodeSize: 1, linkWidth: 1, arrows: false, showIssues: true,
      insetRight: 0, insetBottom: 0, insetLeft: 0, insetTop: 0, keepLayout: true, fitOnSettle: true, labelsAll: false, bg: null,
      glow: 1, colorMode: 'type', sizeMode: 'degree', linkOpacity: 1, showLinks: true, wheelZoom: 'always' }, options || {});
    this.reduced = !!(global.matchMedia && global.matchMedia('(prefers-reduced-motion: reduce)').matches);
    this.sprites = new Map();
    this.stars = null;
    this.params = Object.assign({ center: 0.045, repel: 42, linkForce: 0.9, linkDistance: 26 }, (options || {}).forces || {});
    this.types = {}; TYPES.forEach(function (t) { self.types[t] = true; });
    this.k = 0.6; this.tx = 0; this.ty = 0; this.hover = -1; this.selected = -1; this.focus = null; this.query = '';
    this.sim = new Simulation(graph, this.params, this.opt.keepLayout);
    this.listeners = {};
    this.handlers = [];
    this.settledOnce = false;
    this.applyFilter();
    this.resize();
    this.bind();
    this.loop();
  }

  ForceGraph.prototype.on = function (name, fn) { (this.listeners[name] = this.listeners[name] || []).push(fn); };
  ForceGraph.prototype.emit = function (name, arg) { (this.listeners[name] || []).forEach(function (fn) { fn(arg); }); };

  ForceGraph.prototype.applyFilter = function () {
    var vis = this.g.nodes.map(function (n) { return !!this.types[n.type]; }, this);
    if (this.orphansHidden) {
      for (var i = 0; i < vis.length; i++) if (vis[i] && !this.g.nodes[i].nb.some(function (j) { return vis[j]; })) vis[i] = false;
    }
    this.visible = vis;
    this.sim.setActive(vis);
  };

  ForceGraph.prototype.setType = function (type, on) { this.types[type] = on; this.applyFilter(); this.reheat(0.5); };
  ForceGraph.prototype.setOrphans = function (hidden) { this.orphansHidden = hidden; this.applyFilter(); this.reheat(0.3); };
  ForceGraph.prototype.setForce = function (name, value) { this.params[name] = value; this.reheat(0.6); };
  ForceGraph.prototype.setOption = function (name, value) { this.opt[name] = value; this.dirty = true; };
  ForceGraph.prototype.setStyle = function (name) {
    if (!STYLES[name]) return;
    this.opt.style = name; this.nebKey = null; this.dirty = true; // sprites are keyed by colour only, valid for every style
  };
  ForceGraph.prototype.relabel = function (fn) { relabel(this.g, fn); this.dirty = true; };
  ForceGraph.prototype.getView = function () { return { k: this.k, tx: this.tx, ty: this.ty, w: this.w, h: this.h }; };
  ForceGraph.prototype.setView = function (v) {
    this.k = v.k; this.tx = v.tx; this.ty = v.ty;
    this.target = null; this.userMoved = true; this.dirty = true;
  };
  ForceGraph.prototype.reheat =function (a) { this.sim.alpha = Math.max(this.sim.alpha, a || 0.8); };
  ForceGraph.prototype.animate = function () { this.sim.seed(); this.sim.alpha = 1; this.fit(true); };
  ForceGraph.prototype.search = function (q) { this.query = (q || '').trim().toLowerCase(); this.dirty = true; };

  ForceGraph.prototype.focusIssue = function (issueId) {
    if (!issueId) { this.focus = null; this.dirty = true; return; }
    var set = new Set();
    this.g.nodes.forEach(function (n, i) { if (n.issues.indexOf(issueId) >= 0) set.add(i); });
    this.focus = set; this.dirty = true;
    this.fitTo(Array.from(set));
  };

  ForceGraph.prototype.select = function (i) {
    this.selected = i; this.dirty = true;
    this.emit('select', i >= 0 ? this.g.nodes[i] : null);
  };

  ForceGraph.prototype.selectId = function (id) {
    var i = this.g.resolve(id);
    if (i !== undefined) { this.select(i); this.fitTo([i].concat(this.g.nodes[i].nb)); }
  };

  ForceGraph.prototype.resize = function () {
    var r = this.canvas.getBoundingClientRect(), dpr = global.devicePixelRatio || 1;
    var ow = this.w, oh = this.h, changed = ow !== undefined && (Math.abs(ow - r.width) > 1 || Math.abs(oh - r.height) > 1);
    this.w = r.width; this.h = r.height;
    this.canvas.width = Math.round(r.width * dpr); this.canvas.height = Math.round(r.height * dpr);
    this.ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    if (!this.tx && !this.ty) { this.tx = this.w / 2; this.ty = this.h / 2; }
    // deterministic screen-space starfield, regenerated only on resize
    var rnd = mulberry(7919), cnt = 150 + Math.floor(rnd() * 100), st = [];
    for (var s = 0; s < cnt; s++) {
      var b = rnd();
      st.push(rnd() * this.w, rnd() * this.h, 0.4 + b * b * 1.1, 0.12 + b * 0.6);
    }
    this.stars = st; this.nebKey = null;
    this.dirty = true;
    // the canvas changed size: refit the graph, or keep the centre when the user already moved the camera
    if (changed && this.visible) {
      if (!this.userMoved) this.fit(); else { this.tx += (this.w - ow) / 2; this.ty += (this.h - oh) / 2; }
    }
  };

  ForceGraph.prototype.fit = function (soft) {
    var idx = [];
    for (var i = 0; i < this.visible.length; i++) if (this.visible[i]) idx.push(i);
    this.fitTo(idx, soft);
  };

  ForceGraph.prototype.fitTo = function (idx, soft) {
    if (!idx.length) return;
    var x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity, nodes = this.g.nodes;
    if (idx.length > 60) {
      // robust box: far-flung orphans would otherwise shrink the main body to a dot
      var xs = idx.map(function (i) { return nodes[i].x; }).sort(function (a, b) { return a - b; });
      var ys = idx.map(function (i) { return nodes[i].y; }).sort(function (a, b) { return a - b; });
      var lo = Math.floor(idx.length * 0.04), hi = Math.ceil(idx.length * 0.96) - 1;
      x0 = xs[lo] - 40; x1 = xs[hi] + 40; y0 = ys[lo]; y1 = ys[hi]; // 40: part of a hub label, so edge labels are not cropped
    } else {
      idx.forEach(function (i) { var n = nodes[i]; x0 = Math.min(x0, n.x); x1 = Math.max(x1, n.x); y0 = Math.min(y0, n.y); y1 = Math.max(y1, n.y); });
    }
    var L = this.opt.insetLeft || 0, T = this.opt.insetTop || 0;
    var W = this.w - L - this.opt.insetRight, H = this.h - T - this.opt.insetBottom;
    // margins shrink with the viewport so small canvases (drawer local graphs) still zoom in
    var padX = Math.min(240, W * 0.3), padY = Math.min(200, H * 0.3);
    var k = Math.min(W / Math.max(40, x1 - x0 + padX), H / Math.max(40, y1 - y0 + padY));
    k = Math.max(0.08, Math.min(soft ? 0.9 : 1.8, k));
    this.target = { k: k, tx: L + W / 2 - k * (x0 + x1) / 2, ty: T + H / 2 - k * (y0 + y1) / 2 };
  };

  ForceGraph.prototype.toWorld = function (sx, sy) { return { x: (sx - this.tx) / this.k, y: (sy - this.ty) / this.k }; };

  ForceGraph.prototype.radius = function (n) {
    var mode = this.opt.sizeMode;
    if (mode === 'pagerank') {
      ensurePageRank(this.g);
      return BASE_R[n.type] * this.opt.nodeSize * (0.65 + 2.1 * Math.sqrt(n.prn || 0));
    }
    if (mode === 'uniform') return (n.type === 'account' ? 5 : 3.4) * this.opt.nodeSize;
    return BASE_R[n.type] * this.opt.nodeSize * (1 + 0.12 * Math.sqrt(n.deg));
  };

  ForceGraph.prototype.sprite = function (colour) {
    var s = this.sprites.get(colour);
    if (!s) { s = makeSprite(colour); this.sprites.set(colour, s); }
    return s;
  };

  ForceGraph.prototype.pick = function (sx, sy) {
    var p = this.toWorld(sx, sy), best = -1, bestD = Infinity, nodes = this.g.nodes;
    for (var i = 0; i < nodes.length; i++) {
      if (!this.visible[i]) continue;
      var n = nodes[i], dx = n.x - p.x, dy = n.y - p.y, d = dx * dx + dy * dy, r = this.radius(n) + 4 / this.k;
      if (d < r * r && d < bestD) { best = i; bestD = d; }
    }
    return best;
  };

  ForceGraph.prototype.bind = function () {
    var self = this, c = this.canvas, drag = null, panning = null, moved = false, downX = 0, downY = 0;
    function clearHover() { if (self.hover !== -1) { self.hover = -1; self.dirty = true; c.style.cursor = 'grab'; self.emit('hover', null); } }
    self.listen(c, 'wheel', function (e) {
      if (self.opt.wheelZoom === 'ctrl' && !e.ctrlKey) return; // local graphs: plain wheel scrolls the drawer
      e.preventDefault();
      var r = c.getBoundingClientRect(), sx = e.clientX - r.left, sy = e.clientY - r.top;
      var nk = Math.max(0.05, Math.min(8, self.k * Math.exp(-e.deltaY * 0.0015)));
      self.tx = sx - (sx - self.tx) * nk / self.k; self.ty = sy - (sy - self.ty) * nk / self.k; self.k = nk;
      self.target = null; self.dirty = true; self.userMoved = true;
    }, { passive: false });
    self.listen(c, 'mousedown', function (e) {
      var r = c.getBoundingClientRect(), sx = e.clientX - r.left, sy = e.clientY - r.top, i = self.pick(sx, sy);
      moved = false; self.target = null; downX = sx; downY = sy;
      if (i >= 0) { drag = i; }
      else panning = { sx: sx, sy: sy, tx: self.tx, ty: self.ty };
      self.userMoved = true;
    });
    self.listen(global, 'mousemove', function (e) {
      var r = c.getBoundingClientRect(), sx = e.clientX - r.left, sy = e.clientY - r.top;
      if (drag !== null) {
        if (!moved && Math.abs(sx - downX) + Math.abs(sy - downY) <= 3) return; // a 1px jitter is still a click
        var p = self.toWorld(sx, sy), n = self.g.nodes[drag];
        if (!moved) { self.sim.alphaTarget = 0.25; self.reheat(0.25); }
        n.fx = p.x; n.fy = p.y; moved = true; self.dirty = true; return;
      }
      if (panning) {
        if (!moved && Math.abs(sx - downX) + Math.abs(sy - downY) <= 3) return;
        self.tx = panning.tx + sx - panning.sx; self.ty = panning.ty + sy - panning.sy; moved = true; self.dirty = true; return;
      }
      if (e.target !== c || sx < 0 || sy < 0 || sx > self.w || sy > self.h) { clearHover(); return; } // overlays and the outside do not hover
      var h = self.pick(sx, sy);
      if (h !== self.hover) { self.hover = h; c.style.cursor = h >= 0 ? 'pointer' : 'grab'; self.dirty = true; self.emit('hover', h >= 0 ? self.g.nodes[h] : null); }
    });
    self.listen(global, 'mouseup', function () {
      if (drag !== null) {
        var n = self.g.nodes[drag];
        if (!moved) self.select(drag);
        if (!self.pinOnDrag) { n.fx = null; n.fy = null; }
        self.sim.alphaTarget = 0; drag = null;
      } else if (panning) {
        if (!moved) self.select(-1);
        panning = null;
      }
    });
    self.listen(c, 'mouseleave', clearHover);
    self.listen(c, 'dblclick', function (e) {
      var r = c.getBoundingClientRect(), i = self.pick(e.clientX - r.left, e.clientY - r.top);
      if (i >= 0) self.fitTo([i].concat(self.g.nodes[i].nb));
    });
    if (global.ResizeObserver) {
      this.ro = new global.ResizeObserver(function () { self.resize(); });
      this.ro.observe(c);
    } else {
      self.listen(global, 'resize', function () { self.resize(); });
    }
  };

  ForceGraph.prototype.listen = function (target, name, fn) {
    target.addEventListener(name, fn);
    this.handlers.push([target, name, fn]);
  };

  ForceGraph.prototype.destroy = function () {
    this.dead = true;
    this.handlers.forEach(function (h) { h[0].removeEventListener(h[1], h[2]); });
    this.handlers = [];
    if (this.ro) this.ro.disconnect();
    if (this.sim.alpha < 0.08) this.g.laidOut = true;
  };

  ForceGraph.prototype.color = function (n) {
    var S = STYLES[this.opt.style], mode = this.opt.colorMode;
    var mono = n.type === 'account' ? S.monoHub : n.type === 'row' ? S.monoRow : S.mono;
    if (!this.opt.groups || mode === 'mono') return mono;
    if (mode === 'cluster') return n.cl >= 0 && S.clusters ? S.clusters[n.cl % S.clusters.length] : S.mono;
    if (mode === 'evidence') return n.issues.length ? S.issue : mono;
    return S.groups[n.type];
  };

  ForceGraph.prototype.loop = function () {
    var self = this;
    function frame() {
      if (self.dead) return;
      var running = self.sim.alpha > self.sim.alphaMin || self.sim.alphaTarget > 0;
      if (!self.settledOnce && self.sim.alpha < 0.06) {
        self.settledOnce = true; self.g.laidOut = true;
        if (self.opt.fitOnSettle && !self.userMoved) self.fit();
        self.emit('settle');
      }
      if (running) {
        if (self.reduced) { for (var pz = 0; pz < 220 && self.sim.alpha > 0.06; pz++) self.sim.tick(); } // reduced motion: settle the layout at once
        self.sim.tick(); if (self.sim.alpha > 0.3) self.sim.tick();
      }
      if (self.target) {
        var t = self.target, e = self.reduced ? 1 : 0.18;
        self.k += (t.k - self.k) * e; self.tx += (t.tx - self.tx) * e; self.ty += (t.ty - self.ty) * e;
        if (Math.abs(t.k - self.k) < 1e-3 && Math.abs(t.tx - self.tx) < 0.5 && Math.abs(t.ty - self.ty) < 0.5) self.target = null;
      }
      if (running || self.dirty || self.target) { self.draw(); self.dirty = false; }
      global.requestAnimationFrame(frame);
    }
    global.requestAnimationFrame(frame);
  };

  ForceGraph.prototype.draw = function () {
    var ctx = this.ctx, S = STYLES[this.opt.style], nodes = this.g.nodes, links = this.g.links, k = this.k, vis = this.visible;
    var opt = this.opt, glow = !!S.glow, i, st;
    if (opt.colorMode === 'cluster') ensureCommunities(this.g);
    ctx.save();
    if (opt.bg === 'transparent') ctx.clearRect(0, 0, this.w, this.h);
    else {
      ctx.fillStyle = opt.bg || S.bg; ctx.fillRect(0, 0, this.w, this.h);
      if (S.nebula) {
        var nk = this.w + 'x' + this.h + S.nebula;
        if (this.nebKey !== nk) {
          var nr = Math.max(this.w, this.h) * 0.7;
          this.neb = ctx.createRadialGradient(this.w / 2, this.h / 2, 0, this.w / 2, this.h / 2, nr);
          this.neb.addColorStop(0, S.nebula); this.neb.addColorStop(0.55, 'rgba(40,30,110,0.10)'); this.neb.addColorStop(1, 'rgba(0,0,0,0)');
          this.nebKey = nk;
        }
        ctx.fillStyle = this.neb; ctx.fillRect(0, 0, this.w, this.h);
      }
      if (S.stars && this.stars) {
        st = this.stars; ctx.fillStyle = S.text;
        for (i = 0; i < st.length; i += 4) { ctx.globalAlpha = st[i + 3]; ctx.fillRect(st[i], st[i + 1], st[i + 2], st[i + 2]); }
        ctx.globalAlpha = 1;
      }
    }
    ctx.translate(this.tx, this.ty); ctx.scale(k, k);
    if (glow) ctx.globalCompositeOperation = 'lighter';
    // emphasis set: hover/selected neighbourhood, issue focus, search
    var em = null, center = this.hover >= 0 ? this.hover : this.selected;
    if (center >= 0) { em = new Set([center].concat(nodes[center].nb)); }
    else if (this.focus) em = this.focus;
    var q = this.query, matches = null;
    if (q) { matches = new Set(); for (var m = 0; m < nodes.length; m++) if (vis[m] && (nodes[m].id.toLowerCase().indexOf(q) >= 0 || nodes[m].label.toLowerCase().indexOf(q) >= 0)) matches.add(m); if (!em) em = matches; }
    // edges
    var lw = 1 * this.opt.linkWidth / k;
    ctx.lineWidth = lw;
    ctx.strokeStyle = S.edge;
    ctx.globalAlpha = (em ? 0.35 : 1) * opt.linkOpacity;
    ctx.beginPath();
    for (i = 0; i < links.length && opt.showLinks; i++) {
      var l = links[i];
      if (!vis[l.s] || !vis[l.t]) continue;
      if (em && em.has(l.s) && em.has(l.t) && (center < 0 || l.s === center || l.t === center)) continue;
      var a = nodes[l.s], b = nodes[l.t];
      ctx.moveTo(a.x, a.y); ctx.lineTo(b.x, b.y);
    }
    ctx.stroke();
    if (em) {
      ctx.globalAlpha = 1; ctx.strokeStyle = S.edgeHi; ctx.lineWidth = 1.6 * this.opt.linkWidth / k;
      ctx.beginPath();
      for (i = 0; i < links.length; i++) {
        l = links[i];
        if (!vis[l.s] || !vis[l.t] || !em.has(l.s) || !em.has(l.t)) continue;
        if (center >= 0 && l.s !== center && l.t !== center) continue;
        a = nodes[l.s]; b = nodes[l.t];
        ctx.moveTo(a.x, a.y); ctx.lineTo(b.x, b.y);
      }
      ctx.stroke();
    }
    // nodes
    for (i = 0; i < nodes.length; i++) {
      if (!vis[i]) continue;
      var n = nodes[i], r = this.radius(n), dim = em && !em.has(i);
      var nsx = n.x * k + this.tx, nsy = n.y * k + this.ty, nm = (r * (glow ? 4 : 1) + 6) * k;
      if (nsx < -nm || nsx > this.w + nm || nsy < -nm || nsy > this.h + nm) continue;
      ctx.globalAlpha = dim ? 0.13 : 1;
      var col = (i === center || (matches && matches.has(i))) ? S.hi : this.color(n);
      if (glow && opt.glow > 0) {
        var gd = r * (2.2 + 2 * opt.glow) * (n.type === 'account' ? 1.35 : 1.6); // 1.6: galaxy bloom reads at default zoom
        ctx.drawImage(this.sprite(col), n.x - gd / 2, n.y - gd / 2, gd, gd);
        if (n.type === 'account') { gd *= 0.5; ctx.drawImage(this.sprite('#ffffff'), n.x - gd / 2, n.y - gd / 2, gd, gd); }
      } else {
        ctx.beginPath(); ctx.arc(n.x, n.y, r, 0, Math.PI * 2);
        ctx.fillStyle = col;
        ctx.fill();
      }
      if (S.outline) { ctx.lineWidth = 1.2 / k; ctx.strokeStyle = S.outline; ctx.stroke(); }
      if (opt.showIssues && n.issues.length && !dim) {
        // evidence ring goes on top of the glow, in normal blending so it stays hot pink-red
        if (glow) ctx.globalCompositeOperation = 'source-over';
        ctx.beginPath(); ctx.arc(n.x, n.y, r + (glow ? 4.2 : 3.2) / Math.sqrt(k), 0, Math.PI * 2);
        ctx.strokeStyle = S.issue; ctx.lineWidth = (glow ? 2 : 1.6) / k; ctx.stroke();
        if (glow) ctx.globalCompositeOperation = 'lighter';
      }
      if (i === this.selected) { ctx.beginPath(); ctx.arc(n.x, n.y, r + 4 / k, 0, Math.PI * 2); ctx.strokeStyle = S.ring; ctx.lineWidth = 2 / k; ctx.stroke(); }
    }
    if (glow) ctx.globalCompositeOperation = 'source-over';
    // labels: fade in with zoom; always for the emphasised neighbourhood and account hubs
    var fade = Math.max(0, Math.min(1, (k - this.opt.labels) / 0.5));
    ctx.textAlign = 'center'; ctx.textBaseline = 'top';
    // candidates as flat triplets (index, alpha, priority): emphasised > hubs > documents > rows and rates
    var cand = [];
    for (i = 0; i < nodes.length; i++) {
      if (!vis[i]) continue;
      n = nodes[i];
      var csx = n.x * k + this.tx, csy = n.y * k + this.ty;
      if (csx < -200 || csx > this.w + 200 || csy < -40 || csy > this.h + 40) continue; // off-screen labels are never drawn
      var inEm = em && em.has(i), hub = n.type === 'account' && k > 0.25;
      var a2 = inEm || i === this.selected ? 1 : hub ? 0.9 : this.opt.labelsAll ? (em ? 0.25 : 0.9) : (em ? 0 : fade * (n.type === 'row' ? 0.55 : 1));
      if (a2 <= 0.02) continue;
      cand.push(i, a2, inEm || i === this.selected ? 3 : hub ? 2 : (n.type === 'row' || n.type === 'fx') ? 0 : 1);
    }
    var order = [];
    for (var c3 = 0; c3 < cand.length; c3 += 3) order.push(c3);
    order.sort(function (a, b) { return cand[b + 2] - cand[a + 2] || cand[a] - cand[b]; });
    // dense views (glow styles, local graphs with every label on) skip lower-priority labels that would overlap
    var boxes = [], avoid = true;
    for (var oi = 0; oi < order.length; oi++) {
      var ci = order[oi];
      i = cand[ci]; a2 = cand[ci + 1]; n = nodes[i];
      hub = n.type === 'account' && k > 0.25;
      var fs = (hub ? 12.5 : 11.5) / k * Math.max(0.85, Math.min(1.2, Math.pow(k, 0.25)));
      var ly = n.y + this.radius(n) + 3 / k;
      if (avoid) {
        var lw2 = n.label.length * fs * 0.56, lh = fs * 1.2, ox = n.x - lw2 / 2, hit = false;
        if (cand[ci + 2] < 3) {
          for (var q2 = 0; q2 < boxes.length; q2 += 4) {
            if (ox < boxes[q2] + boxes[q2 + 2] && ox + lw2 > boxes[q2] && ly < boxes[q2 + 1] + boxes[q2 + 3] && ly + lh > boxes[q2 + 1]) { hit = true; break; }
          }
        }
        if (hit) continue;
        boxes.push(ox, ly, lw2, lh);
      }
      ctx.font = (hub || i === center ? '600 ' : '') + fs + 'px "Segoe UI Variable Text","Segoe UI",system-ui,sans-serif';
      ctx.globalAlpha = a2; ctx.fillStyle = S.text;
      ctx.fillText(n.label, n.x, ly);
    }
    ctx.restore();
  };

  // neighbourhood of some seed nodes (breadth-first), as a standalone graph with copied positions
  function subgraph(G, seeds, depth, maxNodes) {
    var keep = new Map(), queue = [], d = 0;
    seeds.forEach(function (i) { if (i !== undefined && !keep.has(i)) { keep.set(i, keep.size); queue.push(i); } });
    while (queue.length && d < depth) {
      var next = [];
      queue.forEach(function (i) {
        if (d > 0 && G.nodes[i].type === 'account') return; // an account hub reached by the walk is kept but not expanded
        G.nodes[i].nb.forEach(function (j) {
          if (keep.size >= maxNodes) return;
          var nj = G.nodes[j];
          if (nj.type === 'account' && d > 0) return; // do not expand through account hubs
          if (!keep.has(j)) { keep.set(j, keep.size); next.push(j); }
        });
      });
      queue = next; d++;
    }
    var nodes = [], index = new Map();
    keep.forEach(function (ni, oi) {
      var o = G.nodes[oi];
      nodes[ni] = { id: o.id, type: o.type, label: o.label, rec: o.rec, group: o.group, deg: 0, issues: o.issues.slice(), nb: [], x: o.x, y: o.y, vx: 0, vy: 0, fx: null, fy: null, src: oi };
      index.set(o.id, ni);
    });
    var links = [];
    G.links.forEach(function (l) {
      if (keep.has(l.s) && keep.has(l.t)) {
        var a = keep.get(l.s), b = keep.get(l.t);
        links.push({ s: a, t: b, kind: l.kind }); nodes[a].deg++; nodes[b].deg++; nodes[a].nb.push(b); nodes[b].nb.push(a);
      }
    });
    return { nodes: nodes, links: links, index: index, resolve: function (id) { var oi = G.resolve(id); return oi === undefined ? undefined : keep.get(oi); }, laidOut: false };
  }

  global.AuditGraph = { buildEpisodeGraph: buildEpisodeGraph, ForceGraph: ForceGraph, STYLES: STYLES, TYPES: TYPES, subgraph: subgraph, relabel: relabel };
})(window);
