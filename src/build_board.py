"""
DeepDive Board Builder — Luminous Precision cockpit UI.

Light theme, frosted white glass panels, OSINT tool integration.
"""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'core'))
from graph import InvestigationGraph

COLORS = {
    'person':     '#E11D48',
    'company':    '#2563EB',
    'location':   '#059669',
    'event':      '#D97706',
    'money':      '#7C3AED',
    'concept':    '#0891B2',
    'government': '#EA580C',
    'document':   '#6366F1',
    'unknown':    '#6B7280',
}

SERVER = 'http://localhost:8766'


def generate_css():
    return '''
@import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700;800;900&family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap');

*,*::before,*::after{margin:0;padding:0;box-sizing:border-box}

:root{
  --bg:#F0F2F5;
  --canvas-bg:#E4E8ED;
  --white:#FFFFFF;
  --glass:rgba(255,255,255,0.72);
  --glass-solid:rgba(255,255,255,0.88);
  --glass-border:rgba(0,0,0,0.07);
  --glass-border-hi:rgba(0,0,0,0.12);
  --glass-shadow:0 8px 32px rgba(0,0,0,0.08),0 1px 3px rgba(0,0,0,0.06);
  --glass-shadow-lg:0 20px 60px rgba(0,0,0,0.12),0 2px 6px rgba(0,0,0,0.06);
  --blur:blur(24px) saturate(180%);

  --text:#0F172A;
  --text-secondary:#475569;
  --text-muted:#94A3B8;
  --text-light:#CBD5E1;

  --blue:#2563EB;
  --blue-light:#DBEAFE;
  --blue-lighter:#EFF6FF;
  --blue-dark:#1D4ED8;
  --purple:#7C3AED;
  --purple-light:#EDE9FE;
  --green:#059669;
  --green-light:#D1FAE5;
  --red:#DC2626;
  --red-light:#FEE2E2;
  --amber:#D97706;
  --amber-light:#FEF3C7;
  --cyan:#0891B2;

  --font-display:'Outfit',sans-serif;
  --font-body:'Inter',-apple-system,BlinkMacSystemFont,sans-serif;
  --font-mono:'JetBrains Mono',monospace;

  --sidebar-w:340px;
  --detail-w:420px;
  --topbar-h:56px;
  --status-h:32px;
  --radius:14px;
  --radius-md:10px;
  --radius-sm:8px;
  --radius-xs:6px;
}

html,body{
  height:100%;overflow:hidden;
  background:var(--bg);
  font-family:var(--font-body);
  font-size:13px;line-height:1.55;
  color:var(--text);
  -webkit-font-smoothing:antialiased;
}

::-webkit-scrollbar{width:5px}
::-webkit-scrollbar-track{background:transparent}
::-webkit-scrollbar-thumb{background:rgba(0,0,0,0.12);border-radius:3px}
*{scrollbar-width:thin;scrollbar-color:rgba(0,0,0,0.12) transparent}

/* ═══════════════════════════════════════════
   VIEWPORT
   ═══════════════════════════════════════════ */

.viewport{
  position:relative;width:100vw;height:100vh;overflow:hidden;
  background:var(--bg);
}

canvas#graphCanvas{
  position:absolute;inset:0;width:100%;height:100%;z-index:1;cursor:grab;
  background:
    radial-gradient(circle at 30% 40%,rgba(37,99,235,0.04) 0%,transparent 50%),
    radial-gradient(circle at 70% 60%,rgba(124,58,237,0.03) 0%,transparent 50%),
    linear-gradient(rgba(0,0,0,0.02) 1px,transparent 1px),
    linear-gradient(90deg,rgba(0,0,0,0.02) 1px,transparent 1px),
    var(--canvas-bg);
  background-size:100% 100%,100% 100%,60px 60px,60px 60px;
}
canvas#graphCanvas:active{cursor:grabbing}

/* ═══════════════════════════════════════════
   GLASS BASE
   ═══════════════════════════════════════════ */

.glass{
  background:var(--glass-solid);
  backdrop-filter:var(--blur);
  -webkit-backdrop-filter:var(--blur);
  border:1px solid var(--glass-border);
  border-radius:var(--radius);
  box-shadow:var(--glass-shadow);
}

/* ═══════════════════════════════════════════
   TOP BAR
   ═══════════════════════════════════════════ */

.topbar{
  position:absolute;top:10px;left:10px;right:10px;
  height:var(--topbar-h);display:flex;align-items:center;
  gap:12px;padding:0 20px;z-index:20;
}

.topbar-brand{
  font-family:var(--font-display);font-weight:900;font-size:18px;
  letter-spacing:1px;
  background:linear-gradient(135deg,var(--blue),var(--purple));
  -webkit-background-clip:text;-webkit-text-fill-color:transparent;
  background-clip:text;
}

.topbar-sep{width:1px;height:24px;background:var(--glass-border)}

.topbar-select{
  padding:8px 32px 8px 12px;
  background:var(--white);border:1px solid var(--glass-border-hi);
  color:var(--text);border-radius:var(--radius-xs);
  font-size:13px;font-family:var(--font-body);font-weight:500;
  appearance:none;cursor:pointer;transition:all .2s;max-width:260px;
  background-image:url('data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="%2364748B" stroke-width="2"><polyline points="6 9 12 15 18 9"/></svg>');
  background-repeat:no-repeat;background-position:right 10px center;
}
.topbar-select:hover{border-color:var(--blue);box-shadow:0 0 0 3px var(--blue-light)}
.topbar-select:focus{outline:none;border-color:var(--blue);box-shadow:0 0 0 3px var(--blue-light)}
.topbar-select option{background:var(--white);color:var(--text)}

.topbar-actions{margin-left:auto;display:flex;gap:6px}

.topbar-btn{
  padding:9px 18px;background:var(--white);
  border:1px solid var(--glass-border-hi);color:var(--text);
  border-radius:var(--radius-sm);cursor:pointer;
  font-size:13px;font-family:var(--font-body);font-weight:600;
  transition:all .2s;white-space:nowrap;
}
.topbar-btn:hover{
  border-color:var(--blue);color:var(--blue);
  box-shadow:0 2px 8px rgba(37,99,235,0.12);
  transform:translateY(-1px);
}

/* ═══════════════════════════════════════════
   SIDEBAR
   ═══════════════════════════════════════════ */

.sidebar{
  position:absolute;top:78px;left:10px;bottom:52px;
  width:var(--sidebar-w);display:flex;flex-direction:column;
  overflow:hidden;z-index:10;
  transition:transform .4s cubic-bezier(.16,1,.3,1),opacity .3s;
}
.sidebar.collapsed{transform:translateX(calc(-1 * var(--sidebar-w) - 24px));opacity:0;pointer-events:none}

.sidebar-header{
  padding:20px 22px 16px;
  border-bottom:1px solid var(--glass-border);flex-shrink:0;
}
.sidebar-title{
  font-family:var(--font-display);font-size:18px;font-weight:700;
  color:var(--text);margin-bottom:4px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;
}
.sidebar-meta{display:flex;gap:14px;font-size:11px;font-family:var(--font-mono);color:var(--text-muted)}
.sidebar-meta b{color:var(--blue);font-weight:600}

.sidebar-body{flex:1;overflow-y:auto;padding-bottom:10px}

/* Section */
.section{border-bottom:1px solid var(--glass-border)}
.section-header{
  padding:12px 22px;font-size:11px;font-weight:700;
  color:var(--text-secondary);text-transform:uppercase;letter-spacing:1.2px;
  cursor:pointer;display:flex;justify-content:space-between;align-items:center;
  user-select:none;transition:all .15s;
  font-family:var(--font-body);
}
.section-header:hover{color:var(--blue);background:var(--blue-lighter)}
.section-header .chv{font-size:10px;color:var(--text-muted);transition:transform .25s}
.section-header.open .chv{transform:rotate(180deg)}
.section-body{padding:8px 22px 16px;display:none}
.section-body.open{display:block}

/* Input */
.input-field{
  width:100%;padding:10px 14px;
  background:var(--white);border:1.5px solid var(--glass-border-hi);
  border-radius:var(--radius-xs);color:var(--text);
  font-size:13px;font-family:var(--font-body);transition:all .2s;
}
.input-field:focus{outline:none;border-color:var(--blue);box-shadow:0 0 0 3px var(--blue-light)}
.input-field::placeholder{color:var(--text-muted)}

/* Buttons */
.btn{
  display:inline-flex;align-items:center;justify-content:center;gap:8px;
  padding:10px 18px;border-radius:var(--radius-xs);
  font-size:13px;font-family:var(--font-body);font-weight:600;
  cursor:pointer;transition:all .2s;border:none;white-space:nowrap;
}
.btn-primary{
  width:100%;
  background:linear-gradient(135deg,var(--blue),var(--blue-dark));
  color:#fff;font-weight:700;
  box-shadow:0 4px 14px rgba(37,99,235,0.3);
}
.btn-primary:hover{box-shadow:0 6px 20px rgba(37,99,235,0.4);transform:translateY(-1px);filter:brightness(1.08)}

.btn-secondary{
  width:100%;background:var(--white);
  border:1.5px solid var(--glass-border-hi);color:var(--text);
}
.btn-secondary:hover{border-color:var(--blue);color:var(--blue);background:var(--blue-lighter)}

.btn-danger{
  width:100%;background:var(--red-light);
  border:1.5px solid rgba(220,38,38,0.2);color:var(--red);font-weight:700;
}
.btn-danger:hover{background:#fecaca;border-color:rgba(220,38,38,0.4)}

.btn-sm{padding:7px 14px;font-size:12px}
.btn-icon{
  width:40px;height:40px;padding:0;background:var(--white);
  border:1.5px solid var(--glass-border-hi);border-radius:var(--radius-xs);
  color:var(--text-secondary);cursor:pointer;display:flex;align-items:center;
  justify-content:center;font-size:16px;transition:all .2s;
}
.btn-icon:hover{border-color:var(--blue);color:var(--blue);background:var(--blue-lighter)}

/* Entity cards */
.entity-card{
  padding:10px 14px;margin:3px 0;cursor:pointer;
  border-left:3px solid var(--text-light);
  border-radius:0 var(--radius-xs) var(--radius-xs) 0;
  transition:all .18s;background:transparent;
}
.entity-card:hover{background:var(--blue-lighter);border-left-color:var(--blue);transform:translateX(4px)}
.entity-card.selected{background:var(--blue-light);border-left-color:var(--blue)}
.entity-name{font-size:13px;font-weight:600}
.entity-type{font-size:10px;font-family:var(--font-mono);color:var(--text-muted);text-transform:uppercase;letter-spacing:.6px;margin-top:1px}

/* Legend */
.legend{display:flex;flex-wrap:wrap;gap:10px}
.legend-item{display:flex;align-items:center;gap:5px;font-size:12px;color:var(--text-secondary)}
.legend-dot{width:10px;height:10px;border-radius:50%}

/* ═══════════════════════════════════════════
   OSINT TOOLS — The new stuff
   ═══════════════════════════════════════════ */

.osint-grid{
  display:grid;grid-template-columns:1fr 1fr;gap:6px;margin-top:4px;
}
.osint-tool{
  display:flex;flex-direction:column;align-items:center;gap:4px;
  padding:12px 8px;background:var(--white);
  border:1.5px solid var(--glass-border);border-radius:var(--radius-sm);
  cursor:pointer;transition:all .2s;text-align:center;
}
.osint-tool:hover{
  border-color:var(--blue);background:var(--blue-lighter);
  transform:translateY(-2px);box-shadow:0 4px 12px rgba(37,99,235,0.1);
}
.osint-tool.active{border-color:var(--blue);background:var(--blue-light)}
.osint-icon{font-size:22px;line-height:1}
.osint-label{font-size:10px;font-weight:700;color:var(--text-secondary);text-transform:uppercase;letter-spacing:.5px}

.osint-result{
  padding:8px 12px;margin:3px 0;
  background:var(--white);border:1px solid var(--glass-border);
  border-radius:var(--radius-xs);font-size:12px;
  transition:all .15s;
}
.osint-result:hover{border-color:var(--blue-dark)}
.osint-result-title{font-weight:600;color:var(--text);margin-bottom:2px}
.osint-result-meta{font-size:10px;font-family:var(--font-mono);color:var(--text-muted)}

/* ═══════════════════════════════════════════
   DETAIL PANEL
   ═══════════════════════════════════════════ */

.detail-panel{
  position:absolute;top:78px;right:10px;bottom:52px;
  width:var(--detail-w);display:none;flex-direction:column;
  overflow:hidden;z-index:15;
}
.detail-panel.open{display:flex;animation:slideIn .35s cubic-bezier(.16,1,.3,1)}
@keyframes slideIn{from{transform:translateX(50px);opacity:0}to{transform:translateX(0);opacity:1}}

.detail-header{
  padding:18px 22px;border-bottom:1px solid var(--glass-border);
  display:flex;align-items:flex-start;justify-content:space-between;flex-shrink:0;
}
.detail-header-label{font-size:10px;font-weight:700;color:var(--text-muted);text-transform:uppercase;letter-spacing:1.5px}
.detail-close{
  width:32px;height:32px;background:var(--white);
  border:1.5px solid var(--glass-border-hi);border-radius:var(--radius-xs);
  color:var(--text-muted);cursor:pointer;display:flex;align-items:center;
  justify-content:center;font-size:16px;transition:all .2s;
}
.detail-close:hover{border-color:var(--red);color:var(--red);background:var(--red-light)}

.detail-body{flex:1;overflow-y:auto;padding:20px 22px}

.detail-row{
  display:flex;justify-content:space-between;align-items:center;
  padding:9px 0;border-bottom:1px solid var(--glass-border);font-size:13px;
}
.detail-key{color:var(--text-muted);font-family:var(--font-mono);font-size:11px}
.detail-value{color:var(--text);font-weight:600;text-align:right;max-width:55%}

.detail-actions{display:flex;flex-direction:column;gap:8px;margin:18px 0}
.detail-action-row{display:flex;gap:8px}

.detail-section-title{
  font-family:var(--font-display);font-size:12px;font-weight:700;
  color:var(--text-secondary);text-transform:uppercase;letter-spacing:1px;
  margin:20px 0 10px;padding-bottom:8px;border-bottom:1px solid var(--glass-border);
}

/* ═══════════════════════════════════════════
   STATUS BAR
   ═══════════════════════════════════════════ */

.statusbar{
  position:absolute;bottom:10px;left:10px;right:10px;
  height:var(--status-h);display:flex;align-items:center;
  padding:0 20px;gap:16px;z-index:10;
  font-size:11px;font-family:var(--font-mono);color:var(--text-muted);
}
.status-dot{
  width:8px;height:8px;border-radius:50%;background:var(--green);
  box-shadow:0 0 8px var(--green);
  animation:pulse 2.5s ease-in-out infinite;
}
@keyframes pulse{0%,100%{opacity:.5}50%{opacity:1}}
.status-sep{color:var(--text-light)}

/* ═══════════════════════════════════════════
   ZOOM / TOOLTIP / BANNER
   ═══════════════════════════════════════════ */

.zoom-controls{position:absolute;bottom:54px;right:18px;display:flex;flex-direction:column;gap:5px;z-index:10}
.zoom-btn{
  width:40px;height:40px;background:var(--glass-solid);
  backdrop-filter:var(--blur);border:1px solid var(--glass-border-hi);
  border-radius:var(--radius-sm);color:var(--text-secondary);cursor:pointer;
  display:flex;align-items:center;justify-content:center;
  font-size:18px;font-family:var(--font-mono);transition:all .2s;
}
.zoom-btn:hover{background:var(--white);color:var(--blue);border-color:var(--blue);transform:scale(1.05)}

.tooltip{
  display:none;position:absolute;
  background:var(--white);border:1px solid var(--glass-border-hi);
  border-radius:var(--radius-sm);padding:12px 16px;font-size:13px;
  pointer-events:none;z-index:30;max-width:300px;
  box-shadow:var(--glass-shadow-lg);
}
.tooltip-name{font-family:var(--font-display);font-weight:700;font-size:14px;margin-bottom:3px}
.tooltip-meta{font-size:10px;font-family:var(--font-mono);color:var(--text-muted)}

.banner{
  display:none;position:absolute;bottom:54px;left:50%;transform:translateX(-50%);
  padding:14px 28px;z-index:25;font-size:14px;color:var(--text);
  max-width:650px;text-align:center;
  background:var(--white);border:1px solid var(--glass-border-hi);
  border-radius:var(--radius);box-shadow:var(--glass-shadow-lg);
  animation:bannerIn .35s cubic-bezier(.16,1,.3,1);
}
.banner.visible{display:block}
@keyframes bannerIn{from{transform:translateX(-50%) translateY(24px);opacity:0}to{transform:translateX(-50%) translateY(0);opacity:1}}

/* Interview */
.interview-panel{display:none;margin-top:10px;padding:14px;background:var(--white);border:1.5px solid var(--glass-border-hi);border-radius:var(--radius-sm)}
.interview-panel.open{display:block}
.interview-label{font-size:12px;font-weight:700;color:var(--blue);margin-bottom:8px;font-family:var(--font-display)}
.interview-checks{max-height:180px;overflow-y:auto;font-size:12px}
.interview-checks label{display:block;padding:3px 0;color:var(--text-secondary);cursor:pointer}
.interview-checks label:hover{color:var(--text)}
.interview-cat{font-weight:700;color:var(--blue);margin-top:8px;font-size:10px;text-transform:uppercase;letter-spacing:.8px}

.mode-group{display:flex;gap:2px;margin-top:10px;background:var(--bg);border-radius:var(--radius-xs);padding:3px}
.mode-btn{
  flex:1;padding:7px;background:transparent;border:none;border-radius:5px;
  color:var(--text-muted);cursor:pointer;font-size:12px;font-family:var(--font-body);
  font-weight:600;transition:all .2s;
}
.mode-btn:hover{color:var(--text-secondary)}
.mode-btn.active{background:var(--white);color:var(--blue);box-shadow:0 1px 4px rgba(0,0,0,0.08)}

/* Cards */
.finding-card{padding:8px 12px;margin:3px 0;background:var(--green-light);border-left:3px solid var(--green);border-radius:0 var(--radius-xs) var(--radius-xs) 0;font-size:12px;color:var(--text-secondary)}
.gap-card{padding:8px 12px;margin:3px 0;background:var(--red-light);border-left:3px solid var(--red);border-radius:0 var(--radius-xs) var(--radius-xs) 0;font-size:12px}
.gap-card.researched{border-left-color:var(--green);background:var(--green-light)}
.report-badge{padding:10px 12px;border-radius:var(--radius-xs);font-size:12px;margin:10px 0}
.report-badge.stale{background:var(--amber-light);border:1px solid rgba(217,119,6,.2);color:var(--amber)}
.report-badge.current{background:var(--green-light);border:1px solid rgba(5,150,105,.2);color:var(--green)}
.note-card{padding:8px 12px;margin:3px 0;background:var(--blue-lighter);border-left:3px solid var(--blue);border-radius:0 var(--radius-xs) var(--radius-xs) 0;font-size:12px;color:var(--text-secondary)}

/* File browser modal */
.modal-overlay{display:none;position:fixed;inset:0;background:rgba(0,0,0,0.25);backdrop-filter:blur(8px);z-index:100;align-items:center;justify-content:center}
.modal-overlay.open{display:flex}
.modal{width:580px;max-height:70vh;background:var(--white);border:1px solid var(--glass-border-hi);border-radius:var(--radius);box-shadow:0 24px 80px rgba(0,0,0,0.15);overflow:hidden}
.modal-header{padding:18px 24px;border-bottom:1px solid var(--glass-border);display:flex;justify-content:space-between;align-items:center}
.modal-title{font-family:var(--font-display);font-size:16px;font-weight:700;color:var(--text)}
.modal-body{padding:16px 24px;max-height:50vh;overflow-y:auto}
.modal-footer{padding:14px 24px;border-top:1px solid var(--glass-border);display:flex;gap:8px;justify-content:flex-end}
.file-item{display:flex;align-items:center;gap:10px;padding:10px 12px;border-radius:var(--radius-xs);cursor:pointer;transition:all .15s;font-size:13px;color:var(--text)}
.file-item:hover{background:var(--blue-lighter)}
.file-item.selected{background:var(--blue-light);border:1px solid rgba(37,99,235,.3)}
.file-icon{font-size:18px;width:24px;text-align:center}
.file-name{font-weight:500}
.path-breadcrumb{display:flex;align-items:center;gap:4px;padding:10px 14px;background:var(--bg);border:1px solid var(--glass-border);border-radius:var(--radius-xs);margin-bottom:12px;font-family:var(--font-mono);font-size:12px;color:var(--text-secondary);overflow-x:auto;white-space:nowrap}
.path-segment{cursor:pointer;color:var(--blue);transition:color .15s}
.path-segment:hover{color:var(--blue-dark)}

/* OSINT checkboxes */
.osint-checks{display:flex;flex-direction:column;gap:1px}
.osint-check{display:flex;align-items:center;gap:6px;padding:4px 8px;font-size:12px;color:var(--text-secondary);cursor:pointer;border-radius:var(--radius-xs);transition:all .15s}
.osint-check:hover{background:var(--blue-lighter);color:var(--text)}
.osint-check input[type="checkbox"]{width:14px;height:14px;accent-color:var(--blue);cursor:pointer;flex-shrink:0}
.osint-icon-sm{font-size:14px;width:20px;text-align:center;flex-shrink:0}
.feed-preview{text-decoration:none;color:inherit;cursor:pointer;flex:1}
.feed-preview:hover{color:var(--blue);text-decoration:underline}

/* Feed preview panel */
.feed-panel{display:none;position:absolute;top:78px;left:calc(var(--sidebar-w) + 20px);bottom:52px;width:420px;z-index:12;flex-direction:column;overflow:hidden}
.feed-panel.open{display:flex;animation:slideIn .3s cubic-bezier(.16,1,.3,1)}
.feed-panel-header{padding:14px 18px;border-bottom:1px solid var(--glass-border);display:flex;justify-content:space-between;align-items:center;flex-shrink:0}
.feed-panel-title{font-family:var(--font-display);font-size:14px;font-weight:700;color:var(--text)}
.feed-panel-body{flex:1;overflow-y:auto;padding:12px 18px}
.feed-item{padding:10px 12px;margin:4px 0;background:var(--white);border:1px solid var(--glass-border);border-radius:var(--radius-xs);font-size:12px;transition:all .15s}
.feed-item:hover{border-color:var(--blue)}
.feed-item-title{font-weight:600;color:var(--text);margin-bottom:2px}
.feed-item-meta{font-size:10px;font-family:var(--font-mono);color:var(--text-muted)}
.feed-item-extra{font-size:10px;color:var(--text-secondary);margin-top:2px}
.feed-item-link{font-size:10px;color:var(--blue);word-break:break-all}
.feed-loading{display:flex;align-items:center;justify-content:center;padding:40px;color:var(--text-muted);font-size:13px}

@media print{.sidebar,.detail-panel,.topbar,.statusbar,.zoom-controls,.banner,.tooltip,.modal-overlay,.feed-panel{display:none!important}}
'''


def generate_js(nodes_json, edges_json, colors_json, mode, board_title):
    return f"""
const NODES={nodes_json};
const EDGES={edges_json};
const COLORS={colors_json};
const MODE='{mode}';
const SERVER='{SERVER}';
const nodeMap={{}};
NODES.forEach(n=>nodeMap[n.id]=n);

const canvas=document.getElementById('graphCanvas');
const ctx=canvas.getContext('2d');
let W,H,camRotX=0.2,camRotY=0,camZoom=2.0;
let isDragging=false,lastMX=0,lastMY=0,autoRotate=true,selectedNodeId=null;
let collapsedNodes=new Set();

function resize(){{W=canvas.width=window.innerWidth;H=canvas.height=window.innerHeight}}
window.addEventListener('resize',resize);resize();

const spread=NODES.length>500?2:NODES.length>200?1.2:NODES.length>50?.8:.5;
NODES.forEach((n,i)=>{{
  const a=(i/NODES.length)*Math.PI*2,layer=n.depth||0;
  const r=spread*(.3+layer*.5)+(Math.random()-.5)*spread*.3;
  n.x=Math.cos(a)*r;n.y=(layer-1.5)*spread*.3+(Math.random()-.5)*spread*.2;
  n.z=Math.sin(a)*r;n.vx=0;n.vy=0;n.vz=0;
}});

const repF=NODES.length>200?.015:.02;
function simulate(){{
  for(let i=0;i<NODES.length;i++)for(let j=i+1;j<NODES.length;j++){{
    let dx=NODES[j].x-NODES[i].x,dy=NODES[j].y-NODES[i].y,dz=NODES[j].z-NODES[i].z;
    let d=Math.sqrt(dx*dx+dy*dy+dz*dz)||.01,f=repF/(d*d);
    NODES[i].vx-=dx/d*f;NODES[i].vy-=dy/d*f;NODES[i].vz-=dz/d*f;
    NODES[j].vx+=dx/d*f;NODES[j].vy+=dy/d*f;NODES[j].vz+=dz/d*f;
  }}
  EDGES.forEach(e=>{{
    const s=nodeMap[e.from],t=nodeMap[e.to];if(!s||!t)return;
    let dx=t.x-s.x,dy=t.y-s.y,dz=t.z-s.z;
    let d=Math.sqrt(dx*dx+dy*dy+dz*dz)||.01,f=(d-.5)*.01;
    s.vx+=dx/d*f;s.vy+=dy/d*f;s.vz+=dz/d*f;
    t.vx-=dx/d*f;t.vy-=dy/d*f;t.vz-=dz/d*f;
  }});
  const g=NODES.length>500?.001:.002;
  NODES.forEach(n=>{{n.vx-=n.x*g;n.vy-=n.y*g;n.vz-=n.z*g;n.vx*=.9;n.vy*=.9;n.vz*=.9;n.x+=n.vx;n.y+=n.vy;n.z+=n.vz}});
}}

function project(x,y,z){{
  let cx=x*Math.cos(camRotY)-z*Math.sin(camRotY);
  let cz=x*Math.sin(camRotY)+z*Math.cos(camRotY);
  let cy=y*Math.cos(camRotX)-cz*Math.sin(camRotX);
  cz=y*Math.sin(camRotX)+cz*Math.cos(camRotX);
  let scale=Math.min(W,H)*.4/camZoom;
  return{{px:cx*scale+W/2,py:cy*scale+H/2,s:1/camZoom,z:cz}};
}}

function getVisible(){{
  const vis=new Set(NODES.map(n=>n.id));
  collapsedNodes.forEach(pid=>{{const p=nodeMap[pid];if(!p)return;const pd=p.depth||0;
    function hide(id){{EDGES.forEach(e=>{{if(e.from===id){{const c=nodeMap[e.to];if(c&&(c.depth||0)>pd){{vis.delete(e.to);hide(e.to)}}}}}})}};hide(pid)}});
  return vis;
}}

function render(){{
  if(autoRotate)camRotY+=.001;
  ctx.clearRect(0,0,W,H);
  const proj=NODES.map(n=>({{...n,...project(n.x,n.y,n.z)}})).sort((a,b)=>b.z-a.z);
  const pm={{}};proj.forEach(n=>pm[n.id]=n);
  const vis=getVisible();

  EDGES.forEach(e=>{{
    const s=pm[e.from],t=pm[e.to];if(!s||!t||!vis.has(e.from)||!vis.has(e.to))return;
    const sel=selectedNodeId&&(e.from===selectedNodeId||e.to===selectedNodeId);
    ctx.beginPath();ctx.moveTo(s.px,s.py);ctx.lineTo(t.px,t.py);
    if(sel){{ctx.strokeStyle='rgba(37,99,235,0.5)';ctx.lineWidth=2.5}}
    else if(selectedNodeId){{ctx.strokeStyle='rgba(0,0,0,0.06)';ctx.lineWidth=.5}}
    else{{ctx.strokeStyle='rgba(0,0,0,0.12)';ctx.lineWidth=1}}
    ctx.stroke();
  }});

  proj.filter(n=>vis.has(n.id)).forEach(n=>{{
    const r=Math.max(3,n.size*3/camZoom);if(r<.5)return;
    const isSel=selectedNodeId===n.id;
    const isCon=selectedNodeId&&EDGES.some(e=>(e.from===selectedNodeId&&e.to===n.id)||(e.to===selectedNodeId&&e.from===n.id));
    ctx.beginPath();ctx.arc(n.px,n.py,r,0,Math.PI*2);
    if(isSel){{ctx.fillStyle=n.color;ctx.shadowColor=n.color;ctx.shadowBlur=30/camZoom;
      ctx.strokeStyle='#fff';ctx.lineWidth=3/camZoom;ctx.stroke()}}
    else if(isCon){{ctx.fillStyle=n.color;ctx.shadowColor=n.color;ctx.shadowBlur=12/camZoom}}
    else if(selectedNodeId){{ctx.fillStyle=n.color+'50';ctx.shadowBlur=0}}
    else{{ctx.fillStyle=n.color;ctx.shadowColor=n.color;ctx.shadowBlur=4/camZoom}}
    ctx.fill();ctx.shadowBlur=0;

    if(camZoom<5||isSel||isCon){{
      const fs=Math.max(9,13/camZoom);
      ctx.font=(isSel?'700 ':'500 ')+fs+'px Outfit,Inter,sans-serif';
      ctx.textAlign='center';
      ctx.fillStyle=isSel?'#0F172A':isCon?'#334155':'#94A3B8';
      ctx.fillText(n.label,n.px,n.py+r+fs+3);
    }}
  }});
  requestAnimationFrame(render);
}}

function hitTest(mx,my){{
  let hit=null,best=Infinity;
  NODES.forEach(n=>{{const p=project(n.x,n.y,n.z),r=Math.max(3,n.size*3/camZoom),d=Math.hypot(mx-p.px,my-p.py);if(d<r+8&&d<best){{hit=n;best=d}}}});
  return hit;
}}

canvas.addEventListener('mousedown',e=>{{isDragging=true;lastMX=e.clientX;lastMY=e.clientY;autoRotate=false}});
canvas.addEventListener('mousemove',e=>{{
  if(isDragging){{camRotY+=(e.clientX-lastMX)*.005;camRotX+=(e.clientY-lastMY)*.005;camRotX=Math.max(-1.4,Math.min(1.4,camRotX));lastMX=e.clientX;lastMY=e.clientY;return}}
  const rect=canvas.getBoundingClientRect(),hov=hitTest(e.clientX-rect.left,e.clientY-rect.top);
  const tt=document.getElementById('tooltip');
  if(hov){{
    tt.style.display='block';tt.style.left=(e.clientX+16)+'px';tt.style.top=(e.clientY+16)+'px';
    let h='<div class="tooltip-name" style="color:'+COLORS[hov.type]+'">'+hov.label+'</div>';
    h+='<div class="tooltip-meta">'+hov.type+' &middot; '+hov.connections+' connections</div>';
    if(hov.metadata)Object.entries(hov.metadata).slice(0,3).forEach(([k,v])=>{{if(k!=='notes'&&k!=='pinned')h+='<div class="tooltip-meta">'+k+': '+String(v).substring(0,60)+'</div>'}});
    tt.innerHTML=h;
  }}else tt.style.display='none';
}});
canvas.addEventListener('mouseup',()=>isDragging=false);
canvas.addEventListener('wheel',e=>{{camZoom=e.deltaY>0?Math.min(100,camZoom*1.3):Math.max(.1,camZoom*.75);e.preventDefault()}},{{passive:false}});
canvas.addEventListener('click',e=>{{
  const rect=canvas.getBoundingClientRect(),clicked=hitTest(e.clientX-rect.left,e.clientY-rect.top);
  if(clicked){{if(selectedNodeId===clicked.id){{selectedNodeId=null;closeDetailPanel()}}else{{selectedNodeId=clicked.id;showDetailPanel(clicked);addToRecent(clicked.id,clicked.label,clicked.type)}}}}
}});
canvas.addEventListener('dblclick',e=>{{
  const rect=canvas.getBoundingClientRect(),clicked=hitTest(e.clientX-rect.left,e.clientY-rect.top);
  if(clicked){{toggleCollapse(clicked.id);selectedNodeId=clicked.id;showDetailPanel(clicked)}}else autoRotate=!autoRotate;
}});

function zoomIn(){{camZoom=Math.max(.15,camZoom*.6)}}
function zoomOut(){{camZoom=Math.min(80,camZoom*1.5)}}
function zoomFit(){{
  let cx=0,cy=0,cz=0;NODES.forEach(n=>{{cx+=n.x;cy+=n.y;cz+=n.z}});
  cx/=NODES.length;cy/=NODES.length;cz/=NODES.length;
  NODES.forEach(n=>{{n.x-=cx;n.y-=cy;n.z-=cz}});
  const dists=NODES.map(n=>Math.hypot(n.x,n.y,n.z)).sort((a,b)=>a-b);
  camZoom=(dists[Math.floor(dists.length*.9)]||1)*1.8+.5;
}}
function toggleCollapse(id){{if(collapsedNodes.has(id))collapsedNodes.delete(id);else collapsedNodes.add(id);if(nodeMap[id])showDetailPanel(nodeMap[id])}}

// ── Detail Panel ──
function showDetailPanel(node){{
  const panel=document.querySelector('.detail-panel'),body=document.querySelector('.detail-body');
  const conns=EDGES.filter(e=>e.from===node.id||e.to===node.id);
  let h='<div style="margin-bottom:16px"><div style="font-family:var(--font-display);font-size:22px;font-weight:800;color:'+COLORS[node.type]+'">'+node.label+'</div>';
  h+='<div style="font-size:11px;font-family:var(--font-mono);color:var(--text-muted);margin-top:3px;letter-spacing:1px">'+node.type.toUpperCase()+'</div></div>';
  h+='<div class="detail-row"><span class="detail-key">Connections</span><span class="detail-value">'+conns.length+'</span></div>';
  h+='<div class="detail-row"><span class="detail-key">Depth</span><span class="detail-value">'+(node.depth||0)+'</span></div>';
  if(node.metadata)Object.entries(node.metadata).forEach(([k,v])=>{{if(k!=='notes'&&k!=='pinned')h+='<div class="detail-row"><span class="detail-key">'+k+'</span><span class="detail-value">'+v+'</span></div>'}});
  const cc=EDGES.filter(e=>e.from===node.id).length;
  if(cc>0)h+='<button class="btn btn-secondary btn-sm" style="margin:12px 0 0" onclick="toggleCollapse(\\''+node.id+'\\')">'+(collapsedNodes.has(node.id)?'Expand':'Collapse')+' '+cc+' nodes</button>';
  const ri=nodeReports[node.id];
  if(ri){{const stale=conns.length>ri.conn_count;h+='<div class="report-badge '+(stale?'stale':'current')+'">'+(stale?'Report outdated':'Up to date')+' <a href="file://'+ri.path+'" target="_blank" style="color:var(--blue);margin-left:8px">Open</a></div>'}}
  h+='<div class="detail-actions">';
  h+='<button class="btn btn-primary" onclick="diveDeeper(\\''+node.id+'\\',\\''+node.label.replace(/'/g,"")+'\\')">Dive Deeper</button>';
  h+='<button class="btn btn-secondary" onclick="investigateNode(\\''+node.id+'\\',\\''+node.label.replace(/'/g,"")+'\\',\\''+node.type+'\\','+conns.length+')">Full Investigation</button>';
  h+='<button class="btn btn-secondary" onclick="generateReport(\\''+node.id+'\\',\\''+node.label.replace(/'/g,"")+'\\')">'+( ri?'Update':'Generate')+' Report</button>';
  // OSINT tool buttons for this entity
  h+='<div style="margin-top:4px;font-size:10px;font-weight:700;color:var(--text-muted);text-transform:uppercase;letter-spacing:1px">OSINT Tools</div>';
  const nl=node.label.replace(/'/g,"");
  h+='<div class="detail-action-row"><button class="btn btn-sm btn-secondary" style="flex:1" onclick="runOsintWithPreview(\\'timeline\\',\\''+nl+'\\')">Timeline</button>';
  h+='<button class="btn btn-sm btn-secondary" style="flex:1" onclick="runOsintWithPreview(\\'money\\',\\''+nl+'\\')">Money Flow</button></div>';
  h+='<div class="detail-action-row"><button class="btn btn-sm btn-secondary" style="flex:1" onclick="runOsintWithPreview(\\'social\\',\\''+nl+'\\')">Social Media</button>';
  h+='<button class="btn btn-sm btn-secondary" style="flex:1" onclick="runOsintWithPreview(\\'wayback\\',\\''+nl+'\\')">Wayback</button></div>';
  h+='<div class="detail-action-row"><button class="btn btn-sm btn-secondary" style="flex:1" onclick="previewFeed(\\'darkweb\\')">Dark Web</button>';
  h+='<button class="btn btn-sm btn-secondary" style="flex:1" onclick="previewFeed(\\'feeds\\')">All Feeds</button></div>';
  h+='<div class="detail-action-row">';
  const pin=node.metadata&&node.metadata.pinned;
  h+='<button class="btn btn-sm btn-secondary" style="flex:1" onclick="pinNode(\\''+node.id+'\\')">'+(pin?'Unpin':'Pin')+'</button>';
  h+='<button class="btn btn-sm btn-secondary" style="flex:1" onclick="addNodeNote(\\''+node.id+'\\')">Note</button>';
  h+='<button class="btn btn-sm btn-danger" style="flex:1" onclick="pruneNode(\\''+node.id+'\\',\\''+node.label.replace(/'/g,"")+'\\')">Remove</button></div></div>';
  if(node.metadata&&node.metadata.notes&&node.metadata.notes.length)node.metadata.notes.forEach(note=>{{h+='<div class="note-card">'+note+'</div>'}});
  h+='<div class="detail-section-title">Connections ('+conns.length+')</div>';
  conns.sort((a,b)=>b.confidence-a.confidence).forEach(c=>{{
    const oid=c.from===node.id?c.to:c.from,o=nodeMap[oid];if(!o)return;
    h+='<div class="entity-card" onclick="focusNode(\\''+oid+'\\')"><div class="entity-name" style="color:'+COLORS[o.type]+'">'+o.label+'</div><div class="entity-type">'+c.label+' &middot; '+Math.round(c.confidence*100)+'%</div></div>';
  }});
  body.innerHTML=h;panel.classList.add('open');
}}
function closeDetailPanel(){{document.querySelector('.detail-panel').classList.remove('open')}}
function focusNode(id){{selectedNodeId=id;autoRotate=false;if(nodeMap[id]){{showDetailPanel(nodeMap[id]);addToRecent(id,nodeMap[id].label,nodeMap[id].type)}};camZoom=2}}

// ── OSINT Feed System ──
function getEnabledFeeds(){{
  const feeds=[];
  document.querySelectorAll('.feed-cb:checked').forEach(cb=>feeds.push(cb.value));
  return feeds;
}}
function toggleAllFeeds(on){{document.querySelectorAll('.feed-cb').forEach(cb=>cb.checked=on)}}

function previewFeed(feedName){{
  const entity=selectedNodeId&&nodeMap[selectedNodeId]?nodeMap[selectedNodeId].label:
    document.getElementById('searchInput').value.trim();
  if(!entity){{showBanner('Select a node or enter a search term first');return}}

  const panel=document.getElementById('feedPanel');
  const body=document.getElementById('feedPanelBody');
  const title=document.getElementById('feedPanelTitle');
  title.textContent=feedName.toUpperCase()+' — '+entity;
  body.innerHTML='<div class="feed-loading">Querying '+feedName+'...</div>';
  panel.classList.add('open');

  fetch(SERVER+'/osint/'+feedName,{{
    method:'POST',headers:{{'Content-Type':'application/json'}},
    body:JSON.stringify({{entity:entity}})
  }}).then(r=>r.json()).then(d=>{{
    if(!d.success){{body.innerHTML='<div class="feed-loading">Error: '+(d.error||'Failed')+'</div>';return}}
    const results=d.results||[];
    if(!results.length){{
      body.innerHTML='<div class="feed-loading">No results from '+feedName+'</div>';
      if(d.message)body.innerHTML+='<div style="text-align:center;color:var(--text-muted);font-size:11px;margin-top:8px">'+d.message+'</div>';
      return;
    }}
    let html='<div style="font-size:11px;color:var(--text-muted);margin-bottom:8px">'+d.message+'</div>';
    html+='<button class="btn btn-sm btn-primary" style="width:100%;margin-bottom:10px;padding:6px" onclick="analyzeFeedData(\\''+feedName+'\\')">AI Analyze &amp; Add to Graph</button>';
    html+=results.map(r=>{{
      let extra='';
      if(r.extra)Object.entries(r.extra).slice(0,4).forEach(([k,v])=>{{extra+='<div class="feed-item-extra">'+k+': '+v+'</div>'}});
      let link=r.url?'<div class="feed-item-link"><a href="'+r.url+'" target="_blank">'+r.url.substring(0,80)+'</a></div>':'';
      return '<div class="feed-item"><div class="feed-item-title">'+(r.title||r.name||r.event||'—')+'</div>'
        +'<div class="feed-item-meta">'+(r.source||feedName)+' &middot; '+(r.date||'')+'</div>'
        +extra+link+'</div>';
    }}).join('');
    body.innerHTML=html;
    body.scrollTop=0;
    // Cache for analyze
    panel._lastResults=results;panel._lastFeed=feedName;panel._lastEntity=entity;
  }}).catch(()=>{{body.innerHTML='<div class="feed-loading">Server not running</div>'}});
}}

function closeFeedPanel(){{document.getElementById('feedPanel').classList.remove('open')}}

function analyzeFeedData(feedName){{
  const panel=document.getElementById('feedPanel');
  const results=panel._lastResults;
  const entity=panel._lastEntity||'';
  if(!results||!results.length)return;
  const dataText=results.map(r=>{{
    let line=(r.title||r.name||'')+' | '+(r.source||feedName)+' | '+(r.date||'');
    if(r.extra)Object.entries(r.extra).forEach(([k,v])=>line+=' | '+k+': '+v);
    if(r.url)line+=' | '+r.url;
    return line;
  }}).join('\\n');
  showBanner('AI analyzing '+results.length+' '+feedName+' results...');
  fetch(SERVER+'/osint/analyze',{{
    method:'POST',headers:{{'Content-Type':'application/json'}},
    body:JSON.stringify({{entity:entity,data:dataText,source:feedName}})
  }}).then(r=>r.json()).then(d=>{{
    if(d.success){{showBanner('AI extracted '+d.added+' entities from '+feedName);if(d.reload)setTimeout(()=>location.reload(),1500)}}
    else showBanner('Error: '+(d.error||'Failed'));
  }}).catch(()=>showBanner('Server error'));
}}

// ── OSINT Tool Actions (AI-powered traces from detail panel) ──
function runOsintWithPreview(tool,entity){{
  // Open feed panel immediately with loading state
  const panel=document.getElementById('feedPanel');
  const body=document.getElementById('feedPanelBody');
  const title=document.getElementById('feedPanelTitle');
  title.textContent=tool.toUpperCase()+' — '+entity;
  body.innerHTML='<div class="feed-loading">AI is running '+tool+' trace on '+entity+'... this may take a minute</div>';
  panel.classList.add('open');
  showBanner('AI running <b>'+tool+'</b> on <b>'+entity+'</b>...');

  fetch(SERVER+'/osint/'+tool,{{
    method:'POST',headers:{{'Content-Type':'application/json'}},
    body:JSON.stringify({{entity:entity}})
  }}).then(r=>r.json()).then(d=>{{
    if(!d.success){{
      body.innerHTML='<div class="feed-loading">Error: '+(d.error||'Failed')+'</div>';
      showBanner('Error: '+(d.error||'Failed'));
      return;
    }}
    let html='<div style="font-size:11px;color:var(--text-muted);margin-bottom:10px">'+d.message+'</div>';

    // If entities were added to graph, show them
    if(d.reload){{
      html+='<div style="font-size:11px;font-weight:700;color:var(--green);text-transform:uppercase;letter-spacing:1px;margin-bottom:6px">Entities added to graph</div>';
      html+='<div style="font-size:12px;color:var(--text-secondary);margin-bottom:12px">The AI found connections and added them. The board will reload shortly.</div>';
    }}

    // If there are displayable results, show them
    if(d.results&&d.results.length){{
      html+='<div style="font-size:11px;font-weight:700;color:var(--blue);text-transform:uppercase;letter-spacing:1px;margin-bottom:6px">Data Retrieved ('+d.results.length+')</div>';
      html+='<button class="btn btn-sm btn-primary" style="width:100%;margin-bottom:10px;padding:6px" onclick="analyzeFeedData('+String.fromCharCode(39)+tool+String.fromCharCode(39)+')">AI Analyze &amp; Add to Graph</button>';
      html+=d.results.map(function(r){{
        var extra='';
        if(r.extra)Object.entries(r.extra).slice(0,4).forEach(function(kv){{extra+='<div class="feed-item-extra">'+kv[0]+': '+kv[1]+'</div>'}});
        var link=r.url?'<div class="feed-item-link"><a href="'+r.url+'" target="_blank">'+r.url.substring(0,80)+'</a></div>':'';
        return '<div class="feed-item"><div class="feed-item-title">'+(r.title||r.name||'—')+'</div>'
          +'<div class="feed-item-meta">'+(r.source||tool)+' &middot; '+(r.date||'')+'</div>'
          +extra+link+'</div>';
      }}).join('');
      panel._lastResults=d.results;panel._lastFeed=tool;panel._lastEntity=entity;
    }}

    if(!d.results||!d.results.length){{
      if(!d.reload)html+='<div style="color:var(--text-muted);font-size:12px;padding:10px">No displayable results. The AI searched and processed data internally.</div>';
    }}

    body.innerHTML=html;
    body.scrollTop=0;
    showBanner(tool+' complete: '+d.message);
    if(d.reload)setTimeout(function(){{location.reload()}},3000);
  }}).catch(function(){{
    body.innerHTML='<div class="feed-loading">Server not running</div>';
    showBanner('Error: Server not running');
  }});
}}

// ── Export ──
function exportInvestigation(){{
  const fmt=prompt('Export format:\\n1. HTML Report\\n2. JSON Graph Data\\n3. Print to PDF\\n\\nEnter 1, 2, or 3:');
  if(fmt==='1'||fmt===null)window.open(SERVER+'/report-view','_blank');
  else if(fmt==='2'){{
    const data={{nodes:NODES,edges:EDGES,title:'{board_title}',exported:new Date().toISOString()}};
    const blob=new Blob([JSON.stringify(data,null,2)],{{type:'application/json'}});
    const a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download='deepdive_export.json';a.click();
  }}
  else if(fmt==='3')window.print();
}}

// ── Sidebar / Interview / Search ──
function toggleSidebar(){{document.querySelector('.sidebar').classList.toggle('collapsed')}}
function filterEntities(q){{q=q.toLowerCase();document.querySelectorAll('.entity-card[data-entity]').forEach(c=>{{c.style.display=c.textContent.toLowerCase().includes(q)||!q?'':'none'}})}}
function toggleSection(el){{el.classList.toggle('open');el.nextElementSibling.classList.toggle('open')}}

function toggleInterviewPanel(){{
  const inp=document.getElementById('searchInput');if(!inp.value.trim())return;
  const p=document.getElementById('interviewPanel');
  if(!p.classList.contains('open')){{p.classList.add('open');loadFocusOptions()}}else p.classList.remove('open');
}}
function loadFocusOptions(){{
  fetch(SERVER+'/interview/options',{{method:'POST'}}).then(r=>r.json()).then(d=>{{
    const el=document.getElementById('focusChecks');
    let h='<label><input type="checkbox" value="all" onchange="toggleAllFocus(this.checked)"> <b>Select All</b></label>';
    Object.entries(d.focus_categories||{{}}).forEach(([k,cat])=>{{
      h+='<div class="interview-cat">'+cat.label+'</div>';
      (cat.options||[]).forEach(([v,l])=>{{h+='<label><input type="checkbox" class="focus-cb" value="'+v+'"> '+l+'</label>'}});
    }});el.innerHTML=h;
  }}).catch(()=>{{}});
}}
function toggleAllFocus(c){{document.querySelectorAll('.focus-cb').forEach(cb=>cb.checked=c)}}

function launchInvestigation(){{
  const subj=document.getElementById('searchInput').value.trim();if(!subj)return;
  const fa=[];document.querySelectorAll('.focus-cb:checked').forEach(cb=>fa.push(cb.value));if(!fa.length)fa.push('all');
  const mr=document.querySelector('input[name="investMode"]:checked');
  const ef=getEnabledFeeds();
  const config={{subject:subj,raw_intent:subj,focus_areas:fa,depth:document.getElementById('depthSelect').value,time_period:document.getElementById('timePeriod').value,user_context:document.getElementById('userContext').value,multi_agent:document.getElementById('multiAgent').checked,mode:mr?mr.value:'new',enabled_feeds:ef}};
  showBanner('Investigating <b>'+subj+'</b>...');document.getElementById('interviewPanel').classList.remove('open');
  fetch(SERVER+'/interview/start',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify(config)}}).then(r=>r.json()).then(d=>{{
    if(d.success){{showBanner('Found '+d.entities+' entities');window.location.href=SERVER+'/board'}}else showBanner('Error: '+(d.error||'Failed'));
  }}).catch(()=>showBanner('Error: Server not running'));
}}

function showExpandResults(data){{
  // Show feed data + added entities in the feed panel
  const panel=document.getElementById('feedPanel');
  const body=document.getElementById('feedPanelBody');
  const title=document.getElementById('feedPanelTitle');
  const feedData=data.feed_data||{{}};
  const addedEntities=data.added_entities||[];
  const feedCount=Object.keys(feedData).length;
  const totalItems=Object.values(feedData).reduce((s,arr)=>s+(arr||[]).length,0);

  title.textContent='Expansion Results — +'+data.added+' entities';
  let html='';

  // Show what was added to the graph
  if(addedEntities.length){{
    html+='<div style="font-size:11px;font-weight:700;color:var(--green);text-transform:uppercase;letter-spacing:1px;margin-bottom:6px">Added to Graph ('+addedEntities.length+')</div>';
    html+=addedEntities.map(function(e){{
      var eid=e.name.toLowerCase().replace(/ /g,'_');
      return '<div class="feed-item" style="border-left:3px solid '+(COLORS[e.type]||'#6B7280')+'" onclick="focusNode('+String.fromCharCode(39)+eid+String.fromCharCode(39)+')">'
      +'<div class="feed-item-title" style="color:'+(COLORS[e.type]||'#6B7280')+'">'+e.name+'</div>'
      +'<div class="feed-item-meta">'+e.type+' &middot; '+e.relationship.replace(/_/g,' ')+'</div></div>';
    }}).join('');
  }}

  // Show feed data that was used
  if(feedCount){{
    html+='<div style="font-size:11px;font-weight:700;color:var(--blue);text-transform:uppercase;letter-spacing:1px;margin:14px 0 6px">OSINT Feed Data Used ('+totalItems+' items from '+feedCount+' feeds)</div>';
    Object.entries(feedData).forEach(([feed,items])=>{{
      if(!items||!items.length)return;
      html+='<div style="font-size:10px;font-weight:700;color:var(--text-muted);text-transform:uppercase;margin:8px 0 4px">'+feed+' ('+items.length+')</div>';
      html+=items.map(r=>
        '<div class="feed-item"><div class="feed-item-title">'+(r.title||'—')+'</div>'
        +'<div class="feed-item-meta">'+(r.source||feed)+' &middot; '+(r.date||'')+'</div>'
        +(r.url?'<div class="feed-item-link"><a href="'+r.url+'" target="_blank">'+r.url.substring(0,80)+'</a></div>':'')
        +'</div>'
      ).join('');
    }});
  }}

  if(!html)html='<div class="feed-loading">No feed data or entities to show</div>';
  body.innerHTML=html;
  body.scrollTop=0;
  panel.classList.add('open');
}}

function diveDeeper(id,label){{
  const ef=getEnabledFeeds();
  if(MODE==='server'){{
    if(window._ws&&window._ws.readyState===1){{window._ws.send(JSON.stringify({{action:'expand',id,label,search_mode:searchMode,enabled_feeds:ef.length?ef:null}}));showBanner('Expanding <b>'+label+'</b>'+(ef.length?' + '+ef.length+' OSINT feeds':'')+' ...');return}}
    fetch(SERVER+'/expand',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{id,label,search_mode:searchMode,enabled_feeds:ef.length?ef:null}})}}).then(r=>r.json()).then(d=>{{
      if(d.success){{showBanner(d.added+' new entities');showExpandResults(d);setTimeout(()=>location.reload(),3000)}}else showBanner('Error: '+d.error);
    }}).catch(()=>showBanner('Error: Server not running'));
  }}else{{const cmd='/deepdive expand '+label;navigator.clipboard.writeText(cmd).catch(()=>{{}});showBanner('Copied: <code>'+cmd+'</code>')}}
}}

function investigateNode(id,label,type,cc){{
  const conns=EDGES.filter(e=>e.from===id||e.to===id);
  const names=conns.map(c=>{{const o=nodeMap[c.from===id?c.to:c.from];return o?(o.label+' ('+c.label+')'):''}}).filter(x=>x).slice(0,20).join(', ');
  document.getElementById('searchInput').value=label;
  const p=document.getElementById('interviewPanel');p.classList.add('open');loadFocusOptions();
  setTimeout(()=>{{const ctx=document.getElementById('userContext');if(ctx)ctx.value='Known: '+names;
    let cd=document.getElementById('investChoice');if(!cd){{cd=document.createElement('div');cd.id='investChoice';cd.style.cssText='margin-top:10px';
    cd.innerHTML='<div class="interview-label">Mode</div><label style="display:block;font-size:12px;color:var(--text-secondary);padding:3px 0"><input type="radio" name="investMode" value="expand" checked> Expand current graph</label><label style="display:block;font-size:12px;color:var(--text-secondary);padding:3px 0"><input type="radio" name="investMode" value="new"> New investigation</label>';
    const btn=p.querySelector('.btn-primary');if(btn)p.insertBefore(cd,btn)}}}},300);
}}

function generateReport(id,label){{
  showBanner('Generating report for <b>'+label+'</b>...');
  if(window._ws&&window._ws.readyState===1){{window._ws.send(JSON.stringify({{action:'report',id,label}}));return}}
  fetch(SERVER+'/report',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{id,label}})}}).then(r=>r.json()).then(d=>{{
    if(d.success){{showBanner('Report saved');loadReports();if(selectedNodeId&&nodeMap[selectedNodeId])showDetailPanel(nodeMap[selectedNodeId])}}else showBanner('Error: '+d.error);
  }}).catch(()=>showBanner('Error: Server not running'));
}}

// ── Data Sources ──
let searchMode=localStorage.getItem('dd_search_mode')||'web';
function setSearchMode(m){{searchMode=m;localStorage.setItem('dd_search_mode',m);document.querySelectorAll('.mode-btn').forEach(b=>b.classList.remove('active'));const btn=document.getElementById('mode-'+m);if(btn)btn.classList.add('active')}}

let fileBrowserPath='/home';let fileBrowserSelected='';
function openFileBrowser(){{fileBrowserPath=document.getElementById('dsPath').value||'/home';fileBrowserSelected='';document.getElementById('fileBrowserModal').classList.add('open');loadDirectory(fileBrowserPath)}}
function closeFileBrowser(){{document.getElementById('fileBrowserModal').classList.remove('open')}}
function loadDirectory(path){{
  fileBrowserPath=path;
  fetch(SERVER+'/browse_dir',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{path}})}}).then(r=>r.json()).then(d=>{{
    if(!d.success)return;
    const parts=path.split('/').filter(x=>x);let bc='<span class="path-segment" onclick="loadDirectory(\\'/\\')">/ </span>';let acc='/';
    parts.forEach(p=>{{acc+=p+'/';bc+='<span class="path-segment" onclick="loadDirectory(\\''+acc+'\\')">'+p+' / </span>'}});
    document.getElementById('pathBreadcrumb').innerHTML=bc;
    let html='';if(path!=='/')html+='<div class="file-item" ondblclick="loadDirectory(\\''+d.parent+'\\')"><span class="file-icon">&#128193;</span><span class="file-name">..</span></div>';
    (d.dirs||[]).forEach(dir=>{{html+='<div class="file-item" onclick="selectBrowserItem(this,\\''+dir.path+'\\')" ondblclick="loadDirectory(\\''+dir.path+'\\')"><span class="file-icon">&#128193;</span><span class="file-name">'+dir.name+'</span></div>'}});
    document.getElementById('fileBrowserList').innerHTML=html;
  }}).catch(()=>{{document.getElementById('fileBrowserList').innerHTML='<div style="color:var(--text-muted);padding:16px">Could not load</div>'}});
}}
function selectBrowserItem(el,path){{document.querySelectorAll('.file-item.selected').forEach(e=>e.classList.remove('selected'));el.classList.add('selected');fileBrowserSelected=path}}
function confirmFileBrowser(){{document.getElementById('dsPath').value=fileBrowserSelected||fileBrowserPath;closeFileBrowser()}}

function scanDataset(){{
  const path=document.getElementById('dsPath').value.trim();if(!path)return;showBanner('Scanning...');
  if(window._ws&&window._ws.readyState===1){{window._ws.send(JSON.stringify({{action:'scan_dataset',path}}));return}}
  fetch(SERVER+'/scan',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{path}})}}).then(r=>r.json()).then(d=>{{
    if(d.success){{showBanner(d.files_indexed+' files, '+d.entities_added+' entities');setTimeout(()=>location.reload(),2000)}}else showBanner('Error: '+d.error);
  }}).catch(()=>showBanner('Error: Server not running'));
}}

// ── Node Actions ──
function pinNode(id){{fetch(SERVER+'/node/pin',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{id}})}}).then(r=>r.json()).then(d=>{{if(d.success&&nodeMap[id]){{if(!nodeMap[id].metadata)nodeMap[id].metadata={{}};nodeMap[id].metadata.pinned=d.pinned;showDetailPanel(nodeMap[id])}}}})}};
function addNodeNote(id){{const n=prompt('Add note:');if(!n||!n.trim())return;fetch(SERVER+'/node/note',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{id,note:n.trim()}})}}).then(r=>r.json()).then(d=>{{if(d.success&&nodeMap[id]){{if(!nodeMap[id].metadata)nodeMap[id].metadata={{}};if(!nodeMap[id].metadata.notes)nodeMap[id].metadata.notes=[];nodeMap[id].metadata.notes.push(n.trim());showDetailPanel(nodeMap[id])}}}})}};
function pruneNode(id,label){{if(!confirm('Remove '+label+'?'))return;fetch(SERVER+'/node/prune',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{id}})}}).then(r=>r.json()).then(d=>{{if(d.success)window.location.href=SERVER+'/board'}})}};

// ── Navigation ──
function loadInvestigationList(){{fetch(SERVER+'/list_investigations',{{method:'POST'}}).then(r=>r.json()).then(d=>{{const sel=document.getElementById('navSelect');sel.innerHTML='<option value="" disabled selected>Switch Investigation</option>';(d.investigations||[]).forEach(inv=>{{const o=document.createElement('option');o.value=inv.dir;o.textContent=inv.name+' ('+inv.entities+')';if(inv.active)o.selected=true;sel.appendChild(o)}})}}).catch(()=>{{}})}}
function switchInvestigation(dir){{if(!dir)return;fetch(SERVER+'/switch',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{dir}})}}).then(r=>r.json()).then(d=>{{if(d.success)window.location.href=SERVER+'/board'}})}}
function goHome(){{fetch(SERVER+'/home',{{method:'POST'}}).then(()=>{{window.location.href=SERVER+'/board'}})}}
function researchGaps(){{showBanner('Researching gaps...');fetch(SERVER+'/research_gaps',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{max_gaps:5}})}}).then(r=>r.json()).then(d=>{{if(d.success){{showBanner(d.gaps_researched+' gaps researched');setTimeout(()=>location.reload(),2000)}}else showBanner('Error: '+(d.error||'Failed'))}}).catch(()=>showBanner('Error: Server not running'))}}
function loadGapList(){{fetch(SERVER+'/list_gaps',{{method:'POST'}}).then(r=>r.json()).then(d=>{{const el=document.getElementById('gapList');const gaps=(d.gaps||[]).slice(0,10);if(!gaps.length){{el.innerHTML='<div style="color:var(--text-muted);padding:6px;font-size:12px">No gaps detected</div>';return}};el.innerHTML=gaps.map(g=>'<div class="gap-card'+(g.researched?' researched':'')+'"><span style="color:var(--text)">'+g.a_name+'</span> <span style="color:var(--text-muted)">&harr;</span> <span style="color:var(--text)">'+g.c_name+'</span><div style="color:var(--text-muted);font-size:10px;margin-top:2px">via '+g.b_name+' &middot; score '+g.score+(g.researched?' &check;':'')+'</div></div>').join('')}}).catch(()=>{{}})}}
let nodeReports={{}};function loadReports(){{fetch(SERVER+'/list_reports',{{method:'POST'}}).then(r=>r.json()).then(d=>{{nodeReports={{}};(d.reports||[]).forEach(r=>{{nodeReports[r.id]=r}})}}).catch(()=>{{}})}}

// ── Recent ──
let recentHistory=JSON.parse(localStorage.getItem('dd_recent_'+'{board_title}')||'[]');
function addToRecent(id,label,type){{recentHistory=recentHistory.filter(r=>r.id!==id);recentHistory.unshift({{id,label,type,time:Date.now()}});if(recentHistory.length>20)recentHistory=recentHistory.slice(0,20);localStorage.setItem('dd_recent_'+'{board_title}',JSON.stringify(recentHistory));renderRecent()}}
function renderRecent(){{const el=document.getElementById('recentTargets');if(!recentHistory.length){{el.innerHTML='<div style="color:var(--text-muted);padding:6px;font-size:12px">Click nodes to track</div>';return}};el.innerHTML=recentHistory.map(r=>'<div class="entity-card" onclick="focusNode(\\''+r.id+'\\')" style="border-left-color:'+COLORS[r.type]+'"><div class="entity-name" style="color:'+COLORS[r.type]+'">'+r.label+'</div><div class="entity-type">'+r.type+'</div></div>').join('')}}

// ── Banner / WS ──
function showBanner(html){{const b=document.getElementById('banner');b.innerHTML=html+' <span style="cursor:pointer;margin-left:14px;opacity:.4;font-size:16px" onclick="hideBanner()">&times;</span>';b.classList.add('visible')}}
function hideBanner(){{document.getElementById('banner').classList.remove('visible')}}

if(MODE==='server'){{try{{window._ws=new WebSocket('ws://localhost:8765/ws');
  window._ws.onmessage=e=>{{const d=JSON.parse(e.data);
    if(d.action==='expand_done'){{showBanner(d.message);showExpandResults(d);setTimeout(()=>{{location.hash='focus='+(selectedNodeId||'');location.reload()}},3000)}}
    else if(d.action==='reload'){{showBanner('Done! Reloading...');setTimeout(()=>{{location.hash='focus='+(selectedNodeId||'');location.reload()}},1000)}}
    else if(d.action==='status')showBanner(d.message);else if(d.action==='error')showBanner('Error: '+d.message);
    else if(d.action==='scan_status')showBanner(d.message);else if(d.action==='scan_done'){{showBanner(d.message);setTimeout(()=>location.reload(),2000)}}}};
  window._ws.onerror=()=>{{}};}}catch(e){{}}}}

// ── Init ──
const steps=NODES.length>500?150:NODES.length>200?300:500;
for(let i=0;i<steps;i++)simulate();zoomFit();
setTimeout(()=>{{loadInvestigationList();loadGapList();loadReports();renderRecent();setSearchMode(searchMode)}},300);
setTimeout(()=>{{const hash=location.hash.replace('#',''),params=new URLSearchParams(hash),fid=params.get('focus');
  if(fid&&nodeMap[fid]){{selectedNodeId=fid;autoRotate=false;showDetailPanel(nodeMap[fid]);let mx=0;
    EDGES.forEach(e=>{{let cid=e.from===fid?e.to:(e.to===fid?e.from:null);if(cid&&nodeMap[cid])mx=Math.max(mx,Math.hypot(nodeMap[cid].x-nodeMap[fid].x,nodeMap[cid].y-nodeMap[fid].y,nodeMap[cid].z-nodeMap[fid].z))}});
    camZoom=Math.max(5,mx*3+1);camRotY=Math.atan2(nodeMap[fid].z,nodeMap[fid].x)}}}},100);
render();
"""


def build_board(graph, output_path, title=None, mode="skill"):
    stats = graph.get_stats()
    board_title = title or f"DeepDive: {graph.name}"

    nodes = []
    for eid, entity in graph.entities.items():
        color = COLORS.get(entity.type, '#6B7280')
        conns = len(graph.get_connections_for(eid))
        nodes.append({
            'id': eid, 'label': entity.name, 'type': entity.type,
            'color': color, 'size': min(2 + conns * 0.4, 10),
            'depth': entity.depth, 'investigated': entity.investigated,
            'metadata': entity.metadata, 'connections': conns,
        })

    edges = []
    for conn in graph.connections:
        edges.append({
            'from': conn.source_id, 'to': conn.target_id,
            'label': conn.relationship.replace('_', ' '),
            'confidence': conn.confidence,
        })

    sorted_nodes = sorted(nodes, key=lambda x: (0 if 'your_path' in x['id'] else 1, -x['connections']))
    entity_cards = '\n'.join(
        f'<div class="entity-card" data-entity onclick="focusNode(\'{n["id"]}\')" style="border-left-color:{n["color"]}">'
        f'<div class="entity-name" style="color:{n["color"]}">{n["label"]}</div>'
        f'<div class="entity-type">{n["type"]} &middot; {n["connections"]} conn</div></div>'
        for n in sorted_nodes
    )
    findings_html = '\n'.join(f'<div class="finding-card">{f}</div>' for f in graph.findings) if graph.findings else ''
    legend_html = '\n'.join(
        f'<div class="legend-item"><div class="legend-dot" style="background:{c}"></div>{t} ({stats["entity_types"].get(t,0)})</div>'
        for t, c in COLORS.items() if stats['entity_types'].get(t, 0) > 0
    )

    css = generate_css()
    js = generate_js(json.dumps(nodes), json.dumps(edges), json.dumps(COLORS), mode, board_title)

    html = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><title>{board_title}</title>
<style>{css}</style></head><body>
<div class="viewport">
  <canvas id="graphCanvas"></canvas>

  <div class="topbar glass">
    <span class="topbar-brand">DEEPDIVE</span>
    <div class="topbar-sep"></div>
    <select id="navSelect" onchange="switchInvestigation(this.value)" class="topbar-select"><option value="" disabled>Investigations</option></select>
    <div class="topbar-actions">
      <button onclick="toggleSidebar()" class="topbar-btn">Panel</button>
      <button onclick="window.location.href='{SERVER}/timeline'" class="topbar-btn">Timeline</button>
      <button onclick="window.location.href='{SERVER}/money-flow'" class="topbar-btn">Money Flow</button>
      <button onclick="window.location.href='{SERVER}/report-view'" class="topbar-btn">Report</button>
      <button onclick="exportInvestigation()" class="topbar-btn">Export</button>
      <button onclick="window.location.href='{SERVER}/settings'" class="topbar-btn">Settings</button>
      <button onclick="goHome()" class="topbar-btn">Home</button>
    </div>
  </div>

  <div class="sidebar glass">
    <div class="sidebar-header">
      <div class="sidebar-title">{board_title}</div>
      <div class="sidebar-meta">
        <span><b>{stats['total_entities']}</b> entities</span>
        <span><b>{stats['total_connections']}</b> conn</span>
        <span><b>{stats['gaps_found']}</b> gaps</span>
      </div>
    </div>
    <div class="sidebar-body">

      <div class="section">
        <div class="section-header open" onclick="toggleSection(this)">Investigate <span class="chv">&#9662;</span></div>
        <div class="section-body open">
          <input type="text" id="searchInput" class="input-field" placeholder="Who or what to investigate..." onkeydown="if(event.key==='Enter')toggleInterviewPanel()">
          <div style="margin-top:10px"><button onclick="toggleInterviewPanel()" class="btn btn-primary">Configure &amp; Launch</button></div>
          <div id="interviewPanel" class="interview-panel">
            <div class="interview-label">Focus Areas</div>
            <div id="focusChecks" class="interview-checks"></div>
            <div style="margin-top:10px;display:flex;gap:8px;align-items:center">
              <label style="font-size:12px;color:var(--text-muted)">Depth:</label>
              <select id="depthSelect" class="input-field" style="flex:1;padding:7px 10px"><option value="quick">Quick (~50)</option><option value="standard" selected>Standard (~150)</option><option value="exhaustive">Exhaustive</option></select>
            </div>
            <input type="text" id="timePeriod" class="input-field" placeholder="Time period (optional)" style="margin-top:8px;padding:8px 12px">
            <input type="text" id="userContext" class="input-field" placeholder="Known context (optional)" style="margin-top:6px;padding:8px 12px">
            <div style="margin:10px 0;display:flex;align-items:center;gap:6px"><input type="checkbox" id="multiAgent"><label for="multiAgent" style="font-size:12px;color:var(--text-muted)">Parallel agents</label></div>
            <button onclick="launchInvestigation()" class="btn btn-primary">Launch Investigation</button>
          </div>
        </div>
      </div>

      <div class="section">
        <div class="section-header open" onclick="toggleSection(this)">OSINT Tools <span class="chv">&#9662;</span></div>
        <div class="section-body open">
          <div style="font-size:10px;color:var(--text-muted);margin-bottom:8px">Check sources for AI to query during dives. Click a feed name to preview data.</div>
          <div style="display:flex;gap:6px;margin-bottom:8px">
            <button class="btn btn-sm btn-secondary" style="flex:1;padding:5px;font-size:10px" onclick="toggleAllFeeds(true)">All On</button>
            <button class="btn btn-sm btn-secondary" style="flex:1;padding:5px;font-size:10px" onclick="toggleAllFeeds(false)">All Off</button>
          </div>

          <div style="font-size:10px;font-weight:700;color:var(--text-muted);text-transform:uppercase;letter-spacing:1px;margin-bottom:4px">Intelligence Feeds</div>
          <div class="osint-checks">
            <label class="osint-check"><input type="checkbox" class="feed-cb" value="news" checked><span class="osint-icon-sm">&#128225;</span><span onclick="event.preventDefault();previewFeed('news')" class="feed-preview">News</span></label>
            <label class="osint-check"><input type="checkbox" class="feed-cb" value="gdelt"><span class="osint-icon-sm">&#127758;</span><span onclick="event.preventDefault();previewFeed('gdelt')" class="feed-preview">GDELT Events</span></label>
            <label class="osint-check"><input type="checkbox" class="feed-cb" value="reddit"><span class="osint-icon-sm">&#128172;</span><span onclick="event.preventDefault();previewFeed('reddit')" class="feed-preview">Reddit</span></label>
            <label class="osint-check"><input type="checkbox" class="feed-cb" value="bluesky"><span class="osint-icon-sm">&#9729;</span><span onclick="event.preventDefault();previewFeed('bluesky')" class="feed-preview">Bluesky</span></label>
            <label class="osint-check"><input type="checkbox" class="feed-cb" value="conflicts"><span class="osint-icon-sm">&#9876;</span><span onclick="event.preventDefault();previewFeed('conflicts')" class="feed-preview">Armed Conflicts</span></label>
            <label class="osint-check"><input type="checkbox" class="feed-cb" value="darkweb"><span class="osint-icon-sm">&#128375;</span><span onclick="event.preventDefault();previewFeed('darkweb')" class="feed-preview">Dark Web</span></label>
          </div>

          <div style="font-size:10px;font-weight:700;color:var(--text-muted);text-transform:uppercase;letter-spacing:1px;margin:8px 0 4px">Government &amp; Legal</div>
          <div class="osint-checks">
            <label class="osint-check"><input type="checkbox" class="feed-cb" value="gov"><span class="osint-icon-sm">&#127963;</span><span onclick="event.preventDefault();previewFeed('gov')" class="feed-preview">Gov Contracts</span></label>
            <label class="osint-check"><input type="checkbox" class="feed-cb" value="patents"><span class="osint-icon-sm">&#128218;</span><span onclick="event.preventDefault();previewFeed('patents')" class="feed-preview">Patents</span></label>
            <label class="osint-check"><input type="checkbox" class="feed-cb" value="sec"><span class="osint-icon-sm">&#128200;</span><span onclick="event.preventDefault();previewFeed('sec')" class="feed-preview">SEC Filings</span></label>
            <label class="osint-check"><input type="checkbox" class="feed-cb" value="sanctions"><span class="osint-icon-sm">&#128683;</span><span onclick="event.preventDefault();previewFeed('sanctions')" class="feed-preview">Sanctions</span></label>
            <label class="osint-check"><input type="checkbox" class="feed-cb" value="cisa"><span class="osint-icon-sm">&#128274;</span><span onclick="event.preventDefault();previewFeed('cisa')" class="feed-preview">CISA Vulns</span></label>
            <label class="osint-check"><input type="checkbox" class="feed-cb" value="humanitarian"><span class="osint-icon-sm">&#10010;</span><span onclick="event.preventDefault();previewFeed('humanitarian')" class="feed-preview">Humanitarian</span></label>
          </div>

          <div style="font-size:10px;font-weight:700;color:var(--text-muted);text-transform:uppercase;letter-spacing:1px;margin:8px 0 4px">Geospatial &amp; Signals</div>
          <div class="osint-checks">
            <label class="osint-check"><input type="checkbox" class="feed-cb" value="flights"><span class="osint-icon-sm">&#9992;</span><span onclick="event.preventDefault();previewFeed('flights')" class="feed-preview">Mil Flights</span></label>
            <label class="osint-check"><input type="checkbox" class="feed-cb" value="ships"><span class="osint-icon-sm">&#128674;</span><span onclick="event.preventDefault();previewFeed('ships')" class="feed-preview">Ships</span></label>
            <label class="osint-check"><input type="checkbox" class="feed-cb" value="earthquakes"><span class="osint-icon-sm">&#127755;</span><span onclick="event.preventDefault();previewFeed('earthquakes')" class="feed-preview">Earthquakes</span></label>
            <label class="osint-check"><input type="checkbox" class="feed-cb" value="fires"><span class="osint-icon-sm">&#128293;</span><span onclick="event.preventDefault();previewFeed('fires')" class="feed-preview">NASA Fires</span></label>
            <label class="osint-check"><input type="checkbox" class="feed-cb" value="satellites"><span class="osint-icon-sm">&#128752;</span><span onclick="event.preventDefault();previewFeed('satellites')" class="feed-preview">Satellites</span></label>
            <label class="osint-check"><input type="checkbox" class="feed-cb" value="weather"><span class="osint-icon-sm">&#9888;</span><span onclick="event.preventDefault();previewFeed('weather')" class="feed-preview">Severe Weather</span></label>
            <label class="osint-check"><input type="checkbox" class="feed-cb" value="launches"><span class="osint-icon-sm">&#128640;</span><span onclick="event.preventDefault();previewFeed('launches')" class="feed-preview">Launches</span></label>
            <label class="osint-check"><input type="checkbox" class="feed-cb" value="stock"><span class="osint-icon-sm">&#128178;</span><span onclick="event.preventDefault();previewFeed('stock')" class="feed-preview">Stock Price</span></label>
          </div>

          <div style="font-size:10px;font-weight:700;color:var(--text-muted);text-transform:uppercase;letter-spacing:1px;margin:8px 0 4px">AI-Powered Traces</div>
          <div class="osint-checks">
            <label class="osint-check"><input type="checkbox" class="feed-cb" value="social" checked><span class="osint-icon-sm">&#128100;</span><span onclick="event.preventDefault();previewFeed('social')" class="feed-preview">Social Media Scan</span></label>
            <label class="osint-check"><input type="checkbox" class="feed-cb" value="money"><span class="osint-icon-sm">&#128176;</span><span onclick="event.preventDefault();previewFeed('money')" class="feed-preview">Money Trace</span></label>
            <label class="osint-check"><input type="checkbox" class="feed-cb" value="timeline"><span class="osint-icon-sm">&#128197;</span><span onclick="event.preventDefault();previewFeed('timeline')" class="feed-preview">Timeline Trace</span></label>
            <label class="osint-check"><input type="checkbox" class="feed-cb" value="wayback"><span class="osint-icon-sm">&#128337;</span><span onclick="event.preventDefault();previewFeed('wayback')" class="feed-preview">Wayback Archive</span></label>
          </div>
        </div>
      </div>

      <div class="section">
        <div class="section-header" onclick="toggleSection(this)">Data Sources <span class="chv">&#9662;</span></div>
        <div class="section-body">
          <div style="display:flex;gap:6px">
            <input type="text" id="dsPath" class="input-field" placeholder="/path/to/documents..." style="flex:1">
            <button onclick="openFileBrowser()" class="btn-icon" title="Browse">&#128193;</button>
          </div>
          <div style="margin-top:8px"><button onclick="scanDataset()" class="btn btn-secondary btn-sm">Scan Dataset</button></div>
          <div class="mode-group">
            <button id="mode-web" class="mode-btn active" onclick="setSearchMode('web')">Web</button>
            <button id="mode-local" class="mode-btn" onclick="setSearchMode('local')">Local</button>
            <button id="mode-both" class="mode-btn" onclick="setSearchMode('both')">Both</button>
          </div>
        </div>
      </div>

      <div class="section">
        <div class="section-header" onclick="toggleSection(this)">Types <span class="chv">&#9662;</span></div>
        <div class="section-body"><div class="legend">{legend_html}</div></div>
      </div>

      <div class="section">
        <div class="section-header" onclick="toggleSection(this)">Gaps ({stats['gaps_found']}) <span class="chv">&#9662;</span></div>
        <div class="section-body">
          <button onclick="researchGaps()" class="btn btn-danger btn-sm" style="margin-bottom:8px">Research Top Gaps</button>
          <div id="gapList" style="max-height:140px;overflow-y:auto"></div>
        </div>
      </div>

      <div class="section">
        <div class="section-header" onclick="toggleSection(this)">Recent <span class="chv">&#9662;</span></div>
        <div class="section-body"><div id="recentTargets" style="max-height:140px;overflow-y:auto"></div></div>
      </div>

      <div class="section">
        <div class="section-header open" onclick="toggleSection(this)">Entities ({stats['total_entities']}) <span class="chv">&#9662;</span></div>
        <div class="section-body open">
          <input type="text" class="input-field" placeholder="Filter entities..." oninput="filterEntities(this.value)" style="margin-bottom:8px">
          <div style="max-height:400px;overflow-y:auto">{entity_cards}</div>
        </div>
      </div>

      {"<div class='section'><div class='section-header' onclick='toggleSection(this)'>Findings <span class=chv>&#9662;</span></div><div class='section-body'>" + findings_html + "</div></div>" if findings_html else ""}
    </div>
  </div>

  <div class="feed-panel glass" id="feedPanel">
    <div class="feed-panel-header">
      <div class="feed-panel-title" id="feedPanelTitle">Feed Data</div>
      <button class="detail-close" onclick="closeFeedPanel()">&#10005;</button>
    </div>
    <div class="feed-panel-body" id="feedPanelBody"></div>
  </div>

  <div class="detail-panel glass">
    <div class="detail-header">
      <div class="detail-header-label">Entity Intel</div>
      <button class="detail-close" onclick="closeDetailPanel();selectedNodeId=null">&#10005;</button>
    </div>
    <div class="detail-body"></div>
  </div>

  <div class="zoom-controls">
    <button class="zoom-btn" onclick="zoomIn()" title="Zoom In">+</button>
    <button class="zoom-btn" onclick="zoomOut()" title="Zoom Out">&minus;</button>
    <button class="zoom-btn" onclick="zoomFit()" title="Fit">&#8862;</button>
    <button class="zoom-btn" onclick="autoRotate=!autoRotate" title="Rotate">&#8634;</button>
  </div>

  <div class="tooltip" id="tooltip"></div>
  <div class="banner" id="banner"></div>

  <div class="statusbar glass">
    <span class="status-dot"></span>
    <span style="color:var(--text-secondary)">ACTIVE</span>
    <span class="status-sep">&middot;</span>
    <span>{stats['total_entities']} entities</span>
    <span class="status-sep">&middot;</span>
    <span>{stats['total_connections']} connections</span>
    <span class="status-sep">&middot;</span>
    <span>{stats['gaps_found']} gaps</span>
  </div>

  <div class="modal-overlay" id="fileBrowserModal">
    <div class="modal">
      <div class="modal-header"><div class="modal-title">Select Folder</div><button class="detail-close" onclick="closeFileBrowser()">&#10005;</button></div>
      <div class="modal-body"><div class="path-breadcrumb" id="pathBreadcrumb"></div><div id="fileBrowserList"></div></div>
      <div class="modal-footer"><button class="btn btn-secondary btn-sm" onclick="closeFileBrowser()">Cancel</button><button class="btn btn-primary btn-sm" style="width:auto" onclick="confirmFileBrowser()">Select</button></div>
    </div>
  </div>
</div>
<script>{js}</script></body></html>"""

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, 'w') as f:
        f.write(html)
    return output_path
