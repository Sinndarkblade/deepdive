/**
 * DeepDive 3D Graph Engine
 * Force-directed graph rendering on HTML5 Canvas.
 * No DOM manipulation outside the canvas — UI callbacks are passed in.
 */

let graphState = {
  nodes: [],
  edges: [],
  colors: {},
  nodeMap: {},
  canvas: null,
  ctx: null,
  W: 0, H: 0,
  camRotX: 0.2, camRotY: 0, camZoom: 2.0,
  isDragging: false, lastMX: 0, lastMY: 0,
  autoRotate: true,
  selectedNodeId: null,
  collapsedNodes: new Set(),
};

// Callbacks set by the app
let onNodeClick = null;
let onNodeDoubleClick = null;
let onNodeHover = null;
let onNodeHoverEnd = null;

function _isDarkTheme() {
  const t = document.documentElement.getAttribute('data-theme') || 'aero';
  return t !== 'aero';
}

function initGraph(canvasId, nodes, edges, colors) {
  const gs = graphState;
  gs.nodes = nodes;
  gs.edges = edges;
  gs.colors = colors;
  gs.nodeMap = {};
  gs.nodes.forEach(n => gs.nodeMap[n.id] = n);

  gs.canvas = document.getElementById(canvasId);
  gs.ctx = gs.canvas.getContext('2d');

  _layoutNodes();
  _attachEvents();

  // Pre-simulate
  const steps = gs.nodes.length > 500 ? 150 : gs.nodes.length > 200 ? 300 : 500;
  for (let i = 0; i < steps; i++) _simulate();
  zoomFit();

  // Start render loop
  _render();
}

function _layoutNodes() {
  const gs = graphState;
  const spread = gs.nodes.length > 500 ? 2 : gs.nodes.length > 200 ? 1.2 : gs.nodes.length > 50 ? 0.8 : 0.5;
  gs.nodes.forEach((n, i) => {
    const a = (i / gs.nodes.length) * Math.PI * 2;
    const layer = n.depth || 0;
    const r = spread * (0.3 + layer * 0.5) + (Math.random() - 0.5) * spread * 0.3;
    n.x = Math.cos(a) * r;
    n.y = (layer - 1.5) * spread * 0.3 + (Math.random() - 0.5) * spread * 0.2;
    n.z = Math.sin(a) * r;
    n.vx = 0; n.vy = 0; n.vz = 0;
  });
}

function _simulate() {
  const gs = graphState;
  const repF = gs.nodes.length > 200 ? 0.015 : 0.02;

  for (let i = 0; i < gs.nodes.length; i++) {
    for (let j = i + 1; j < gs.nodes.length; j++) {
      let dx = gs.nodes[j].x - gs.nodes[i].x;
      let dy = gs.nodes[j].y - gs.nodes[i].y;
      let dz = gs.nodes[j].z - gs.nodes[i].z;
      let d = Math.sqrt(dx * dx + dy * dy + dz * dz) || 0.01;
      let f = repF / (d * d);
      gs.nodes[i].vx -= dx / d * f; gs.nodes[i].vy -= dy / d * f; gs.nodes[i].vz -= dz / d * f;
      gs.nodes[j].vx += dx / d * f; gs.nodes[j].vy += dy / d * f; gs.nodes[j].vz += dz / d * f;
    }
  }

  gs.edges.forEach(e => {
    const s = gs.nodeMap[e.from], t = gs.nodeMap[e.to];
    if (!s || !t) return;
    let dx = t.x - s.x, dy = t.y - s.y, dz = t.z - s.z;
    let d = Math.sqrt(dx * dx + dy * dy + dz * dz) || 0.01;
    let f = (d - 0.5) * 0.01;
    s.vx += dx / d * f; s.vy += dy / d * f; s.vz += dz / d * f;
    t.vx -= dx / d * f; t.vy -= dy / d * f; t.vz -= dz / d * f;
  });

  const g = gs.nodes.length > 500 ? 0.001 : 0.002;
  gs.nodes.forEach(n => {
    n.vx -= n.x * g; n.vy -= n.y * g; n.vz -= n.z * g;
    n.vx *= 0.9; n.vy *= 0.9; n.vz *= 0.9;
    n.x += n.vx; n.y += n.vy; n.z += n.vz;
  });
}

function _project(x, y, z) {
  const gs = graphState;
  let cx = x * Math.cos(gs.camRotY) - z * Math.sin(gs.camRotY);
  let cz = x * Math.sin(gs.camRotY) + z * Math.cos(gs.camRotY);
  let cy = y * Math.cos(gs.camRotX) - cz * Math.sin(gs.camRotX);
  cz = y * Math.sin(gs.camRotX) + cz * Math.cos(gs.camRotX);
  let scale = Math.min(gs.W, gs.H) * 0.4 / gs.camZoom;
  return { px: cx * scale + gs.W / 2, py: cy * scale + gs.H / 2, s: 1 / gs.camZoom, z: cz };
}

function _getVisible() {
  const gs = graphState;
  const vis = new Set(gs.nodes.map(n => n.id));
  gs.collapsedNodes.forEach(pid => {
    const p = gs.nodeMap[pid];
    if (!p) return;
    const pd = p.depth || 0;
    function hide(id) {
      gs.edges.forEach(e => {
        if (e.from === id) {
          const c = gs.nodeMap[e.to];
          if (c && (c.depth || 0) > pd) { vis.delete(e.to); hide(e.to); }
        }
      });
    }
    hide(pid);
  });
  return vis;
}

function _render() {
  const gs = graphState;
  if (gs.autoRotate) gs.camRotY += 0.001;

  gs.W = gs.canvas.width = gs.canvas.parentElement.clientWidth;
  gs.H = gs.canvas.height = gs.canvas.parentElement.clientHeight;

  gs.ctx.clearRect(0, 0, gs.W, gs.H);
  const proj = gs.nodes.map(n => ({ ...n, ..._project(n.x, n.y, n.z) })).sort((a, b) => b.z - a.z);
  const pm = {};
  proj.forEach(n => pm[n.id] = n);
  const vis = _getVisible();
  const sel = gs.selectedNodeId;

  // Resolve theme-aware colors from CSS vars
  const style = getComputedStyle(document.documentElement);
  const accent = style.getPropertyValue('--accent').trim() || '#2563EB';
  const edgeNormal = _isDarkTheme() ? 'rgba(255,255,255,0.10)' : 'rgba(0,0,0,0.12)';
  const edgeFade   = _isDarkTheme() ? 'rgba(255,255,255,0.03)' : 'rgba(0,0,0,0.05)';
  const labelSel   = style.getPropertyValue('--text').trim() || '#0F172A';
  const labelCon   = style.getPropertyValue('--text-secondary').trim() || '#334155';
  const labelDim   = style.getPropertyValue('--text-muted').trim() || '#94A3B8';

  // Draw edges
  gs.edges.forEach(e => {
    const s = pm[e.from], t = pm[e.to];
    if (!s || !t || !vis.has(e.from) || !vis.has(e.to)) return;
    const isSel = sel && (e.from === sel || e.to === sel);
    gs.ctx.beginPath();
    gs.ctx.moveTo(s.px, s.py);
    gs.ctx.lineTo(t.px, t.py);
    if (isSel) {
      gs.ctx.strokeStyle = accent + 'aa';
      gs.ctx.lineWidth = 2.5;
    } else if (sel) {
      gs.ctx.strokeStyle = edgeFade;
      gs.ctx.lineWidth = 0.5;
    } else {
      gs.ctx.strokeStyle = edgeNormal;
      gs.ctx.lineWidth = 1;
    }
    gs.ctx.stroke();
  });

  // Draw nodes
  proj.filter(n => vis.has(n.id)).forEach(n => {
    const r = Math.max(3, n.size * 3 / gs.camZoom);
    if (r < 0.5) return;
    const isSel = sel === n.id;
    const isCon = sel && gs.edges.some(e =>
      (e.from === sel && e.to === n.id) || (e.to === sel && e.from === n.id));

    gs.ctx.beginPath();
    gs.ctx.arc(n.px, n.py, r, 0, Math.PI * 2);

    if (isSel) {
      gs.ctx.fillStyle = n.color;
      gs.ctx.shadowColor = n.color;
      gs.ctx.shadowBlur = 30 / gs.camZoom;
      gs.ctx.strokeStyle = '#fff';
      gs.ctx.lineWidth = 3 / gs.camZoom;
      gs.ctx.stroke();
    } else if (isCon) {
      gs.ctx.fillStyle = n.color;
      gs.ctx.shadowColor = n.color;
      gs.ctx.shadowBlur = 12 / gs.camZoom;
    } else if (sel) {
      gs.ctx.fillStyle = n.color + '50';
      gs.ctx.shadowBlur = 0;
    } else {
      gs.ctx.fillStyle = n.color;
      gs.ctx.shadowColor = n.color;
      gs.ctx.shadowBlur = 4 / gs.camZoom;
    }
    gs.ctx.fill();
    gs.ctx.shadowBlur = 0;

    // Labels
    if (gs.camZoom < 5 || isSel || isCon) {
      const fs = Math.max(9, 13 / gs.camZoom);
      gs.ctx.font = (isSel ? '700 ' : '500 ') + fs + 'px Outfit,Inter,sans-serif';
      gs.ctx.textAlign = 'center';
      gs.ctx.fillStyle = isSel ? labelSel : isCon ? labelCon : labelDim;
      gs.ctx.fillText(n.label, n.px, n.py + r + fs + 3);
    }
  });

  requestAnimationFrame(_render);
}

function _hitTest(mx, my) {
  const gs = graphState;
  let hit = null, best = Infinity;
  gs.nodes.forEach(n => {
    const p = _project(n.x, n.y, n.z);
    const r = Math.max(3, n.size * 3 / gs.camZoom);
    const d = Math.hypot(mx - p.px, my - p.py);
    if (d < r + 8 && d < best) { hit = n; best = d; }
  });
  return hit;
}

function _attachEvents() {
  const gs = graphState;
  const canvas = gs.canvas;

  canvas.addEventListener('mousedown', e => {
    gs.isDragging = true;
    gs.lastMX = e.clientX;
    gs.lastMY = e.clientY;
    gs.autoRotate = false;
  });

  canvas.addEventListener('mousemove', e => {
    if (gs.isDragging) {
      gs.camRotY += (e.clientX - gs.lastMX) * 0.005;
      gs.camRotX += (e.clientY - gs.lastMY) * 0.005;
      gs.camRotX = Math.max(-1.4, Math.min(1.4, gs.camRotX));
      gs.lastMX = e.clientX;
      gs.lastMY = e.clientY;
      return;
    }
    const rect = canvas.getBoundingClientRect();
    const hov = _hitTest(e.clientX - rect.left, e.clientY - rect.top);
    if (hov && onNodeHover) {
      onNodeHover(hov, e.clientX, e.clientY);
    } else if (onNodeHoverEnd) {
      onNodeHoverEnd();
    }
  });

  canvas.addEventListener('mouseup', () => gs.isDragging = false);

  canvas.addEventListener('wheel', e => {
    gs.camZoom = e.deltaY > 0 ?
      Math.min(100, gs.camZoom * 1.3) :
      Math.max(0.1, gs.camZoom * 0.75);
    e.preventDefault();
  }, { passive: false });

  canvas.addEventListener('click', e => {
    const rect = canvas.getBoundingClientRect();
    const clicked = _hitTest(e.clientX - rect.left, e.clientY - rect.top);
    if (clicked && onNodeClick) {
      onNodeClick(clicked);
    }
  });

  canvas.addEventListener('dblclick', e => {
    const rect = canvas.getBoundingClientRect();
    const clicked = _hitTest(e.clientX - rect.left, e.clientY - rect.top);
    if (clicked && onNodeDoubleClick) {
      onNodeDoubleClick(clicked);
    } else {
      gs.autoRotate = !gs.autoRotate;
    }
  });
}

// ── Public API ──

function selectNode(id) {
  graphState.selectedNodeId = id;
  graphState.autoRotate = false;
}

function deselectNode() {
  graphState.selectedNodeId = null;
}

function toggleCollapse(id) {
  if (graphState.collapsedNodes.has(id)) {
    graphState.collapsedNodes.delete(id);
  } else {
    graphState.collapsedNodes.add(id);
  }
}

function isCollapsed(id) {
  return graphState.collapsedNodes.has(id);
}

function zoomIn() { graphState.camZoom = Math.max(0.15, graphState.camZoom * 0.6); }
function zoomOut() { graphState.camZoom = Math.min(80, graphState.camZoom * 1.5); }

function zoomFit() {
  const gs = graphState;
  let cx = 0, cy = 0, cz = 0;
  gs.nodes.forEach(n => { cx += n.x; cy += n.y; cz += n.z; });
  cx /= gs.nodes.length; cy /= gs.nodes.length; cz /= gs.nodes.length;
  gs.nodes.forEach(n => { n.x -= cx; n.y -= cy; n.z -= cz; });
  const dists = gs.nodes.map(n => Math.hypot(n.x, n.y, n.z)).sort((a, b) => a - b);
  gs.camZoom = (dists[Math.floor(dists.length * 0.9)] || 1) * 1.8 + 0.5;
}

function focusOnNode(id) {
  const gs = graphState;
  selectNode(id);
  gs.camZoom = 2;
  const n = gs.nodeMap[id];
  if (n) {
    gs.camRotY = Math.atan2(n.z, n.x);
  }
}

function getNode(id) {
  return graphState.nodeMap[id] || null;
}

function getEdgesFor(nodeId) {
  return graphState.edges.filter(e => e.from === nodeId || e.to === nodeId);
}

function getChildCount(nodeId) {
  return graphState.edges.filter(e => e.from === nodeId).length;
}
