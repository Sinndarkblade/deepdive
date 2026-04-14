"""
Investigation Routes — create, switch, list, expand, investigate, gaps.
"""

import json
import os

from graph import InvestigationGraph, Entity, Connection
from extractors import extract_entities
from interview import InvestigationConfig
from utils import extract_subject

import server.state as state


def do_expand(entity_id, entity_name, search_mode="web", enabled_feeds=None, preview_only=False):
    """Expand an entity. If preview_only=True, finds entities but doesn't add to graph.
    Returns (success, added_count, added_entities, feed_summary, error)."""
    if not state.GRAPH:
        return False, 0, None, None, "No investigation or model loaded"

    entity = state.GRAPH.entities.get(entity_id)
    if not entity:
        return False, 0, None, None, f"Entity {entity_id} not found"

    # Build existing context
    existing_conns = state.GRAPH.get_connections_for(entity_id)
    context_parts = []
    for conn in existing_conns:
        other_id = conn.target_id if conn.source_id == entity_id else conn.source_id
        other = state.GRAPH.entities.get(other_id)
        if other:
            context_parts.append(f"{other.name} ({conn.relationship})")
    known = "Already known: " + ", ".join(context_parts) if context_parts else ""

    # Search based on mode
    search_text = ""
    if search_mode in ("local", "both") and state.DATASET_PATH:
        from search.local_files import LocalFileSearch
        local = LocalFileSearch(state.DATASET_PATH)
        if local.index():
            results = local.search(entity_name, max_results=15)
            for r in results:
                search_text += r.get('body', '') + "\n"
            if search_text:
                search_text = f"LOCAL DOCUMENTS ({len(results)} matches):\n" + search_text

    if search_mode in ("web", "both") and state.ENGINES:
        for engine in state.ENGINES:
            try:
                results, text = engine.deep_search(entity_name)
                if text:
                    search_text += text[:4000] + "\n"
            except Exception as e:
                print(f"[DiveServer] Search error ({engine.name}): {e}")

    full_context = ""
    if search_text:
        full_context += "SEARCH RESULTS:\n" + search_text[:8000] + "\n\n"
    if known:
        full_context += known

    try:
        response, feed_results = state.BRIDGE.research(
            entity_name, entity.type, full_context, enabled_feeds=enabled_feeds)
    except Exception as e:
        return False, 0, None, None, f"Model error: {e}"

    if not response or response.startswith("Error"):
        return False, 0, None, None, f"Model returned: {response}"

    extracted = extract_entities(response)

    # If model returned prose instead of structured output, try a second
    # extraction pass with a stricter prompt
    if not extracted and response and len(response) > 50:
        print(f"[DiveServer] First extraction failed for {entity_name}, trying fallback...")
        retry_prompt = f"""The following text contains information about "{entity_name}".
Extract EVERY person, company, location, event, and financial amount mentioned.

TEXT:
{response[:3000]}

Output ONLY in this format, one per line:
ENTITY_NAME | ENTITY_TYPE | RELATIONSHIP | CONFIDENCE

Example:
Jeffrey Epstein | person | associated_with | high
New York | location | sentenced_in | high
$30 million | money | amount_involved | medium

Output ONLY entity lines. No other text."""

        retry_response = state.BRIDGE._call(retry_prompt)
        if retry_response and not retry_response.startswith("Error"):
            extracted = extract_entities(retry_response)
            print(f"[DiveServer] Fallback extraction: {len(extracted)} entities")

    added = 0
    added_entities = []
    for name, etype, rel, conf in extracted:
        new_entity = Entity(name, etype)
        if new_entity.id == entity_id:
            continue
        added_entities.append({'name': name, 'type': etype, 'relationship': rel,
                               'confidence': conf, 'source_id': entity_id})

        if not preview_only:
            new_entity.depth = entity.depth + 1
            new_entity.sources.append(f"Expanded from {entity.name}")
            is_new = state.GRAPH.add_entity(new_entity)
            if is_new:
                added += 1
            state.GRAPH.add_connection(Connection(entity_id, new_entity.id, rel, conf))

    if not preview_only:
        state.GRAPH.mark_investigated(entity_id)
        state.GRAPH.save(state.INV_PATH)
        _rebuild_board()
    else:
        added = len(added_entities)  # In preview mode, "added" means "found"

    # Format feed results for the UI
    feed_summary = _format_feed_results(feed_results)

    print(f"[DiveServer] {'Previewed' if preview_only else 'Expanded'} {entity_name}: {len(added_entities)} entities")
    return True, added, added_entities, feed_summary, None


def do_investigate(subject):
    """Start a full investigation on a subject."""
    title = extract_subject(subject)

    inv_root = state.get_investigations_root()
    os.makedirs(inv_root, exist_ok=True)
    inv_dir = os.path.join(inv_root, title.lower().replace(' ', '_')[:50])
    os.makedirs(inv_dir, exist_ok=True)

    seed = Entity(title, "unknown", {"source": "user_input"})
    graph = InvestigationGraph(title, seed)

    print(f"[DiveServer] Researching: {subject}")
    try:
        response, _ = state.BRIDGE.research(subject, "unknown", "")
    except Exception as e:
        return False, 0, f"Research error: {e}"

    if not response or response.startswith("Error"):
        return False, 0, f"Model returned: {response}"

    extracted = extract_entities(response)
    added = 0
    for name, etype, rel, conf in extracted:
        new_entity = Entity(name, etype)
        if new_entity.id == seed.id:
            continue
        new_entity.depth = 1
        is_new = graph.add_entity(new_entity)
        if is_new:
            added += 1
        graph.add_connection(Connection(seed.id, new_entity.id, rel, conf))

    graph.mark_investigated(seed.id)
    graph.detect_gaps()
    graph.save(inv_dir)
    _rebuild_board_for(graph, inv_dir, subject)

    state.GRAPH = graph
    state.INV_PATH = inv_dir

    print(f"[DiveServer] Investigation: {subject} — {added} entities")
    return True, added, None


def do_investigate_with_config(config, expand_current=False):
    """Run investigation using interview config."""
    subject = config.subject
    if not subject:
        return False, 0, "No subject provided"

    title = extract_subject(subject)
    enabled_feeds = config.enabled_feeds if config.enabled_feeds else None

    if expand_current and state.GRAPH and state.INV_PATH:
        graph = state.GRAPH
        inv_dir = state.INV_PATH
        seed_id = title.lower().strip().replace(" ", "_")
        if seed_id in graph.entities:
            seed = graph.entities[seed_id]
        else:
            seed = Entity(title, "unknown", {"source": "node_investigation"})
            graph.add_entity(seed)
    else:
        inv_root = state.get_investigations_root()
        os.makedirs(inv_root, exist_ok=True)
        inv_dir = os.path.join(inv_root, title.lower().replace(' ', '_')[:50])
        os.makedirs(inv_dir, exist_ok=True)
        seed = Entity(title, "unknown", {"source": "interview", "config": json.dumps(config.to_dict())})
        graph = InvestigationGraph(title, seed)

    search_prompt = config.build_search_prompt()
    depth_config = config.get_depth_config()

    # Pass 1
    print(f"[Investigation] Pass 1: {subject}")
    response, _ = state.BRIDGE.research(subject, "unknown", search_prompt, enabled_feeds=enabled_feeds)

    if not response or response.startswith("Error"):
        return False, 0, f"Research error: {response}"

    extracted = extract_entities(response)
    total_added = 0
    for name, etype, rel, conf in extracted:
        new_entity = Entity(name, etype)
        if new_entity.id == seed.id:
            continue
        new_entity.depth = 1
        is_new = graph.add_entity(new_entity)
        if is_new:
            total_added += 1
        graph.add_connection(Connection(seed.id, new_entity.id, rel, conf))

    graph.mark_investigated(seed.id)

    # Additional passes
    max_passes = depth_config["passes"]
    expand_per = depth_config["expand_per_pass"]
    if max_passes == 0:
        max_passes = 20

    pass_num = 2
    while pass_num <= max_passes and expand_per > 0:
        candidates = [
            (eid, len(graph.get_connections_for(eid)))
            for eid, e in graph.entities.items()
            if not e.investigated
        ]
        candidates.sort(key=lambda x: -x[1])
        to_expand = candidates[:expand_per]

        if not to_expand:
            break

        new_this_pass = 0
        for eid, _ in to_expand:
            entity = graph.entities[eid]
            print(f"[Investigation] Pass {pass_num}: expanding {entity.name}")
            resp, _ = state.BRIDGE.research(entity.name, entity.type, search_prompt,
                                            enabled_feeds=enabled_feeds)
            if not resp or resp.startswith("Error"):
                continue
            extr = extract_entities(resp)
            for name, etype, rel, conf in extr:
                new_e = Entity(name, etype)
                if new_e.id == eid:
                    continue
                new_e.depth = entity.depth + 1
                is_new = graph.add_entity(new_e)
                if is_new:
                    new_this_pass += 1
                    total_added += 1
                graph.add_connection(Connection(eid, new_e.id, rel, conf))
            graph.mark_investigated(eid)

        if new_this_pass == 0:
            break
        pass_num += 1

    graph.detect_gaps()
    graph.save(inv_dir)
    _rebuild_board_for(graph, inv_dir, subject)

    state.GRAPH = graph
    state.INV_PATH = inv_dir

    print(f"[Investigation] Complete: {subject} — {total_added} entities, {pass_num - 1} passes")
    return True, total_added, None


def do_generate_report(entity_id, entity_name):
    """Generate a detailed markdown report for an entity."""
    if not state.GRAPH:
        return False, None, "No investigation loaded"

    entity = state.GRAPH.entities.get(entity_id)
    if not entity:
        return False, None, f"Entity {entity_id} not found"

    conns = state.GRAPH.get_connections_for(entity_id)
    conn_details = []
    for conn in conns:
        other_id = conn.target_id if conn.source_id == entity_id else conn.source_id
        other = state.GRAPH.entities.get(other_id)
        if other:
            conn_details.append({
                'name': other.name, 'type': other.type,
                'relationship': conn.relationship, 'confidence': conn.confidence,
                'metadata': other.metadata,
                'direction': 'outgoing' if conn.source_id == entity_id else 'incoming',
            })

    conn_text = "\n".join(
        f"- {c['name']} ({c['type']}) — {c['relationship']} (confidence: {c['confidence']}, {c['direction']})"
        + (f" | Details: {c['metadata']}" if c['metadata'] else "")
        for c in conn_details
    )

    findings_text = chr(10).join(f for f in state.GRAPH.findings if entity_name.lower() in f.lower())
    prompt = f"""Write a structured intelligence report in markdown format for "{entity_name}".

SUBJECT: {entity_name} ({entity.type})
INVESTIGATION: {state.GRAPH.name}

KNOWN CONNECTIONS ({len(conn_details)}):
{conn_text}

{('ADDITIONAL FINDINGS:\n' + findings_text) if findings_text else ''}

Write the report in this structure:
# {entity_name} — Intelligence Report

## Executive Summary
[2-3 paragraph overview of who/what this is and why they matter]

## Key Connections
[Describe each significant connection and why it matters]

## Financial Activity
[Any money flows, investments, transactions]

## Legal & Regulatory
[Court cases, charges, regulatory actions]

## Suspicious Patterns
[Anything unusual, contradictory, or worth investigating further]

## Gaps & Next Steps
[What's missing, what to investigate next]

Use [[Entity Name]] format for cross-references. Be specific and factual."""

    try:
        response = state.BRIDGE._call(prompt, timeout=300)
    except Exception as e:
        return False, None, f"Model error: {e}"

    if not response or response.startswith("Error"):
        response = f"# {entity_name}\n\n**Type:** {entity.type}\n"
        for c in sorted(conn_details, key=lambda x: -x['confidence']):
            response += f"- **[[{c['name']}]]** ({c['type']}) — {c['relationship']}\n"

    reports_dir = os.path.join(state.INV_PATH, 'reports')
    os.makedirs(reports_dir, exist_ok=True)
    safe_name = entity_name.replace('/', '_').replace('\\', '_').replace(':', '_')[:80]
    report_path = os.path.join(reports_dir, f"{safe_name}.md")

    with open(report_path, 'w') as f:
        f.write(response)

    return True, os.path.abspath(report_path), None


def do_research_gaps(max_gaps=5, status_callback=None):
    """Actively research the top suspicious gaps."""
    if not state.GRAPH:
        return False, 0, 0, "No investigation or model loaded"

    gaps = state.GRAPH.detect_gaps()
    if not gaps:
        return True, 0, 0, "No gaps to research"

    top_gaps = [g for g in gaps if not g.get('researched', False)][:max_gaps]
    if not top_gaps:
        return True, 0, 0, "All gaps already researched"

    connections_found = 0
    gaps_researched = 0

    for i, gap in enumerate(top_gaps):
        a_name, c_name, b_name = gap['a_name'], gap['c_name'], gap['b_name']
        if status_callback:
            status_callback(f"Gap {i + 1}/{len(top_gaps)}: searching {a_name} ↔ {c_name}...")

        context = f"""INVESTIGATING A GAP in the "{state.GRAPH.name}" investigation.
{a_name} and {c_name} both connect to {b_name} but have NO direct connection.
Suspicion score: {gap['score']}/10
Search for ANY connection between {a_name} and {c_name}."""

        try:
            response, _ = state.BRIDGE.research(f"{a_name} AND {c_name}", "gap_research", context)
        except Exception as e:
            print(f"[DiveServer] Gap research error: {e}")
            continue

        if not response or response.startswith("Error"):
            continue

        gaps_researched += 1

        if "NO CONNECTION FOUND" not in response.upper():
            extracted = extract_entities(response)
            for name, etype, rel, conf in extracted:
                new_entity = Entity(name, etype, {"source": "gap_research"})
                state.GRAPH.add_entity(new_entity)
                state.GRAPH.add_connection(Connection(gap['entity_a'], new_entity.id, rel, conf))
                state.GRAPH.add_connection(Connection(gap['entity_c'], new_entity.id, rel, conf))

            rel_found = "related_to"
            for keyword, rel_type in [
                ("business", "partner_of"), ("met", "met_with"), ("paid", "paid_by"),
                ("invested", "invested_in"), ("worked", "works_for"), ("board", "board_member"),
            ]:
                if keyword in response.lower():
                    rel_found = rel_type
                    break

            state.GRAPH.add_connection(Connection(gap['entity_a'], gap['entity_c'], rel_found, 0.5))
            connections_found += 1
            state.GRAPH.findings.append(f"GAP FILLED: {a_name} ↔ {c_name} — {rel_found}")
        else:
            state.GRAPH.findings.append(f"GAP CONFIRMED: {a_name} and {c_name} — no apparent connection")

        gap['researched'] = True

    state.GRAPH.save(state.INV_PATH)
    _rebuild_board()
    return True, gaps_researched, connections_found, None


def do_scan_dataset(folder_path, status_callback=None):
    """Scan a local document folder, extract entities."""
    state.DATASET_PATH = folder_path

    if not state.GRAPH:
        return False, 0, 0, "No investigation or model loaded"

    if not os.path.isdir(folder_path):
        return False, 0, 0, f"Folder not found: {folder_path}"

    from search.local_files import LocalFileSearch
    local = LocalFileSearch(folder_path)
    if not local.index():
        return False, 0, 0, f"Could not index {folder_path}"

    files_indexed = len(local.file_cache)
    if status_callback:
        status_callback(f"Indexed {files_indexed} files. Searching...")

    search_queries = [state.GRAPH.name]
    by_conns = sorted(state.GRAPH.entities.items(), key=lambda x: -len(state.GRAPH.get_connections_for(x[0])))
    for eid, entity in by_conns[:10]:
        search_queries.append(entity.name)

    all_text_parts = []
    total_hits = 0
    for query in search_queries:
        results = local.search(query, max_results=10)
        total_hits += len(results)
        for r in results:
            all_text_parts.append(r.get('body', ''))

    if not all_text_parts:
        return True, files_indexed, 0, "No relevant content found"

    combined_text = "\n".join(all_text_parts)[:12000]
    if status_callback:
        status_callback(f"Found {total_hits} passages. AI analyzing...")

    prompt_context = f"DOCUMENT CORPUS ANALYSIS for: {state.GRAPH.name}\n\n{combined_text}"

    try:
        response, _ = state.BRIDGE.research(state.GRAPH.name, "investigation", prompt_context)
    except Exception as e:
        return False, files_indexed, 0, f"Model error: {e}"

    if not response or response.startswith("Error"):
        return False, files_indexed, 0, f"Model returned: {response}"

    extracted = extract_entities(response)
    added = 0
    seed_id = list(state.GRAPH.entities.keys())[0]

    for name, etype, rel, conf in extracted:
        new_entity = Entity(name, etype, {"source": f"dataset:{folder_path}"})
        if new_entity.id == seed_id:
            continue
        if new_entity.id in state.GRAPH.entities:
            state.GRAPH.findings.append(f"CROSS-LINK (dataset): {name} found in documents AND graph")
        new_entity.depth = 1
        is_new = state.GRAPH.add_entity(new_entity)
        if is_new:
            added += 1
        state.GRAPH.add_connection(Connection(seed_id, new_entity.id, rel, conf))

    state.GRAPH.save(state.INV_PATH)
    _rebuild_board()
    return True, files_indexed, added, None


def list_investigations():
    """List all saved investigations."""
    inv_root = state.get_investigations_root()
    results = []
    if not os.path.isdir(inv_root):
        return results
    for d in sorted(os.listdir(inv_root)):
        full = os.path.join(inv_root, d)
        if not os.path.isdir(full):
            continue
        json_files = [f for f in os.listdir(full) if f.endswith('.json')]
        if not json_files:
            continue
        try:
            with open(os.path.join(full, json_files[0])) as f:
                data = json.load(f)
            results.append({
                'dir': full,
                'name': data.get('name', d),
                'entities': len(data.get('entities', {})),
                'connections': len(data.get('connections', [])),
                'active': os.path.abspath(full) == os.path.abspath(state.INV_PATH) if state.INV_PATH else False,
            })
        except:
            results.append({'dir': full, 'name': d, 'entities': 0, 'connections': 0, 'active': False})
    return results


def switch_investigation(inv_dir):
    """Switch to a different investigation."""
    if not os.path.isdir(inv_dir):
        return False, f"Not found: {inv_dir}", None
    json_files = [f for f in os.listdir(inv_dir) if f.endswith('.json')]
    if not json_files:
        return False, "No investigation data", None
    try:
        state.GRAPH = InvestigationGraph.load(os.path.join(inv_dir, json_files[0]))
        state.INV_PATH = inv_dir
        _rebuild_board()
        print(f"[DiveServer] Switched to: {state.GRAPH.name} ({len(state.GRAPH.entities)} entities)")
        return True, None, os.path.abspath(os.path.join(inv_dir, 'board_3d.html'))
    except Exception as e:
        return False, str(e), None


def create_new_investigation(name):
    """Create a new empty investigation."""
    if not name:
        return False, "Name required", None
    inv_root = state.get_investigations_root()
    inv_dir = os.path.join(inv_root, name.lower().replace(' ', '_'))
    os.makedirs(inv_dir, exist_ok=True)

    seed = Entity(name, "unknown", {"source": "user_created"})
    graph = InvestigationGraph(name, seed)
    graph.save(inv_dir)

    state.GRAPH = graph
    state.INV_PATH = inv_dir
    _rebuild_board()
    return True, None, os.path.abspath(os.path.join(inv_dir, 'board_3d.html'))


def create_empty_investigation():
    """Create a blank investigation if none is loaded."""
    if state.GRAPH:
        return
    inv_root = state.get_investigations_root()
    os.makedirs(inv_root, exist_ok=True)
    state.INV_PATH = os.path.join(inv_root, '_new')
    os.makedirs(state.INV_PATH, exist_ok=True)
    seed = Entity("New Investigation", "concept", {"source": "app_start"})
    state.GRAPH = InvestigationGraph("New Investigation", seed)
    _rebuild_board()
    state.GRAPH.save(state.INV_PATH)


def reset_to_home():
    """Reset to home — clear current investigation."""
    state.GRAPH = None
    state.INV_PATH = None
    create_empty_investigation()


def list_reports():
    """List all reports for the current investigation."""
    import re
    if not state.GRAPH or not state.INV_PATH:
        return []
    reports_dir = os.path.join(state.INV_PATH, 'reports')
    if not os.path.isdir(reports_dir):
        return []
    results = []
    for fname in os.listdir(reports_dir):
        if not fname.endswith('.md'):
            continue
        fpath = os.path.join(reports_dir, fname)
        entity_name = fname[:-3]
        entity_id = entity_name.lower().strip().replace(' ', '_')
        current_conns = len(state.GRAPH.get_connections_for(entity_id)) if entity_id in state.GRAPH.entities else 0
        try:
            with open(fpath) as f:
                first_lines = f.read(500)
            match = re.search(r'Connections.*?(\d+)', first_lines)
            report_conns = int(match.group(1)) if match else current_conns
        except:
            report_conns = current_conns
        results.append({
            'id': entity_id, 'name': entity_name, 'path': os.path.abspath(fpath),
            'conn_count': report_conns, 'current_conns': current_conns,
            'stale': current_conns > report_conns, 'modified': os.path.getmtime(fpath),
        })
    return results


# ── Helpers ──

def _rebuild_board():
    """Rebuild the board HTML for the current investigation."""
    if state.GRAPH and state.INV_PATH:
        from build_board import build_board
        build_board(state.GRAPH, os.path.join(state.INV_PATH, 'board_3d.html'),
                    state.GRAPH.name, mode='server')


def _rebuild_board_for(graph, inv_dir, title):
    """Rebuild board for a specific graph/path."""
    from build_board import build_board
    build_board(graph, os.path.join(inv_dir, 'board_3d.html'),
                f'Investigation: {title}', mode='server')


def _format_feed_results(feed_results):
    """Format raw feed results dict for the UI."""
    feed_summary = {}
    for feed_name, items in (feed_results or {}).items():
        feed_summary[feed_name] = []
        for item in (items if isinstance(items, list) else [items] if items else [])[:10]:
            if isinstance(item, dict):
                feed_summary[feed_name].append({
                    'title': str(item.get('title', item.get('name', item.get('event',
                             item.get('headline', item.get('cve', str(item)[:80]))))))[:200],
                    'source': item.get('source', feed_name),
                    'url': item.get('url', item.get('archive_url', '')),
                    'date': item.get('date', item.get('date_added', item.get('effective', ''))),
                })
    return feed_summary
