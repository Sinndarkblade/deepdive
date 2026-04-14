#!/usr/bin/env python3
"""
Money Flow View — generates a Sankey/flow diagram showing money movement between entities.
Uses D3-sankey for the visualization.
"""

import os
import json
from collections import defaultdict


MONEY_KEYWORDS = {
    'paid', 'funded', 'invested', 'donated', 'acquired', 'purchased', 'bought',
    'sold', 'financed', 'sponsor', 'grant', 'loan', 'bribe', 'payment',
    'contract', 'revenue', 'income', 'salary', 'dividend', 'transfer',
    'capital', 'stake', 'shares', 'equity', 'debt', 'owed', 'cost',
    'billion', 'million', 'thousand', '$', '€', '£', '¥',
}

MONEY_RELATIONSHIPS = {
    'funded_by', 'invested_in', 'acquired', 'paid_by', 'donated_to',
    'contract_with', 'purchased', 'sold_to', 'financed_by', 'sponsor_of',
    'revenue_from', 'subsidiary_of', 'parent_company', 'merged_with',
    'investor_in', 'shareholder_of', 'creditor_of', 'debtor_of',
}


def extract_amount(text):
    """Try to extract a dollar amount from text."""
    import re
    patterns = [
        r'\$[\d,]+\.?\d*\s*(?:billion|B)',
        r'\$[\d,]+\.?\d*\s*(?:million|M)',
        r'\$[\d,]+\.?\d*\s*(?:thousand|K)',
        r'\$[\d,]+\.?\d*',
        r'[\d,]+\.?\d*\s*(?:billion|million|thousand)',
    ]
    for pat in patterns:
        match = re.search(pat, text, re.I)
        if match:
            return match.group(0)
    return None


def is_money_connection(conn):
    """Check if a connection involves money flow."""
    rel = conn.relationship.lower().replace('_', ' ')
    return any(kw in rel for kw in MONEY_KEYWORDS) or conn.relationship in MONEY_RELATIONSHIPS


def build_money_flow(graph, output_path, title=None):
    """Generate a money flow visualization from the graph."""

    COLORS = {
        'person': '#E11D48', 'company': '#2563EB', 'location': '#059669',
        'event': '#D97706', 'money': '#7C3AED', 'concept': '#0891B2',
        'government': '#EA580C', 'document': '#6366F1', 'unknown': '#6B7280',
    }

    # Collect money-related connections
    money_conns = []
    for conn in graph.connections:
        if is_money_connection(conn):
            src = graph.entities.get(conn.source_id)
            tgt = graph.entities.get(conn.target_id)
            if src and tgt:
                amount = extract_amount(conn.relationship)
                money_conns.append({
                    'source': conn.source_id,
                    'target': conn.target_id,
                    'source_name': src.name,
                    'target_name': tgt.name,
                    'source_type': src.type,
                    'target_type': tgt.type,
                    'relationship': conn.relationship.replace('_', ' '),
                    'amount': amount or '',
                    'confidence': conn.confidence,
                })

    # Also include ALL connections for entities of type "money"
    for eid, entity in graph.entities.items():
        if entity.type == 'money':
            for conn in graph.get_connections_for(eid):
                src = graph.entities.get(conn.source_id)
                tgt = graph.entities.get(conn.target_id)
                if src and tgt:
                    key = f"{conn.source_id}-{conn.target_id}"
                    if not any(f"{c['source']}-{c['target']}" == key for c in money_conns):
                        money_conns.append({
                            'source': conn.source_id,
                            'target': conn.target_id,
                            'source_name': src.name,
                            'target_name': tgt.name,
                            'source_type': src.type,
                            'target_type': tgt.type,
                            'relationship': conn.relationship.replace('_', ' '),
                            'amount': extract_amount(conn.relationship) or '',
                            'confidence': conn.confidence,
                        })

    # Build unique node list
    node_ids = set()
    for mc in money_conns:
        node_ids.add(mc['source'])
        node_ids.add(mc['target'])

    nodes = []
    node_index = {}
    for i, nid in enumerate(sorted(node_ids)):
        entity = graph.entities.get(nid)
        if entity:
            nodes.append({
                'id': nid,
                'name': entity.name,
                'type': entity.type,
                'color': COLORS.get(entity.type, '#6B7280'),
            })
            node_index[nid] = i

    # Build links for Sankey
    links = []
    for mc in money_conns:
        if mc['source'] in node_index and mc['target'] in node_index:
            links.append({
                'source': node_index[mc['source']],
                'target': node_index[mc['target']],
                'value': max(1, int(mc['confidence'] * 10)),
                'label': mc['relationship'],
                'amount': mc['amount'],
            })

    # Aggregate duplicate links
    agg = defaultdict(lambda: {'value': 0, 'labels': [], 'amounts': []})
    for link in links:
        key = (link['source'], link['target'])
        agg[key]['value'] += link['value']
        agg[key]['labels'].append(link['label'])
        if link['amount']:
            agg[key]['amounts'].append(link['amount'])

    final_links = []
    for (src, tgt), data in agg.items():
        label = data['labels'][0] if data['labels'] else ''
        amount = data['amounts'][0] if data['amounts'] else ''
        final_links.append({
            'source': src,
            'target': tgt,
            'value': data['value'],
            'label': label,
            'amount': amount,
        })

    board_title = title or f"Money Flow: {graph.name}"

    nodes_json = json.dumps(nodes)
    links_json = json.dumps(final_links)

    html = f'''<!DOCTYPE html>
<html lang="en" id="moneyHtml">
<head>
<meta charset="UTF-8"><title>{board_title}</title>
<link rel="stylesheet" href="/static/css/themes.css">
<script src="https://d3js.org/d3.v7.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/d3-sankey@0.12.3/dist/d3-sankey.min.js"></script>
<script>
(function(){{
  var t = localStorage.getItem('deepdive-theme') || 'dark';
  document.getElementById('moneyHtml').setAttribute('data-theme', t);
}})();
</script>
<style>
@import url('https://fonts.googleapis.com/css2?family=Outfit:wght@700;800&family=Inter:wght@400;500;600&display=swap');
*{{margin:0;padding:0;box-sizing:border-box}}
body{{background:var(--bg);color:var(--text);font-family:'Inter',system-ui;overflow:hidden}}
.mf-header{{height:50px;padding:0 24px;display:flex;align-items:center;gap:16px;border-bottom:1px solid var(--glass-border);background:var(--glass-solid);backdrop-filter:var(--blur)}}
.mf-title{{font-family:'Outfit',sans-serif;font-size:16px;font-weight:800;background:var(--brand-gradient);-webkit-background-clip:text;background-clip:text;-webkit-text-fill-color:transparent}}
.mf-stats{{font-size:11px;color:var(--text-muted)}}
.back-btn{{display:inline-flex;align-items:center;padding:5px 12px;background:var(--white);border:1px solid var(--glass-border-hi);border-radius:20px;color:var(--accent);font-size:11px;font-weight:600;text-decoration:none;transition:all .2s}}
.back-btn:hover{{background:var(--accent-lighter);border-color:var(--accent)}}
.print-btn{{padding:6px 14px;background:linear-gradient(135deg,var(--accent),var(--accent-dark));border:none;color:#fff;border-radius:8px;cursor:pointer;font-size:11px;font-weight:600}}
#chart{{width:100vw;height:calc(100vh - 50px)}}
svg text{{font-size:11px;fill:var(--text-secondary)}}
.node rect{{cursor:pointer;stroke:var(--glass-border);stroke-width:1}}
.node rect:hover{{stroke:var(--accent);stroke-width:2}}
.link{{fill:none;stroke-opacity:0.25}}
.link:hover{{stroke-opacity:0.5}}
.node-label{{font-size:11px;font-weight:600}}
.link-label{{font-size:9px;pointer-events:none;fill:var(--text-muted)}}
.mf-tooltip{{position:absolute;background:var(--glass-solid);border:1px solid var(--glass-border);border-radius:10px;padding:12px;font-size:12px;pointer-events:none;display:none;max-width:300px;z-index:100;backdrop-filter:var(--blur);box-shadow:var(--glass-shadow)}}
.mf-tooltip .tt-name{{font-weight:700;color:var(--text);margin-bottom:4px}}
.mf-tooltip .tt-rel{{color:var(--text-muted);font-size:11px}}
.mf-tooltip .tt-amount{{color:var(--accent);font-weight:600;margin-top:4px}}
.no-data{{display:flex;align-items:center;justify-content:center;height:calc(100vh - 50px);flex-direction:column;gap:12px}}
.no-data h2{{color:var(--text-muted);font-size:18px}}
.no-data p{{color:var(--text-muted);font-size:13px;max-width:500px;text-align:center}}
@media print{{.mf-header{{display:none}} .link{{stroke-opacity:0.3}}}}
</style>
</head>
<body>
<div class="mf-header">
  <a href="http://localhost:8766/board" class="back-btn">← Board</a>
  <div class="mf-title">Money Flow — {board_title}</div>
  <span class="mf-stats">{len(money_conns)} financial connections · {len(nodes)} entities</span>
  <button onclick="window.print()" class="print-btn" style="margin-left:auto">Print / PDF</button>
</div>
<div id="chart"></div>
<div class="mf-tooltip" id="tooltip"></div>

<script>
const nodes = {nodes_json};
const links = {links_json};

if (nodes.length === 0 || links.length === 0) {{
    document.getElementById('chart').innerHTML = `
        <div class="no-data">
            <h2>No Financial Connections Found</h2>
            <p>This investigation hasn't uncovered money flow data yet. Try using the Money Trace tool on specific entities, or expand your investigation to include financial connections.</p>
            <a href="http://localhost:8766/board" class="back-btn" style="margin-top:12px">Back to Graph</a>
        </div>`;
}} else {{
    const width = window.innerWidth;
    const height = window.innerHeight - 50;
    const margin = {{top: 20, right: 200, bottom: 20, left: 200}};

    const svg = d3.select('#chart').append('svg')
        .attr('width', width).attr('height', height);

    const sankey = d3.sankey()
        .nodeId(d => d.index)
        .nodeWidth(20)
        .nodePadding(16)
        .nodeAlign(d3.sankeyJustify)
        .extent([[margin.left, margin.top], [width - margin.right, height - margin.bottom]]);

    const data = sankey({{
        nodes: nodes.map((d, i) => ({{...d, index: i}})),
        links: links.map(d => ({{...d}}))
    }});

    const tooltip = document.getElementById('tooltip');

    // Draw links
    svg.append('g').selectAll('.link')
        .data(data.links)
        .join('path')
        .attr('class', 'link')
        .attr('d', d3.sankeyLinkHorizontal())
        .attr('stroke', d => nodes[d.source.index]?.color || '#7C3AED')
        .attr('stroke-width', d => Math.max(2, d.width))
        .on('mouseover', function(event, d) {{
            d3.select(this).attr('stroke-opacity', 0.6);
            const src = nodes[d.source.index];
            const tgt = nodes[d.target.index];
            let html = `<div class="tt-name">${{src?.name || '?'}} → ${{tgt?.name || '?'}}</div>`;
            html += `<div class="tt-rel">${{d.label || 'connection'}}</div>`;
            if (d.amount) html += `<div class="tt-amount">${{d.amount}}</div>`;
            tooltip.innerHTML = html;
            tooltip.style.display = 'block';
            tooltip.style.left = (event.pageX + 10) + 'px';
            tooltip.style.top = (event.pageY - 10) + 'px';
        }})
        .on('mouseout', function() {{
            d3.select(this).attr('stroke-opacity', 0.25);
            tooltip.style.display = 'none';
        }});

    // Draw nodes
    const node = svg.append('g').selectAll('.node')
        .data(data.nodes)
        .join('g')
        .attr('class', 'node');

    node.append('rect')
        .attr('x', d => d.x0).attr('y', d => d.y0)
        .attr('height', d => Math.max(4, d.y1 - d.y0))
        .attr('width', d => d.x1 - d.x0)
        .attr('fill', d => d.color || '#6B7280')
        .attr('rx', 3)
        .on('mouseover', function(event, d) {{
            let html = `<div class="tt-name">${{d.name}}</div>`;
            html += `<div class="tt-rel">Type: ${{d.type}}</div>`;
            const inflow = d.targetLinks?.reduce((s, l) => s + l.value, 0) || 0;
            const outflow = d.sourceLinks?.reduce((s, l) => s + l.value, 0) || 0;
            html += `<div class="tt-rel">Inflow: ${{inflow}} | Outflow: ${{outflow}}</div>`;
            tooltip.innerHTML = html;
            tooltip.style.display = 'block';
            tooltip.style.left = (event.pageX + 10) + 'px';
            tooltip.style.top = (event.pageY - 10) + 'px';
        }})
        .on('mouseout', () => {{ tooltip.style.display = 'none'; }});

    // Labels
    node.append('text')
        .attr('class', 'node-label')
        .attr('x', d => d.x0 < width / 2 ? d.x0 - 8 : d.x1 + 8)
        .attr('y', d => (d.y0 + d.y1) / 2)
        .attr('dy', '0.35em')
        .attr('text-anchor', d => d.x0 < width / 2 ? 'end' : 'start')
        .text(d => d.name.length > 30 ? d.name.slice(0, 28) + '...' : d.name);
}}
</script></body></html>'''

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, 'w') as f:
        f.write(html)
    return output_path, len(money_conns)
