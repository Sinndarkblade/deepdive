#!/usr/bin/env python3
"""
Professional Report View — generates a print-ready HTML investigation report.
"""

import os
from datetime import datetime


COLORS = {
    'person': '#e74c3c', 'company': '#3498db', 'location': '#2ecc71',
    'event': '#f39c12', 'money': '#9b59b6', 'document': '#1abc9c',
    'government': '#e67e22', 'concept': '#00ccaa', 'unknown': '#7f8c8d',
}


def build_report(graph, output_path, title=None):
    """Generate a professional HTML investigation report."""

    stats = graph.get_stats()
    board_title = title or f"Investigation Report: {graph.name}"
    now = datetime.now().strftime("%B %d, %Y at %I:%M %p")

    # Group entities by type
    by_type = {}
    for eid, entity in graph.entities.items():
        t = entity.type
        if t not in by_type:
            by_type[t] = []
        conns = graph.get_connections_for(eid)
        by_type[t].append({
            'name': entity.name,
            'id': eid,
            'connections': len(conns),
            'metadata': entity.metadata,
            'investigated': entity.investigated,
            'depth': entity.depth,
        })

    # Sort each group by connection count
    for t in by_type:
        by_type[t].sort(key=lambda e: -e['connections'])

    # Build entity sections
    sections_html = ""
    type_order = ['person', 'company', 'government', 'money', 'event', 'location', 'document', 'concept', 'unknown']
    for t in type_order:
        entities = by_type.get(t, [])
        if not entities:
            continue
        color = COLORS.get(t, '#7f8c8d')
        sections_html += f'<h2 style="color:{color};border-bottom:2px solid {color}44;padding-bottom:4px">{t.title()}s ({len(entities)})</h2>\n'
        sections_html += '<table><tr><th>Name</th><th>Connections</th><th>Details</th></tr>\n'
        for e in entities[:50]:  # Limit per section
            meta_str = ', '.join(f'{k}: {v}' for k, v in e['metadata'].items()
                                 if k not in ('pinned', 'notes', 'source', 'config') and v)[:200]
            sections_html += f'<tr><td><b>{e["name"]}</b></td><td>{e["connections"]}</td><td style="color:#8a8f98;font-size:11px">{meta_str}</td></tr>\n'
        sections_html += '</table>\n'

    # Build findings section
    findings_html = ""
    if graph.findings:
        findings_html = '<h2 style="color:#2ecc71">Key Findings</h2>\n<ul>\n'
        for f in graph.findings:
            findings_html += f'<li>{f}</li>\n'
        findings_html += '</ul>\n'

    # Build top gaps section
    gaps = graph.gaps[:20] if graph.gaps else []
    gaps_html = ""
    if gaps:
        gaps_html = '<h2 style="color:#e74c3c">Suspicious Gaps</h2>\n'
        gaps_html += '<table><tr><th>Entity A</th><th>↔</th><th>Entity B</th><th>Via</th><th>Score</th></tr>\n'
        for g in gaps:
            gaps_html += f'<tr><td>{g.get("a_name","?")}</td><td>↔</td><td>{g.get("c_name","?")}</td><td>{g.get("b_name","?")}</td><td><b>{g.get("score",0)}</b></td></tr>\n'
        gaps_html += '</table>\n'

    # Top connections
    top_entities = sorted(graph.entities.items(), key=lambda x: -len(graph.get_connections_for(x[0])))[:15]
    top_html = '<h2>Most Connected Entities</h2>\n<table><tr><th>#</th><th>Entity</th><th>Type</th><th>Connections</th></tr>\n'
    for i, (eid, e) in enumerate(top_entities, 1):
        color = COLORS.get(e.type, '#7f8c8d')
        top_html += f'<tr><td>{i}</td><td style="color:{color}"><b>{e.name}</b></td><td>{e.type}</td><td>{len(graph.get_connections_for(eid))}</td></tr>\n'
    top_html += '</table>\n'

    html = f'''<!DOCTYPE html>
<html lang="en" id="reportHtml">
<head>
<meta charset="UTF-8"><title>{board_title}</title>
<link rel="stylesheet" href="/static/css/themes.css">
<link rel="stylesheet" href="/static/css/views-shared.css">
<script>
(function(){{
  var t = localStorage.getItem('deepdive-theme') || 'dark';
  document.getElementById('reportHtml').setAttribute('data-theme', t);
}})();
</script>
<style>
@media print {{
  body {{ background: #fff !important; color: #333 !important; }}
  .no-print {{ display: none !important; }}
  table {{ page-break-inside: avoid; }}
  h2 {{ page-break-after: avoid; }}
  .back-bar {{ display: none !important; }}
}}
.report-title {{ font-family:'Outfit',sans-serif; font-size:24px; font-weight:800; background:var(--brand-gradient); -webkit-background-clip:text; background-clip:text; -webkit-text-fill-color:transparent; margin-bottom:4px; }}
.subtitle {{ color:var(--text-muted); font-size:12px; margin-bottom:20px; }}
.type-bar {{ display:flex; gap:8px; flex-wrap:wrap; margin:10px 0 20px; }}
.type-tag {{ padding:4px 10px; border-radius:20px; font-size:11px; font-weight:600; }}
.section-h {{ font-family:'Outfit',sans-serif; font-size:13px; font-weight:700; text-transform:uppercase; letter-spacing:.8px; color:var(--text); margin:24px 0 10px; padding-bottom:6px; border-bottom:2px solid var(--glass-border); }}
.print-btn {{ padding:8px 18px; background:linear-gradient(135deg,var(--accent),var(--accent-dark)); color:#fff; border:none; border-radius:8px; cursor:pointer; font-size:12px; font-weight:600; }}
ul {{ padding-left:20px; margin:10px 0; }}
li {{ margin:6px 0; font-size:13px; color:var(--text-secondary); }}
</style>
</head>
<body>

<div class="back-bar no-print">
  <a href="http://localhost:8766/board" class="back-btn">← Board</a>
  <span class="back-bar-title">Investigation Report</span>
  <button onclick="window.print()" class="print-btn" style="margin-left:auto">Print / Save PDF</button>
</div>

<div class="page" style="max-width:960px">
  <div class="report-title">{board_title}</div>
  <div class="subtitle">Generated {now} &nbsp;·&nbsp; DeepDive</div>

  <div class="stats-row">
    <div class="stat-pill"><b>{stats['total_entities']}</b><span>Entities</span></div>
    <div class="stat-pill"><b>{stats['total_connections']}</b><span>Connections</span></div>
    <div class="stat-pill"><b>{stats['investigated']}</b><span>Investigated</span></div>
    <div class="stat-pill"><b>{stats['gaps_found']}</b><span>Gaps</span></div>
  </div>

  <div class="type-bar">
  {"".join(f'<span class="type-tag" style="background:{COLORS.get(t,"#7f8c8d")}22;color:{COLORS.get(t,"#7f8c8d")}">{t}: {c}</span>' for t, c in stats['entity_types'].items() if c > 0)}
  </div>

  <div class="card">
    <div class="card-header"><span class="card-title">Most Connected</span></div>
    <div class="card-body" style="padding:0">{top_html}</div>
  </div>

  {f'<div class="card"><div class="card-header"><span class="card-title">Key Findings</span></div><div class="card-body">{findings_html}</div></div>' if findings_html else ''}

  {f'<div class="card"><div class="card-header"><span class="card-title">Suspicious Gaps</span></div><div class="card-body" style="padding:0">{gaps_html}</div></div>' if gaps_html else ''}

  {f'<div class="card"><div class="card-header"><span class="card-title">Entities by Type</span></div><div class="card-body">{sections_html}</div></div>' if sections_html else ''}

  <div style="margin-top:24px;padding-top:16px;border-top:1px solid var(--glass-border);color:var(--text-muted);font-size:11px;text-align:center">
    DeepDive Investigation Report — Generated {now}
  </div>
</div>
</body></html>'''

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, 'w') as f:
        f.write(html)
    return output_path
