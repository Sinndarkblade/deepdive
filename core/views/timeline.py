#!/usr/bin/env python3
"""
Timeline View — generates a chronological HTML timeline from graph events.
"""

import re
import os


def extract_date(text):
    """Try to extract a date/year from entity name or metadata."""
    # Look for years
    years = re.findall(r'((?:19|20)\d{2})', text)
    if years:
        return years[0]

    # Look for month-year patterns
    months = re.findall(r'((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*\s+\d{4})', text, re.I)
    if months:
        return months[0]

    # Look for YYYY-MM patterns
    ym = re.findall(r'(\d{4}-\d{2})', text)
    if ym:
        return ym[0]

    return None


def build_timeline(graph, output_path, title=None):
    """Generate a timeline HTML page from the graph's event entities."""

    events = []
    for eid, entity in graph.entities.items():
        # Get date from entity name, metadata, or connections
        date = None
        date_source = entity.name

        # Check metadata for dates
        for key in ['date', 'year', 'when', 'time_period', 'founded']:
            if key in entity.metadata:
                date = extract_date(str(entity.metadata[key]))
                if date:
                    break

        # Check entity name for dates
        if not date:
            date = extract_date(entity.name)

        # Check connection relationships for dates
        if not date:
            for conn in graph.get_connections_for(eid):
                date = extract_date(conn.relationship)
                if date:
                    break

        if not date:
            continue  # Skip entities with no date

        # Get connections for context
        conns = graph.get_connections_for(eid)
        connected = []
        for conn in conns[:5]:
            other_id = conn.target_id if conn.source_id == eid else conn.source_id
            other = graph.entities.get(other_id)
            if other:
                connected.append({'name': other.name, 'type': other.type, 'rel': conn.relationship})

        events.append({
            'id': eid,
            'name': entity.name,
            'type': entity.type,
            'date': date,
            'date_sort': date.replace('-', '').ljust(8, '0'),
            'metadata': entity.metadata,
            'connections': connected,
            'confidence': max((c.confidence for c in conns), default=0.5),
            'investigated': entity.investigated,
        })

    # Sort by date
    events.sort(key=lambda e: e['date_sort'])

    COLORS = {
        'person': '#e74c3c', 'company': '#3498db', 'location': '#2ecc71',
        'event': '#f39c12', 'money': '#9b59b6', 'document': '#1abc9c',
        'government': '#e67e22', 'concept': '#00ccaa', 'unknown': '#7f8c8d',
    }

    board_title = title or f"Timeline: {graph.name}"

    # Build event cards HTML
    cards_html = ""
    for i, ev in enumerate(events):
        color = COLORS.get(ev['type'], '#7f8c8d')
        side = 'left' if i % 2 == 0 else 'right'
        conn_html = ""
        for c in ev['connections']:
            ccolor = COLORS.get(c['type'], '#7f8c8d')
            conn_html += f'<div class="tl-conn"><span style="color:{ccolor}">●</span> {c["name"]} <span class="tl-rel">{c["rel"]}</span></div>'

        meta_html = ""
        for k, v in ev.get('metadata', {}).items():
            if k not in ('pinned', 'notes', 'source', 'config') and v:
                meta_html += f'<div class="tl-meta"><span class="tl-mk">{k}:</span> {str(v)[:100]}</div>'

        # Escape for data attribute
        import html as html_mod
        meta_json = html_mod.escape(str(ev.get('metadata', {})).replace("'", ""))
        conn_json_parts = []
        for c in ev['connections']:
            ccolor = COLORS.get(c['type'], '#7f8c8d')
            conn_json_parts.append(f'{c["name"]}|{c["type"]}|{c["rel"].replace("_", " ")}|{ccolor}')
        conn_data = html_mod.escape(';;'.join(conn_json_parts))

        cards_html += f'''
        <div class="tl-item tl-{side}">
            <div class="tl-date">{ev['date']}</div>
            <div class="tl-card" style="border-left:3px solid {color}" onclick="showTlDetail(this)" data-name="{html_mod.escape(ev['name'])}" data-type="{ev['type']}" data-color="{color}" data-conns="{conn_data}" data-meta="{meta_json}">
                <div class="tl-name" style="color:{color}">{ev['name']}</div>
                <div class="tl-type">{ev['type']}</div>
            </div>
        </div>'''

    html = f'''<!DOCTYPE html>
<html lang="en" id="timelineHtml">
<head>
<meta charset="UTF-8"><title>{board_title}</title>
<link rel="stylesheet" href="/static/css/themes.css">
<link rel="stylesheet" href="/static/css/views-shared.css">
<script>
(function(){{
  var t = localStorage.getItem('deepdive-theme') || 'dark';
  document.getElementById('timelineHtml').setAttribute('data-theme', t);
}})();
</script>
<style>
.tl-title{{font-family:'Outfit',sans-serif;font-size:22px;font-weight:800;background:var(--brand-gradient);-webkit-background-clip:text;background-clip:text;-webkit-text-fill-color:transparent;text-align:center;margin-bottom:4px}}
.tl-stats{{text-align:center;color:var(--text-muted);font-size:12px;margin-bottom:20px}}

.timeline{{position:relative;max-width:900px;margin:0 auto}}
.timeline::before{{content:'';position:absolute;left:50%;width:2px;background:var(--glass-border);top:0;bottom:0;transform:translateX(-50%)}}

.tl-item{{position:relative;width:50%;padding:10px 30px;margin-bottom:4px}}
.tl-left{{left:0;text-align:right}}
.tl-right{{left:50%;text-align:left}}

.tl-item::after{{content:'';position:absolute;top:14px;width:10px;height:10px;background:var(--accent);border-radius:50%;z-index:1}}
.tl-left::after{{right:-5px}}
.tl-right::after{{left:-5px}}

.tl-date{{font-size:11px;color:var(--accent);font-weight:600;margin-bottom:4px}}
.tl-card{{background:var(--glass-solid);border-radius:10px;padding:10px;border:1px solid var(--glass-border);cursor:pointer;max-width:380px;overflow:hidden;backdrop-filter:var(--blur);transition:border-color .2s}}
.tl-card:hover{{border-color:var(--accent)}}
.tl-left .tl-card{{margin-left:auto}}
.tl-name{{font-size:13px;font-weight:600;margin-bottom:2px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;color:var(--text)}}
.tl-type{{font-size:9px;color:var(--text-muted);text-transform:uppercase;margin-bottom:4px}}
.tl-meta{{font-size:10px;color:var(--text-secondary);padding:1px 0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
.tl-mk{{color:var(--text-muted)}}
.tl-conn{{font-size:10px;color:var(--text-secondary);padding:1px 0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
.tl-rel{{color:var(--text-muted);font-size:9px}}

#detailOverlay{{display:none;position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,0.6);z-index:200;justify-content:center;align-items:center}}
#detailOverlay.show{{display:flex}}
#detailBox{{background:var(--glass-solid);border:1px solid var(--glass-border);border-radius:14px;padding:20px;max-width:600px;width:90%;max-height:80vh;overflow-y:auto;box-shadow:var(--glass-shadow-lg);backdrop-filter:var(--blur)}}
#detailBox h2{{font-size:17px;margin-bottom:4px}}
#detailBox .d-type{{color:var(--text-muted);font-size:11px;text-transform:uppercase;margin-bottom:10px}}
#detailBox .d-meta{{font-size:12px;color:var(--text-secondary);padding:3px 0}}
#detailBox .d-section{{color:var(--accent);font-size:12px;font-weight:600;margin-top:12px;margin-bottom:4px;border-bottom:1px solid var(--glass-border);padding-bottom:3px}}
#detailBox .d-conn{{font-size:12px;color:var(--text-secondary);padding:3px 0}}
#detailBox .d-close{{position:absolute;top:12px;right:16px;color:var(--text-muted);cursor:pointer;font-size:20px}}

.tl-filter{{display:flex;flex-wrap:wrap;justify-content:center;gap:4px;margin-bottom:20px}}
.tl-filter label{{font-size:10px;color:var(--text-muted);cursor:pointer;padding:2px 8px;background:var(--white);border-radius:4px;border:1px solid var(--glass-border)}}
.tl-filter label:hover{{border-color:var(--accent)}}
.tl-filter input{{display:none}}
.tl-filter input:checked+span{{color:var(--accent)}}

@media print{{
  .back-bar,.tl-filter{{display:none}}
  .tl-card{{box-shadow:none}}
  .timeline::before{{background:#ccc}}
}}
</style>
</head>
<body>

<div class="back-bar">
  <a href="http://localhost:8766/board" class="back-btn">← Board</a>
  <span class="back-bar-title">Timeline</span>
</div>

<div class="page">
<div class="tl-title">📅 {board_title}</div>
<div class="tl-stats">{len(events)} dated events from {graph.name} · {len(graph.entities)} total entities</div>

<div class="tl-filter" id="typeFilter">
    {"".join(f'<label><input type="checkbox" checked onchange="filterTimeline()" value="{t}"><span style="color:{c}"> ● {t}</span></label>' for t, c in COLORS.items() if any(e["type"] == t for e in events))}
</div>

<div id="detailOverlay" onclick="if(event.target===this)this.classList.remove('show')">
<div id="detailBox" style="position:relative"><span class="d-close" onclick="document.getElementById('detailOverlay').classList.remove('show')">✕</span><div id="detailContent"></div></div>
</div>

<div class="timeline" id="timeline">
{cards_html}
</div>
</div>

<script>
function clean(s){{return s?s.replace(/_/g,' '):''}}

function showTlDetail(el){{
    const name=clean(el.dataset.name);
    const type=el.dataset.type;
    const color=el.dataset.color;
    const meta=el.dataset.meta;
    const connsRaw=el.dataset.conns;

    let h='<h2 style="color:'+color+'">'+name+'</h2>';
    h+='<div class="d-type">'+type+'</div>';

    if(meta&&meta!=='{{}}'){{
        h+='<div class="d-section">Details</div>';
        meta.replace(/[{{}}]/g,'').split(',').forEach(pair=>{{
            const p=clean(pair.trim());
            if(p)h+='<div class="d-meta">'+p+'</div>';
        }});
    }}

    if(connsRaw){{
        h+='<div class="d-section">Connections</div>';
        connsRaw.split(';;').forEach(c=>{{
            const parts=c.split('|');
            if(parts.length>=4){{
                const cname=clean(parts[0]);
                const ctype=parts[1];
                const crel=clean(parts[2]);
                const ccolor=parts[3];
                h+='<div class="d-conn" style="cursor:pointer" onclick="event.stopPropagation();openConnTile(&apos;'+cname+'&apos;,&apos;'+ctype+'&apos;,&apos;'+ccolor+'&apos;)"><span style="color:'+ccolor+'">●</span> <b>'+cname+'</b> <span style="color:#64748b">('+ctype+')</span> — <span style="color:#8a8f98">'+crel+'</span></div>';
            }}
        }});
    }}

    // Check if report exists
    h+='<div id="tlReportSection" style="margin-top:12px"></div>';
    h+='<div style="margin-top:6px;display:flex;gap:6px">';
    h+='<button onclick="event.stopPropagation();generateTlReport(&apos;'+name+'&apos;)" style="flex:1;padding:6px;background:#9b59b622;border:1px solid #9b59b6;color:#9b59b6;border-radius:6px;cursor:pointer;font-size:11px">📄 Generate Report</button>';
    h+='</div>';

    // Check for existing report
    checkExistingReport(name);

    document.getElementById('detailContent').innerHTML=h;
    document.getElementById('detailOverlay').classList.add('show');
}}

// Open a connected entity as a floating tile
let tileCount=0;
function openConnTile(name,type,color){{
    tileCount++;
    const tile=document.createElement('div');
    tile.style.cssText='position:fixed;top:'+(60+tileCount*30)+'px;right:'+(20+tileCount*20)+'px;width:350px;max-height:400px;overflow-y:auto;background:#0a0e1a;border:1px solid #1e293b;border-radius:10px;padding:14px;z-index:'+(100+tileCount)+';box-shadow:0 8px 32px rgba(0,0,0,0.5)';
    tile.innerHTML='<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px"><h3 style="color:'+color+';font-size:14px">'+name+'</h3><span style="cursor:pointer;color:#64748b;font-size:16px" onclick="this.parentElement.parentElement.remove();tileCount--">✕</span></div>'
    +'<div style="color:#64748b;font-size:10px;text-transform:uppercase;margin-bottom:8px">'+type+'</div>'
    +'<div style="color:#8a8f98;font-size:11px">Click "Generate Report" in the main detail panel for full analysis of this entity.</div>';
    document.body.appendChild(tile);
}}

function checkExistingReport(name){{
    const id=name.toLowerCase().replace(/ /g,'_');
    fetch('http://localhost:8766/report/get',{{
        method:'POST',headers:{{'Content-Type':'application/json'}},
        body:JSON.stringify({{id:id}})
    }}).then(r=>r.json()).then(d=>{{
        const section=document.getElementById('tlReportSection');
        if(d.exists&&section){{
            section.innerHTML='<div class="d-section">📄 Report</div>'
                +'<div style="background:#111827;border-radius:6px;padding:10px;max-height:300px;overflow-y:auto;font-size:11px;line-height:1.6;color:#c0c8e0;white-space:pre-wrap">'+d.content.replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/\\[\\[([^\\]]+)\\]\\]/g,'<span style="color:#00ccaa;cursor:pointer" onclick="event.stopPropagation();openConnTile(&apos;$1&apos;,&apos;unknown&apos;,&apos;#00ccaa&apos;)">$1</span>')+'</div>';
        }}
    }}).catch(()=>{{}});
}}

function generateTlReport(name){{
    // Show status bar
    let status=document.getElementById('tlStatus');
    if(!status){{
        status=document.createElement('div');
        status.id='tlStatus';
        status.style.cssText='position:fixed;bottom:0;left:0;right:0;background:#00ccaa;color:#050810;padding:10px 20px;font-size:13px;font-weight:600;text-align:center;z-index:200';
        document.body.appendChild(status);
    }}
    status.style.display='block';
    status.textContent='📄 Generating report for '+name+'... this may take a minute';

    fetch('http://localhost:8766/report',{{
        method:'POST',headers:{{'Content-Type':'application/json'}},
        body:JSON.stringify({{id:name.toLowerCase().replace(/ /g,'_'),label:name}})
    }}).then(r=>r.json()).then(d=>{{
        if(d.success){{
            status.innerHTML='✅ Report saved: <a href="file://'+d.path+'" target="_blank" style="color:#050810;text-decoration:underline">'+d.path+'</a> <span onclick="this.parentElement.style.display=&quot;none&quot;" style="cursor:pointer;margin-left:20px">✕</span>';
            checkExistingReport(name);
        }} else {{
            status.innerHTML='❌ '+(d.error||'Failed')+' <span onclick="this.parentElement.style.display=&quot;none&quot;" style="cursor:pointer;margin-left:20px">✕</span>';
        }}
    }}).catch(()=>{{
        status.innerHTML='❌ Server error <span onclick="this.parentElement.style.display=&quot;none&quot;" style="cursor:pointer;margin-left:20px">✕</span>';
    }});
}}

function filterTimeline(){{
    const checked=new Set();
    document.querySelectorAll('#typeFilter input:checked').forEach(cb=>checked.add(cb.value));
    document.querySelectorAll('.tl-item').forEach(item=>{{
        const card=item.querySelector('.tl-type');
        const type=card?card.textContent.trim().toLowerCase():'';
        item.style.display=checked.has(type)?'':'none';
    }});
}}
</script>
</body></html>'''

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, 'w') as f:
        f.write(html)
    return output_path, len(events)
