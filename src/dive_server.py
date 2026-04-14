#!/usr/bin/env python3
"""
DeepDive Dive Server — WebSocket + HTTP server for live board expansion.
Runs alongside the board. When user clicks "Dive Deeper", this server:
1. Searches (DDG/SearXNG/local files)
2. Sends results to the model (Ollama/OpenAI/etc)
3. Extracts entities, updates graph
4. Rebuilds board, tells browser to reload
"""

import asyncio
import json
import os
import sys
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'core'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'cli'))

from graph import InvestigationGraph, Entity, Connection
from extractors import extract_entities
from auth import DeepDiveBridge
from interview import InvestigationConfig, get_focus_categories, get_depth_levels
from node_actions import prune_node, pin_node, add_note, get_pinned
from views.timeline import build_timeline
from views.report import build_report
from views.money_flow import build_money_flow
from views.settings import build_settings_page, load_settings, save_settings
from plugins import PluginManager, create_plugin_template
from utils import extract_subject

# Global plugin manager
PLUGIN_MGR = PluginManager()
PLUGIN_MGR.load_all()

# Global bridge
BRIDGE = DeepDiveBridge()


def pick_folder_dialog():
    """Open a native OS folder picker dialog. Returns path or empty string."""
    try:
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk()
        root.withdraw()
        root.attributes('-topmost', True)
        folder = filedialog.askdirectory(title="Select Document Folder")
        root.destroy()
        return folder or ""
    except Exception as e:
        print(f"[DiveServer] Folder picker error: {e}")
        return ""


# Globals
GRAPH = None
INV_PATH = None
# PROVIDER removed — using BRIDGE (Agent SDK)
ENGINES = []


DATASET_PATH = None  # Set when user scans a dataset


def do_expand(entity_id, entity_name, search_mode="web", enabled_feeds=None):
    """Expand an entity. search_mode: web, local, both. enabled_feeds: list of OSINT feed names."""
    global GRAPH, INV_PATH, ENGINES, DATASET_PATH

    if not GRAPH:
        return False, 0, "No investigation or model loaded"

    entity = GRAPH.entities.get(entity_id)
    if not entity:
        return False, 0, f"Entity {entity_id} not found"

    # Build existing context
    existing_conns = GRAPH.get_connections_for(entity_id)
    context_parts = []
    for conn in existing_conns:
        other_id = conn.target_id if conn.source_id == entity_id else conn.source_id
        other = GRAPH.entities.get(other_id)
        if other:
            context_parts.append(f"{other.name} ({conn.relationship})")
    known = "Already known: " + ", ".join(context_parts) if context_parts else ""

    # Step 1: Search based on mode
    search_text = ""

    # Local search
    if search_mode in ("local", "both") and DATASET_PATH:
        from search.local_files import LocalFileSearch
        local = LocalFileSearch(DATASET_PATH)
        if local.index():
            results = local.search(entity_name, max_results=15)
            for r in results:
                search_text += r.get('body', '') + "\n"
            if search_text:
                search_text = f"LOCAL DOCUMENTS ({len(results)} matches):\n" + search_text

    # Web search (via ENGINES or Claude's built-in)
    if search_mode in ("web", "both") and ENGINES:
        for engine in ENGINES:
            try:
                results, text = engine.deep_search(entity_name)
                if text:
                    search_text += text[:4000] + "\n"
            except Exception as e:
                print(f"[DiveServer] Search error ({engine.name}): {e}")

    # Step 2: Model analysis
    full_context = ""
    if search_text:
        full_context += "SEARCH RESULTS:\n" + search_text[:8000] + "\n\n"
    if known:
        full_context += known

    try:
        response, feed_results = BRIDGE.research(entity_name, entity.type, full_context,
                                                  enabled_feeds=enabled_feeds)
    except Exception as e:
        return False, 0, None, None, f"Model error: {e}"

    if not response or response.startswith("Error"):
        return False, 0, None, None, f"Model returned: {response}"

    # Step 3: Extract
    extracted = extract_entities(response)

    # Step 4: Add to graph (skip self-references)
    added = 0
    added_entities = []
    for name, etype, rel, conf in extracted:
        new_entity = Entity(name, etype)
        if new_entity.id == entity_id:
            continue
        new_entity.depth = entity.depth + 1
        new_entity.sources.append(f"Expanded from {entity.name}")
        is_new = GRAPH.add_entity(new_entity)
        if is_new:
            added += 1
            added_entities.append({'name': name, 'type': etype, 'relationship': rel})
        GRAPH.add_connection(Connection(entity_id, new_entity.id, rel, conf))

    GRAPH.mark_investigated(entity_id)
    GRAPH.save(INV_PATH)

    # Step 5: Rebuild board
    from build_board import build_board
    board_path = os.path.join(INV_PATH, 'board_3d.html')
    build_board(GRAPH, board_path, GRAPH.name, mode='server')

    # Format feed results for the UI
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

    print(f"[DiveServer] Expanded {entity_name}: +{added} entities, {len(extracted)} connections, {len(feed_results or {})} feeds")
    return True, added, added_entities, feed_summary, None


def do_scan_dataset(folder_path, status_callback=None):
    """Scan a local document folder, extract entities related to the investigation."""
    global GRAPH, INV_PATH, DATASET_PATH
    DATASET_PATH = folder_path  # Save for future local-mode expansions

    if not GRAPH:
        return False, 0, 0, "No investigation or model loaded"

    if not os.path.isdir(folder_path):
        return False, 0, 0, f"Folder not found: {folder_path}"

    # Step 1: Index files
    from search.local_files import LocalFileSearch
    local = LocalFileSearch(folder_path)
    if not local.index():
        return False, 0, 0, f"Could not index {folder_path}"

    files_indexed = len(local.file_cache)
    if status_callback:
        status_callback(f"Indexed {files_indexed} files. Searching...")

    # Step 2: Search for the investigation subject + all existing entities
    search_queries = [GRAPH.name]
    # Add top entities as search terms
    by_conns = sorted(GRAPH.entities.items(), key=lambda x: -len(GRAPH.get_connections_for(x[0])))
    for eid, entity in by_conns[:10]:
        search_queries.append(entity.name)

    all_text_parts = []
    total_hits = 0
    for query in search_queries:
        results = local.search(query, max_results=10)
        total_hits += len(results)
        for r in results:
            all_text_parts.append(r.get('body', ''))
        if status_callback and len(all_text_parts) % 20 == 0:
            status_callback(f"Searching... {total_hits} hits so far")

    if not all_text_parts:
        return True, files_indexed, 0, "No relevant content found in dataset"

    combined_text = "\n".join(all_text_parts)[:12000]

    if status_callback:
        status_callback(f"Found {total_hits} relevant passages. Claude is analyzing...")

    # Step 3: Send to Claude for entity extraction
    prompt_context = f"DOCUMENT CORPUS ANALYSIS for investigation: {GRAPH.name}\n\n"
    prompt_context += f"Extracted text from {total_hits} relevant passages in {files_indexed} files:\n\n"
    prompt_context += combined_text

    try:
        response, _ = BRIDGE.research(GRAPH.name, "investigation", prompt_context)
    except Exception as e:
        return False, files_indexed, 0, f"Model error: {e}"

    if not response or response.startswith("Error"):
        return False, files_indexed, 0, f"Model returned: {response}"

    # Step 4: Extract entities and add to graph
    extracted = extract_entities(response)
    added = 0
    seed_id = list(GRAPH.entities.keys())[0]  # connect to root

    for name, etype, rel, conf in extracted:
        new_entity = Entity(name, etype, {"source": f"dataset:{folder_path}"})
        if new_entity.id == seed_id:
            continue
        # Check for cross-links
        if new_entity.id in GRAPH.entities:
            GRAPH.findings.append(f"CROSS-LINK (dataset): {name} found in documents AND already in graph")
        new_entity.depth = 1
        is_new = GRAPH.add_entity(new_entity)
        if is_new:
            added += 1
        GRAPH.add_connection(Connection(seed_id, new_entity.id, rel, conf))

    # Step 5: Save and rebuild
    GRAPH.save(INV_PATH)
    from build_board import build_board
    board_path = os.path.join(INV_PATH, 'board_3d.html')
    build_board(GRAPH, board_path, GRAPH.name, mode='server')

    print(f"[DiveServer] Dataset scan: {files_indexed} files, {total_hits} hits, +{added} entities")
    return True, files_indexed, added, None


def do_generate_report(entity_id, entity_name):
    """Generate a detailed markdown report for an entity — all connections explained."""
    global GRAPH, INV_PATH

    if not GRAPH:
        return False, None, "No investigation loaded"

    entity = GRAPH.entities.get(entity_id)
    if not entity:
        return False, None, f"Entity {entity_id} not found"

    # Gather all connections
    conns = GRAPH.get_connections_for(entity_id)
    conn_details = []
    for conn in conns:
        other_id = conn.target_id if conn.source_id == entity_id else conn.source_id
        other = GRAPH.entities.get(other_id)
        if other:
            conn_details.append({
                'name': other.name,
                'type': other.type,
                'relationship': conn.relationship,
                'confidence': conn.confidence,
                'metadata': other.metadata,
                'direction': 'outgoing' if conn.source_id == entity_id else 'incoming',
            })

    # Build prompt for Claude to explain the connections
    conn_text = "\n".join(
        f"- {c['name']} ({c['type']}) — {c['relationship']} (confidence: {c['confidence']}, {c['direction']})"
        + (f" | Details: {c['metadata']}" if c['metadata'] else "")
        for c in conn_details
    )

    prompt = f"""Generate a detailed intelligence report for the entity "{entity_name}" based on the following connection data from an investigation graph.

Entity: {entity_name}
Type: {entity.type}
Metadata: {entity.metadata}
Investigation: {GRAPH.name}

CONNECTIONS ({len(conn_details)} total):
{conn_text}

FINDINGS related to this entity:
{chr(10).join(f for f in GRAPH.findings if entity_name.lower() in f.lower())}

Write a structured markdown report that:
1. Summarizes who/what this entity is
2. Groups connections by type (people, companies, money, locations, events)
3. Explains WHY each connection matters — what's the significance
4. Identifies the most suspicious or notable patterns
5. Lists gaps — what connections should exist but don't
6. Recommends what to investigate next

Use [[wikilinks]] for entity names so the report works in Obsidian.
Format as clean markdown with headers, bullet points, and bold for key facts."""

    try:
        response, _ = BRIDGE.research(entity_name, entity.type, prompt)
    except Exception as e:
        return False, None, f"Model error: {e}"

    if not response or response.startswith("Error"):
        # Fallback: generate report without AI
        response = f"# {entity_name}\n\n"
        response += f"**Type:** {entity.type}\n"
        if entity.metadata:
            response += f"**Details:** {entity.metadata}\n"
        response += f"\n## Connections ({len(conn_details)})\n\n"
        for c in sorted(conn_details, key=lambda x: -x['confidence']):
            response += f"- **[[{c['name']}]]** ({c['type']}) — {c['relationship']} ({int(c['confidence']*100)}%)\n"

    # Save report
    reports_dir = os.path.join(INV_PATH, 'reports')
    os.makedirs(reports_dir, exist_ok=True)
    safe_name = entity_name.replace('/', '_').replace('\\', '_').replace(':', '_')[:80]
    report_path = os.path.join(reports_dir, f"{safe_name}.md")

    with open(report_path, 'w') as f:
        f.write(response)

    print(f"[DiveServer] Report generated: {report_path}")
    return True, os.path.abspath(report_path), None


def do_research_gaps(max_gaps=5, status_callback=None):
    """Actively research the top suspicious gaps — search for evidence linking the disconnected entities."""
    global GRAPH, INV_PATH, DATASET_PATH

    if not GRAPH:
        return False, 0, 0, "No investigation or model loaded"

    gaps = GRAPH.detect_gaps()
    if not gaps:
        return True, 0, 0, "No gaps to research"

    # Take the top N most suspicious gaps
    top_gaps = [g for g in gaps if not g.get('researched', False)][:max_gaps]
    if not top_gaps:
        return True, 0, 0, "All gaps already researched"

    connections_found = 0
    gaps_researched = 0

    for i, gap in enumerate(top_gaps):
        a_name = gap['a_name']
        c_name = gap['c_name']
        b_name = gap['b_name']

        if status_callback:
            status_callback(f"Gap {i+1}/{len(top_gaps)}: searching {a_name} ↔ {c_name}...")

        print(f"[DiveServer] Researching gap: {a_name} ↔ {c_name} (via {b_name}, score: {gap['score']})")

        # Build a targeted prompt
        context = f"""INVESTIGATING A GAP in the "{GRAPH.name}" investigation.

{a_name} and {c_name} both connect to {b_name} but have NO direct connection to each other.
This is suspicious because: {gap.get('details', 'unknown')}
Suspicion score: {gap['score']}/10

Search for ANY connection between {a_name} and {c_name}:
- Did they ever meet, work together, do business?
- Any financial connection (payments, investments, shared funds)?
- Shared locations, events, organizations?
- Any legal/lawsuit connections?
- Even indirect connections through other entities

If you find a connection, output it as:
ENTITY_NAME | ENTITY_TYPE | RELATIONSHIP | CONFIDENCE

If you find NO connection, say "NO CONNECTION FOUND" and explain why this gap might exist (deliberately hidden? different domains? insufficient data?)"""

        try:
            response, _ = BRIDGE.research(
                f"{a_name} AND {c_name}",
                "gap_research",
                context
            )
        except Exception as e:
            print(f"[DiveServer] Gap research error: {e}")
            continue

        if not response or response.startswith("Error"):
            continue

        gaps_researched += 1

        # Check if connection was found
        if "NO CONNECTION FOUND" not in response.upper():
            # Extract any entities/connections from the response
            extracted = extract_entities(response)
            for name, etype, rel, conf in extracted:
                new_entity = Entity(name, etype, {"source": "gap_research"})
                if new_entity.id == gap['entity_a'] or new_entity.id == gap['entity_c']:
                    continue
                GRAPH.add_entity(new_entity)
                # Connect to both gap endpoints if relevant
                GRAPH.add_connection(Connection(gap['entity_a'], new_entity.id, rel, conf))
                GRAPH.add_connection(Connection(gap['entity_c'], new_entity.id, rel, conf))

            # Also try direct connection between A and C
            # Look for relationship keywords in the response
            rel_found = "related_to"
            for keyword, rel_type in [
                ("business", "partner_of"), ("met", "met_with"), ("paid", "paid_by"),
                ("invested", "invested_in"), ("worked", "works_for"), ("board", "board_member"),
                ("lawsuit", "sued_by"), ("married", "married_to"), ("founded", "co_founded"),
                ("associate", "associate_of"),
            ]:
                if keyword in response.lower():
                    rel_found = rel_type
                    break

            GRAPH.add_connection(Connection(gap['entity_a'], gap['entity_c'], rel_found, 0.5))
            connections_found += 1
            GRAPH.findings.append(
                f"GAP FILLED: {a_name} ↔ {c_name} — connection found via gap research ({rel_found})"
            )
        else:
            # No connection — that's also a finding
            GRAPH.findings.append(
                f"GAP CONFIRMED: {a_name} and {c_name} have no apparent connection despite both linking to {b_name} — possible deliberate separation"
            )

        # Mark this gap as researched
        gap['researched'] = True

    # Save and rebuild
    GRAPH.save(INV_PATH)
    from build_board import build_board
    board_path = os.path.join(INV_PATH, 'board_3d.html')
    build_board(GRAPH, board_path, GRAPH.name, mode='server')

    print(f"[DiveServer] Gap research: {gaps_researched} gaps investigated, {connections_found} connections found")
    return True, gaps_researched, connections_found, None


def list_reports():
    """List all reports for the current investigation with stale detection."""
    global GRAPH, INV_PATH
    if not GRAPH or not INV_PATH:
        return []
    reports_dir = os.path.join(INV_PATH, 'reports')
    if not os.path.isdir(reports_dir):
        return []
    results = []
    for fname in os.listdir(reports_dir):
        if not fname.endswith('.md'):
            continue
        fpath = os.path.join(reports_dir, fname)
        # Match to entity by filename
        entity_name = fname[:-3]  # strip .md
        entity_id = entity_name.lower().strip().replace(' ', '_')
        # Count connections at time of report (store in first line or use file mod time)
        current_conns = len(GRAPH.get_connections_for(entity_id)) if entity_id in GRAPH.entities else 0
        # Read report to check stored connection count
        try:
            with open(fpath) as f:
                first_lines = f.read(500)
            # Try to find connection count in report
            import re
            match = re.search(r'Connections.*?(\d+)', first_lines)
            report_conns = int(match.group(1)) if match else current_conns
        except:
            report_conns = current_conns

        results.append({
            'id': entity_id,
            'name': entity_name,
            'path': os.path.abspath(fpath),
            'conn_count': report_conns,
            'current_conns': current_conns,
            'stale': current_conns > report_conns,
            'modified': os.path.getmtime(fpath),
        })
    return results


def get_investigations_root():
    """Get the investigations directory."""
    return os.path.join(os.path.dirname(__file__), '..', 'investigations')


def list_investigations():
    """List all saved investigations."""
    global INV_PATH
    inv_root = get_investigations_root()
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
                'active': os.path.abspath(full) == os.path.abspath(INV_PATH) if INV_PATH else False,
            })
        except:
            results.append({'dir': full, 'name': d, 'entities': 0, 'connections': 0, 'active': False})
    return results


def switch_investigation(inv_dir):
    """Switch to a different investigation."""
    global GRAPH, INV_PATH
    if not os.path.isdir(inv_dir):
        return False, f"Not found: {inv_dir}"
    json_files = [f for f in os.listdir(inv_dir) if f.endswith('.json')]
    if not json_files:
        return False, "No investigation data in that folder"
    try:
        GRAPH = InvestigationGraph.load(os.path.join(inv_dir, json_files[0]))
        INV_PATH = inv_dir
        # Rebuild board for this investigation
        from build_board import build_board
        board_path = os.path.join(INV_PATH, 'board_3d.html')
        build_board(GRAPH, board_path, GRAPH.name, mode='server')
        board_path_abs = os.path.abspath(board_path)
        print(f"[DiveServer] Switched to: {GRAPH.name} ({len(GRAPH.entities)} entities)")
        return True, None, board_path_abs
    except Exception as e:
        return False, str(e), None


def create_new_investigation(name):
    """Create a new empty investigation and switch to it."""
    global GRAPH, INV_PATH
    if not name:
        return False, "Name required"
    inv_root = get_investigations_root()
    inv_dir = os.path.join(inv_root, name.lower().replace(' ', '_'))
    os.makedirs(inv_dir, exist_ok=True)

    seed = Entity(name, "unknown", {"source": "user_created"})
    graph = InvestigationGraph(name, seed)
    graph.save(inv_dir)

    GRAPH = graph
    INV_PATH = inv_dir

    from build_board import build_board
    board_path = os.path.join(INV_PATH, 'board_3d.html')
    build_board(GRAPH, board_path, 'Investigation: ' + name, mode='server')

    board_path_abs = os.path.abspath(board_path)
    print(f"[DiveServer] New investigation: {name} -> {board_path_abs}")
    return True, None, board_path_abs


def do_investigate_with_config(config, expand_current=False):
    """Run investigation using interview config. expand_current=True adds to existing graph."""
    global GRAPH, INV_PATH

    subject = config.subject
    if not subject:
        return False, 0, "No subject provided"

    # Extract clean title from the full prompt
    title = extract_subject(subject)

    if expand_current and GRAPH and INV_PATH:
        graph = GRAPH
        inv_dir = INV_PATH
        seed_id = title.lower().strip().replace(" ", "_")
        if seed_id in graph.entities:
            seed = graph.entities[seed_id]
        else:
            seed = Entity(title, "unknown", {"source": "node_investigation"})
            graph.add_entity(seed)
        print(f"[Investigation] Expanding current graph with: {title}")
    else:
        inv_root = get_investigations_root()
        os.makedirs(inv_root, exist_ok=True)
        inv_dir = os.path.join(inv_root, title.lower().replace(' ', '_')[:50])
        os.makedirs(inv_dir, exist_ok=True)
        seed = Entity(title, "unknown", {"source": "interview", "config": json.dumps(config.to_dict())})
        graph = InvestigationGraph(title, seed)

    # Build focused prompt from config
    search_prompt = config.build_search_prompt()
    depth_config = config.get_depth_config()

    # Pass 1: Initial research with focused prompt
    enabled_feeds = config.enabled_feeds if config.enabled_feeds else None
    print(f"[Investigation] Pass 1: {subject} (feeds: {enabled_feeds})")
    from auth.bridge import INVESTIGATOR_PROMPT
    response, _ = BRIDGE.research(subject, "unknown", search_prompt,
                                  enabled_feeds=enabled_feeds)

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

    # Additional passes based on depth
    max_passes = depth_config["passes"]
    expand_per = depth_config["expand_per_pass"]

    if max_passes == 0:
        max_passes = 20  # exhaustive but not infinite

    pass_num = 2
    while pass_num <= max_passes and expand_per > 0:
        # Get top uninvestigated nodes by connection count
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

            resp, _ = BRIDGE.research(entity.name, entity.type, search_prompt,
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

        print(f"[Investigation] Pass {pass_num}: +{new_this_pass} entities")

        if new_this_pass == 0:
            break  # Nothing new found, stop

        pass_num += 1

    # Finalize
    graph.detect_gaps()
    graph.save(inv_dir)

    from build_board import build_board
    build_board(graph, os.path.join(inv_dir, 'board_3d.html'), f'Investigation: {subject}', mode='server')

    GRAPH = graph
    INV_PATH = inv_dir

    print(f"[Investigation] Complete: {subject} — {total_added} entities, {len(graph.connections)} connections, {pass_num-1} passes")
    return True, total_added, None


def do_investigate(subject):
    """Start a full investigation on a subject — create graph, research, build board."""
    global GRAPH, INV_PATH

    # Extract clean title from the full prompt
    title = extract_subject(subject)

    inv_root = get_investigations_root()
    os.makedirs(inv_root, exist_ok=True)
    inv_dir = os.path.join(inv_root, title.lower().replace(' ', '_')[:50])
    os.makedirs(inv_dir, exist_ok=True)

    seed = Entity(title, "unknown", {"source": "user_input"})
    graph = InvestigationGraph(title, seed)

    # Have Claude research the subject
    print(f"[DiveServer] Researching: {subject}")
    try:
        response, _ = BRIDGE.research(subject, "unknown", "")
    except Exception as e:
        return False, 0, f"Research error: {e}"

    if not response or response.startswith("Error"):
        return False, 0, f"Claude returned: {response}"

    # Extract entities
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

    # Build board
    from build_board import build_board
    build_board(graph, os.path.join(inv_dir, 'board_3d.html'), f'Investigation: {subject}', mode='server')

    # Switch to this investigation
    GRAPH = graph
    INV_PATH = inv_dir

    print(f"[DiveServer] Investigation: {subject} — {added} entities, {len(graph.connections)} connections")
    return True, added, None


def _reset_to_home():
    """Reset to home — clear current investigation, create empty one."""
    global GRAPH, INV_PATH
    GRAPH = None
    INV_PATH = None
    _create_empty_investigation()


def _create_empty_investigation():
    """Create a blank investigation if none is loaded."""
    global GRAPH, INV_PATH
    if GRAPH:
        return
    inv_root = get_investigations_root()
    os.makedirs(inv_root, exist_ok=True)
    INV_PATH = os.path.join(inv_root, '_new')
    os.makedirs(INV_PATH, exist_ok=True)
    seed = Entity("New Investigation", "concept", {"source": "app_start"})
    GRAPH = InvestigationGraph("New Investigation", seed)
    from build_board import build_board
    build_board(GRAPH, os.path.join(INV_PATH, 'board_3d.html'), 'DeepDive', mode='server')
    GRAPH.save(INV_PATH)


# --- HTTP Server (fallback for when WebSocket isn't connected) ---

class ExpandHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        """Handle GET requests — serves the board page for browser navigation."""
        if self.path == '/settings':
            self.send_response(200)
            self.send_header('Content-Type', 'text/html')
            self.end_headers()
            self.wfile.write(build_settings_page().encode())
            return

        elif self.path == '/report-view':
            if GRAPH and INV_PATH:
                rpt_path = os.path.join(INV_PATH, 'report_full.html')
                build_report(GRAPH, rpt_path, f'Investigation Report: {GRAPH.name}')
                self.send_response(200)
                self.send_header('Content-Type', 'text/html')
                self.end_headers()
                with open(rpt_path, 'rb') as f:
                    self.wfile.write(f.read())
                return
            self.send_response(404)
            self.end_headers()
            return

            return

        elif self.path == '/timeline':
            if GRAPH and INV_PATH:
                tl_path = os.path.join(INV_PATH, 'timeline.html')
                build_timeline(GRAPH, tl_path, f'Timeline: {GRAPH.name}')
                self.send_response(200)
                self.send_header('Content-Type', 'text/html')
                self.end_headers()
                with open(tl_path, 'rb') as f:
                    self.wfile.write(f.read())
                return
            self.send_response(404)
            self.end_headers()
            return

        elif self.path == '/money-flow':
            if GRAPH and INV_PATH:
                mf_path = os.path.join(INV_PATH, 'money_flow.html')
                build_money_flow(GRAPH, mf_path, f'Money Flow: {GRAPH.name}')
                self.send_response(200)
                self.send_header('Content-Type', 'text/html')
                self.end_headers()
                with open(mf_path, 'rb') as f:
                    self.wfile.write(f.read())
                return
            self.send_response(404)
            self.end_headers()
            return

        elif self.path == '/board' or self.path == '/':
            # Serve the frontend index.html
            if not GRAPH:
                _create_empty_investigation()
            frontend_dir = os.path.join(os.path.dirname(__file__), '..', 'frontend')
            index_path = os.path.join(frontend_dir, 'index.html')
            if os.path.exists(index_path):
                self.send_response(200)
                self.send_header('Content-Type', 'text/html')
                self.end_headers()
                with open(index_path, 'rb') as f:
                    self.wfile.write(f.read())
                return
            # Fallback to old generated board if frontend doesn't exist
            if INV_PATH:
                board_file = os.path.join(INV_PATH, 'board_3d.html')
                if os.path.exists(board_file):
                    self.send_response(200)
                    self.send_header('Content-Type', 'text/html')
                    self.end_headers()
                    with open(board_file, 'rb') as f:
                        self.wfile.write(f.read())
                    return
            self.send_response(404)
            self.end_headers()
            return

        elif self.path.startswith('/static/'):
            # Serve static frontend files (CSS, JS, assets)
            frontend_dir = os.path.join(os.path.dirname(__file__), '..', 'frontend')
            rel_path = self.path[len('/static/'):]
            file_path = os.path.join(frontend_dir, rel_path)
            # Security: prevent directory traversal
            file_path = os.path.realpath(file_path)
            frontend_real = os.path.realpath(frontend_dir)
            if not file_path.startswith(frontend_real) or not os.path.isfile(file_path):
                self.send_response(404)
                self.end_headers()
                return
            # Content type mapping
            ext = os.path.splitext(file_path)[1].lower()
            content_types = {
                '.css': 'text/css',
                '.js': 'application/javascript',
                '.html': 'text/html',
                '.svg': 'image/svg+xml',
                '.png': 'image/png',
                '.jpg': 'image/jpeg',
                '.ico': 'image/x-icon',
                '.json': 'application/json',
                '.woff2': 'font/woff2',
                '.woff': 'font/woff',
            }
            ct = content_types.get(ext, 'application/octet-stream')
            self.send_response(200)
            self.send_header('Content-Type', ct)
            self.send_header('Cache-Control', 'no-cache')
            self.end_headers()
            with open(file_path, 'rb') as f:
                self.wfile.write(f.read())
            return

        self.send_response(404)
        self.end_headers()

    def do_POST(self):
        length = int(self.headers.get('Content-Length', 0))
        body = json.loads(self.rfile.read(length)) if length > 0 else {}

        if self.path == '/api/board-data':
            # Return all data the frontend needs to render the board
            if not GRAPH:
                _create_empty_investigation()
            from build_board import COLORS
            stats = GRAPH.get_stats()
            nodes = []
            for eid, entity in GRAPH.entities.items():
                color = COLORS.get(entity.type, '#6B7280')
                conns = len(GRAPH.get_connections_for(eid))
                nodes.append({
                    'id': eid, 'label': entity.name, 'type': entity.type,
                    'color': color, 'size': min(2 + conns * 0.4, 10),
                    'depth': entity.depth, 'investigated': entity.investigated,
                    'metadata': entity.metadata, 'connections': conns,
                })
            edges = [{
                'from': c.source_id, 'to': c.target_id,
                'label': c.relationship.replace('_', ' '),
                'confidence': c.confidence,
            } for c in GRAPH.connections]
            self._json_response({
                'nodes': nodes,
                'edges': edges,
                'colors': COLORS,
                'title': f'Investigation: {GRAPH.name}' if GRAPH.name != 'New Investigation' else 'DeepDive',
                'stats': stats,
                'findings': GRAPH.findings or [],
            })
            return

        if self.path == '/expand':
            entity_id = body.get('id', '')
            entity_name = body.get('label', '')
            search_mode = body.get('search_mode', 'web')
            enabled_feeds = body.get('enabled_feeds', None)
            print(f"[HTTP] Expand: {entity_name} (mode: {search_mode}, feeds: {enabled_feeds})")
            success, added, added_entities, feed_data, error = do_expand(entity_id, entity_name, search_mode, enabled_feeds)
            self._json_response({
                'success': success, 'added': added, 'error': error,
                'added_entities': added_entities or [],
                'feed_data': feed_data or {},
            })

        elif self.path == '/scan':
            folder_path = body.get('path', '')
            print(f"[HTTP] Scan dataset: {folder_path}")
            success, files_indexed, entities_added, error = do_scan_dataset(folder_path)
            self._json_response({
                'success': success, 'files_indexed': files_indexed,
                'entities_added': entities_added, 'error': error
            })

        elif self.path == '/report':
            entity_id = body.get('id', '')
            entity_name = body.get('label', '')
            print(f"[HTTP] Report: {entity_name}")
            success, path, error = do_generate_report(entity_id, entity_name)
            self._json_response({'success': success, 'path': path, 'error': error})

        elif self.path == '/report/get':
            entity_id = body.get('id', '')
            if GRAPH and INV_PATH:
                reports_dir = os.path.join(INV_PATH, 'reports')
                # Try exact match first, then case-insensitive
                report_path = None
                if os.path.isdir(reports_dir):
                    for fname in os.listdir(reports_dir):
                        if fname.endswith('.md'):
                            fid = fname[:-3].lower().replace(' ', '_')
                            if fid == entity_id or fname[:-3].lower() == entity_id:
                                report_path = os.path.join(reports_dir, fname)
                                break
                if report_path and os.path.exists(report_path):
                    with open(report_path, 'r') as f:
                        content = f.read()
                    self._json_response({'exists': True, 'content': content, 'path': report_path})
                else:
                    self._json_response({'exists': False})
            else:
                self._json_response({'exists': False})

        elif self.path == '/list_gaps':
            gaps = GRAPH.detect_gaps() if GRAPH else []
            self._json_response({'gaps': gaps[:20]})

        elif self.path == '/research_gaps':
            max_gaps = body.get('max_gaps', 5)
            print(f"[HTTP] Research gaps (top {max_gaps})")
            success, researched, found, error = do_research_gaps(max_gaps)
            self._json_response({
                'success': success, 'gaps_researched': researched,
                'connections_found': found, 'error': error
            })

        elif self.path == '/list_reports':
            reports = list_reports()
            self._json_response({'reports': reports})

        elif self.path == '/get_board' or self.path == '/board':
            # Serve the current investigation's board HTML
            if INV_PATH:
                board_file = os.path.join(INV_PATH, 'board_3d.html')
                if os.path.exists(board_file):
                    self.send_response(200)
                    self.send_header('Content-Type', 'text/html')
                    self.send_header('Access-Control-Allow-Origin', '*')
                    self.end_headers()
                    with open(board_file, 'rb') as f:
                        self.wfile.write(f.read())
                    return
            # No investigation loaded — create empty one and serve its board
            _create_empty_investigation()
            board_file = os.path.join(INV_PATH, 'board_3d.html')
            self.send_response(200)
            self.send_header('Content-Type', 'text/html')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            with open(board_file, 'rb') as f:
                self.wfile.write(f.read())
            return
            # Dead code below — kept for reference
            welcome = b'''<!DOCTYPE html><html><head><style>
*{margin:0;padding:0;box-sizing:border-box}
body{background:#050810;color:#c0c8e0;font-family:system-ui;display:flex;align-items:center;justify-content:center;height:100vh}
.wrap{text-align:center;width:500px}
h1{color:#00ccaa;font-size:28px;margin-bottom:8px}
p{color:#8a8f98;margin-bottom:24px;font-size:14px}
.row{display:flex;gap:8px;margin-bottom:16px}
input{flex:1;padding:12px 16px;background:#111827;border:1px solid rgba(255,255,255,0.1);border-radius:10px;color:#ededef;font-size:14px;font-family:system-ui}
input:focus{outline:none;border-color:#00ccaa}
button{padding:12px 20px;background:#00ccaa;color:#050810;border:none;border-radius:10px;font-size:14px;font-weight:600;cursor:pointer;font-family:system-ui}
button:hover{background:#00e6bf}
.inv{background:#111827;border:1px solid rgba(255,255,255,0.06);border-radius:10px;padding:10px 14px;margin:4px 0;cursor:pointer;text-align:left;display:flex;justify-content:space-between;transition:all .15s}
.inv:hover{border-color:#00ccaa}
.inv .name{color:#ededef;font-size:13px;font-weight:500}
.inv .meta{color:#4a5060;font-size:11px}
h2{color:#00ccaa;font-size:13px;margin:20px 0 8px;text-align:left}
</style></head><body>
<div class="wrap">
<h1>DeepDive</h1>
<p>AI-Powered Research & Discovery</p>
<div class="row">
<input id="subj" placeholder="Enter subject to investigate..." onkeydown="if(event.key==='Enter')go()">
<button onclick="go()">Start</button>
</div>
<div id="list"></div>
</div>
<script>
async function go(){
  const name=document.getElementById('subj').value.trim();
  if(!name)return;
  document.getElementById('subj').disabled=true;
  const r=await fetch('http://localhost:8766/new_investigation',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name:name})});
  const d=await r.json();
  if(d.success){const b=await fetch('http://localhost:8766/get_board',{method:'POST'});const h=await b.text();document.open();document.write(h);document.close()}
}
async function load(dir){
  const r=await fetch('http://localhost:8766/switch',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({dir:dir})});
  const d=await r.json();
  if(d.success){const b=await fetch('http://localhost:8766/get_board',{method:'POST'});const h=await b.text();document.open();document.write(h);document.close()}
}
fetch('http://localhost:8766/list_investigations',{method:'POST'}).then(r=>r.json()).then(d=>{
  const invs=d.investigations||[];
  if(!invs.length)return;
  const el=document.getElementById('list');
  el.innerHTML='<h2>Previous Investigations</h2>';
  invs.forEach(i=>{
    el.innerHTML+='<div class="inv" onclick="load(\\''+i.dir+'\\')"><div><div class="name">'+i.name+'</div><div class="meta">'+i.entities+' entities, '+i.connections+' connections</div></div></div>';
  });
});
</script></body></html>'''
            self.wfile.write(welcome)
            return

        elif self.path == '/interview/options':
            self._json_response({
                'focus_categories': {k: {'label': v['label'], 'options': v['options']} for k, v in get_focus_categories().items()},
                'depth_levels': {k: {'label': v['label'], 'description': v['description']} for k, v in get_depth_levels().items()},
            })

        elif self.path == '/interview/start':
            config = InvestigationConfig.from_dict(body)
            mode = body.get('mode', 'new')
            print(f"[Interview] Subject: {config.subject}, Focus: {len(config.focus_areas)} areas, Depth: {config.depth}, Mode: {mode}")
            success, entities, error = do_investigate_with_config(config, expand_current=(mode == 'expand'))
            self._json_response({'success': success, 'entities': entities, 'error': error})

        elif self.path == '/investigate':
            subject = body.get('subject', '')
            if not subject:
                self._json_response({'success': False, 'error': 'No subject provided'})
            else:
                print(f"[HTTP] New investigation: {subject}")
                success, entities, error = do_investigate(subject)
                self._json_response({'success': success, 'entities': entities, 'error': error})

        elif self.path == '/home':
            # Reset to no investigation, serve welcome page
            _reset_to_home()
            board_file = os.path.join(INV_PATH, 'board_3d.html')
            self.send_response(200)
            self.send_header('Content-Type', 'text/html')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            with open(board_file, 'rb') as f:
                self.wfile.write(f.read())
            return

        elif self.path == '/node/prune':
            eid = body.get('id', '')
            if GRAPH:
                success, error = prune_node(GRAPH, eid)
                if success:
                    GRAPH.save(INV_PATH)
                    from build_board import build_board
                    build_board(GRAPH, os.path.join(INV_PATH, 'board_3d.html'), GRAPH.name, mode='server')
                self._json_response({'success': success, 'error': error})
            else:
                self._json_response({'success': False, 'error': 'No investigation loaded'})

        elif self.path == '/node/pin':
            eid = body.get('id', '')
            if GRAPH:
                success, pinned = pin_node(GRAPH, eid)
                GRAPH.save(INV_PATH)
                self._json_response({'success': success, 'pinned': pinned})
            else:
                self._json_response({'success': False, 'error': 'No investigation loaded'})

        elif self.path == '/node/note':
            eid = body.get('id', '')
            note = body.get('note', '')
            if GRAPH and note:
                success, count = add_note(GRAPH, eid, note)
                GRAPH.save(INV_PATH)
                self._json_response({'success': success, 'note_count': count})
            else:
                self._json_response({'success': False, 'error': 'No investigation or empty note'})

        elif self.path == '/node/pinned':
            if GRAPH:
                self._json_response({'pinned': get_pinned(GRAPH)})
            else:
                self._json_response({'pinned': []})

        elif self.path == '/view/timeline':
            if GRAPH and INV_PATH:
                tl_path = os.path.join(INV_PATH, 'timeline.html')
                build_timeline(GRAPH, tl_path, f'Timeline: {GRAPH.name}')
                self.send_response(200)
                self.send_header('Content-Type', 'text/html')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                with open(tl_path, 'rb') as f:
                    self.wfile.write(f.read())
                return
            else:
                self._json_response({'error': 'No investigation loaded'})

        elif self.path == '/settings/save':
            success = save_settings(body)
            self._json_response({'success': success})

        elif self.path == '/settings/load':
            self._json_response(load_settings())

        elif self.path == '/plugins/list':
            self._json_response({'plugins': PLUGIN_MGR.list_plugins()})

        elif self.path == '/plugins/toggle':
            name = body.get('name', '')
            result = PLUGIN_MGR.toggle_plugin(name)
            self._json_response({'success': result is not None, 'enabled': result})

        elif self.path == '/plugins/install':
            source = body.get('source', '')
            success = PLUGIN_MGR.install_plugin(source)
            self._json_response({'success': success})

        elif self.path == '/plugins/create':
            name = body.get('name', '')
            if name:
                path = create_plugin_template(name)
                PLUGIN_MGR.discover()
                self._json_response({'success': True, 'path': path})
            else:
                self._json_response({'success': False, 'error': 'Name required'})

        elif self.path == '/export/json':
            if GRAPH:
                export = {
                    'name': GRAPH.name,
                    'entities': {eid: {'name': e.name, 'type': e.type, 'metadata': e.metadata,
                                       'depth': e.depth, 'investigated': e.investigated}
                                 for eid, e in GRAPH.entities.items()},
                    'connections': [{'source': c.source_id, 'target': c.target_id,
                                     'relationship': c.relationship, 'confidence': c.confidence}
                                    for c in GRAPH.connections],
                    'findings': GRAPH.findings,
                    'gaps': GRAPH.gaps[:50] if GRAPH.gaps else [],
                }
                self._json_response(export)
            else:
                self._json_response({'error': 'No investigation loaded'})

        elif self.path == '/export/markdown':
            if GRAPH:
                md = f"# Investigation: {GRAPH.name}\n\n"
                md += f"**Entities:** {len(GRAPH.entities)} | **Connections:** {len(GRAPH.connections)}\n\n"
                by_type = {}
                for eid, e in GRAPH.entities.items():
                    by_type.setdefault(e.type, []).append(e)
                for t, entities in sorted(by_type.items()):
                    md += f"## {t.title()}s ({len(entities)})\n\n"
                    for e in sorted(entities, key=lambda x: -len(GRAPH.get_connections_for(x.id if hasattr(x, 'id') else ''))):
                        eid_val = e.name.lower().replace(' ', '_')
                        conns = len(GRAPH.get_connections_for(eid_val))
                        md += f"- **{e.name}** ({conns} connections)\n"
                    md += "\n"
                if GRAPH.findings:
                    md += "## Key Findings\n\n"
                    for f in GRAPH.findings:
                        md += f"- {f}\n"
                self.send_response(200)
                self.send_header('Content-Type', 'text/markdown')
                self.send_header('Content-Disposition', f'attachment; filename="{GRAPH.name}_export.md"')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(md.encode())
            else:
                self._json_response({'error': 'No investigation loaded'})

        elif self.path == '/usage':
            from auth.bridge import USAGE
            self._json_response(USAGE.get_stats())

        elif self.path == '/kill':
            from auth.bridge import USAGE
            USAGE.kill()
            self._json_response({'success': True, 'message': 'Kill signal sent'})

        elif self.path == '/kill/reset':
            from auth.bridge import USAGE
            USAGE.reset_kill()
            self._json_response({'success': True})

        elif self.path == '/auth/status':
            available = BRIDGE.is_available()
            settings = BRIDGE._get_settings()
            provider = settings.get('provider', 'claude')
            self._json_response({
                'authenticated': available,
                'provider': provider,
                'user': {'method': provider},
            })

        elif self.path == '/pick_folder':
            path = pick_folder_dialog()
            self._json_response({'path': path})

        elif self.path == '/browse_dir':
            target = body.get('path', '/home')
            try:
                if not os.path.isdir(target):
                    target = os.path.dirname(target) or '/home'
                dirs = []
                for name in sorted(os.listdir(target)):
                    full = os.path.join(target, name)
                    if os.path.isdir(full) and not name.startswith('.'):
                        dirs.append({'name': name, 'path': full})
                parent = os.path.dirname(target.rstrip('/')) or '/'
                self._json_response({'success': True, 'path': target, 'parent': parent, 'dirs': dirs})
            except PermissionError:
                self._json_response({'success': False, 'error': 'Permission denied'})
            except Exception as e:
                self._json_response({'success': False, 'error': str(e)})

        elif self.path == '/osint/analyze':
            # Takes raw OSINT feed data and sends it to Claude for entity extraction
            entity = body.get('entity', '')
            feed_data = body.get('data', '')
            feed_source = body.get('source', 'OSINT feed')
            print(f"[HTTP] OSINT analyze: {entity} from {feed_source}")
            try:
                if not GRAPH:
                    self._json_response({'success': False, 'error': 'No investigation loaded'})
                    return
                prompt = f"""Analyze this {feed_source} data related to "{entity}" in the context of investigation "{GRAPH.name}".

FEED DATA:
{feed_data[:8000]}

Extract ALL people, companies, locations, events, and money connections.
Output each as: ENTITY_NAME | ENTITY_TYPE | RELATIONSHIP | CONFIDENCE (high/medium/low)
Be thorough — extract every name, organization, amount, and date mentioned."""

                response, _ = BRIDGE.research(entity, "feed_analysis", prompt)
                if not response or response.startswith("Error"):
                    self._json_response({'success': False, 'error': response or 'Analysis failed'})
                    return

                extracted = extract_entities(response)
                added = 0
                entity_id = entity.lower().replace(' ', '_')
                # Connect to the entity if it exists, otherwise to root
                parent_id = entity_id if entity_id in GRAPH.entities else list(GRAPH.entities.keys())[0]
                for name, etype, rel, conf in extracted:
                    ent = Entity(name, etype, {"source": feed_source})
                    ent.depth = 2
                    if GRAPH.add_entity(ent):
                        added += 1
                    GRAPH.add_connection(Connection(parent_id, ent.id, rel, conf))
                if added:
                    GRAPH.save(INV_PATH)
                    from build_board import build_board
                    build_board(GRAPH, os.path.join(INV_PATH, 'board_3d.html'), GRAPH.name, mode='server')

                self._json_response({
                    'success': True,
                    'message': f'AI extracted {added} entities from {feed_source} data',
                    'added': added,
                    'reload': added > 0,
                })
            except Exception as e:
                print(f"[OSINT Analyze Error] {e}")
                self._json_response({'success': False, 'error': str(e)})

        elif self.path.startswith('/osint/'):
            tool = self.path.split('/osint/')[1]
            entity = body.get('entity', '')
            print(f"[HTTP] OSINT tool: {tool} on {entity}")
            try:
                result = {'success': True, 'message': '', 'results': [], 'reload': False}
                if tool in ('timeline', 'money', 'social', 'wayback'):
                    # AI-powered traces — call Claude, extract entities, add to graph
                    tool_fns = {
                        'timeline': BRIDGE.trace_timeline,
                        'money': BRIDGE.trace_money,
                        'social': BRIDGE.scan_social_media,
                        'wayback': BRIDGE.check_wayback,
                    }
                    tool_labels = {
                        'timeline': 'timeline events',
                        'money': 'money connections',
                        'social': 'social media findings',
                        'wayback': 'archived findings',
                    }
                    raw = tool_fns[tool](entity)
                    from extractors import extract_entities
                    extracted = extract_entities(raw)
                    added = 0
                    added_list = []
                    entity_id = entity.lower().replace(' ', '_')
                    for name, etype, rel, conf in extracted:
                        ent = Entity(name, etype)
                        ent.depth = 2
                        is_new = GRAPH.add_entity(ent)
                        if is_new:
                            added += 1
                        added_list.append({
                            'title': name,
                            'source': f'AI {tool} trace',
                            'date': rel.replace('_', ' '),
                            'extra': {'type': etype, 'confidence': conf, 'new': is_new},
                        })
                        GRAPH.add_connection(Connection(entity_id, ent.id, rel, conf))
                    if added:
                        GRAPH.save(INV_PATH)
                        from build_board import build_board
                        build_board(GRAPH, os.path.join(INV_PATH, 'board_3d.html'), GRAPH.name, mode='server')
                    result['message'] = f'{added} {tool_labels[tool]} ({len(extracted)} total analyzed)'
                    result['reload'] = added > 0
                    result['results'] = added_list
                elif tool in ('feeds', 'patents', 'gov', 'sanctions', 'bluesky',
                             'conflicts', 'who', 'cisa', 'humanitarian',
                             'flights', 'satellites', 'earthquakes', 'weather',
                             'fires', 'launches', 'ships', 'sec', 'stock',
                             'gdelt', 'reddit', 'news', 'ofac'):
                    from search.osint_feeds import OSINTFeeds
                    feeds = OSINTFeeds()
                    if tool == 'feeds':
                        data = feeds.search_all(entity)
                        items = []
                        for source, entries in data.items():
                            for entry in (entries or [])[:5]:
                                items.append({'title': entry.get('title', entry.get('name', '')), 'source': source, 'url': entry.get('url', ''), 'date': entry.get('date', '')})
                        result['results'] = items
                        result['message'] = f'{len(items)} feed results'
                    else:
                        items = feeds.search_targeted(entity, tool)
                        formatted = []
                        for item in (items or []):
                            if isinstance(item, dict):
                                title = item.get('title', item.get('name', item.get('event', item.get('headline', item.get('cve', str(item)[:80])))))
                                formatted.append({
                                    'title': str(title)[:200],
                                    'source': item.get('source', tool.upper()),
                                    'url': item.get('url', item.get('archive_url', '')),
                                    'date': item.get('date', item.get('date_added', item.get('effective', ''))),
                                    'extra': {k: str(v)[:100] for k, v in item.items()
                                              if k not in ('title', 'source', 'url', 'date', 'name') and v},
                                })
                        result['results'] = formatted
                        result['message'] = f'{len(formatted)} {tool} results'
                elif tool == 'darkweb':
                    try:
                        from search.darkweb import search as darkweb_search
                        results = darkweb_search(entity, max_results=10)
                        result['results'] = [{'title': r.get('title', r.get('name', '')), 'source': 'Dark Web', 'url': r.get('url', r.get('link', ''))} for r in (results if isinstance(results, list) else [])]
                        result['message'] = f'{len(result["results"])} dark web results'
                    except Exception as dwe:
                        result['message'] = f'Dark web search unavailable: {dwe}'
                        result['results'] = []
                else:
                    result = {'success': False, 'error': f'Unknown tool: {tool}'}
                self._json_response(result)
            except Exception as e:
                print(f"[OSINT Error] {tool}: {e}")
                self._json_response({'success': False, 'error': str(e)})

        elif self.path == '/list_investigations':
            investigations = list_investigations()
            self._json_response({'investigations': investigations})

        elif self.path == '/switch':
            inv_dir = body.get('dir', '')
            result = switch_investigation(inv_dir)
            success, error = result[0], result[1]
            board_url = result[2] if len(result) > 2 else None
            self._json_response({'success': success, 'error': error, 'board_url': board_url})

        elif self.path == '/new_investigation':
            name = body.get('name', '')
            result = create_new_investigation(name)
            success, error = result[0], result[1]
            board_url = result[2] if len(result) > 2 else None
            self._json_response({'success': success, 'error': error, 'board_url': board_url})

        else:
            self.send_response(404)
            self.end_headers()

    def _json_response(self, data):
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def log_message(self, format, *args):
        pass  # Suppress default logging


# --- WebSocket Server ---

async def handle_ws(websocket):
    print(f"[WS] Client connected")
    async for message in websocket:
        try:
            data = json.loads(message)
            action = data.get('action')

            if action == 'investigate':
                subject = data.get('subject', '')
                print(f"[WS] Investigate: {subject}")
                await websocket.send(json.dumps({'action': 'status', 'message': f'Investigating {subject}...'}))
                loop = asyncio.get_event_loop()
                success, entities, error = await loop.run_in_executor(None, do_investigate, subject)
                if success:
                    await websocket.send(json.dumps({'action': 'reload', 'message': f'{subject}: {entities} entities found'}))
                else:
                    await websocket.send(json.dumps({'action': 'error', 'message': error or 'Investigation failed'}))

            elif action == 'expand':
                entity_id = data.get('id', '')
                entity_name = data.get('label', '')
                search_mode = data.get('search_mode', 'web')
                enabled_feeds = data.get('enabled_feeds', None)
                print(f"[WS] Expand: {entity_name} (mode: {search_mode}, feeds: {enabled_feeds})")

                feeds_msg = f" + {len(enabled_feeds)} OSINT feeds" if enabled_feeds else ""
                await websocket.send(json.dumps({
                    'action': 'status',
                    'message': f'Searching for {entity_name} ({search_mode}{feeds_msg})...'
                }))

                loop = asyncio.get_event_loop()
                success, added, added_entities, feed_data, error = await loop.run_in_executor(
                    None, do_expand, entity_id, entity_name, search_mode, enabled_feeds
                )

                if success:
                    await websocket.send(json.dumps({
                        'action': 'expand_done',
                        'message': f'{entity_name}: +{added} new entities',
                        'added': added,
                        'added_entities': added_entities or [],
                        'feed_data': feed_data or {},
                    }))
                else:
                    await websocket.send(json.dumps({
                        'action': 'error',
                        'message': error or 'Expansion failed'
                    }))

            elif action == 'research_gaps':
                max_gaps = data.get('max_gaps', 5)
                print(f"[WS] Research gaps (top {max_gaps})")

                async def gap_status(msg):
                    pass  # handled via queue below

                import queue, concurrent.futures
                status_q = queue.Queue()
                def sync_gaps():
                    def cb(msg): status_q.put(msg)
                    return do_research_gaps(max_gaps, status_callback=cb)

                loop = asyncio.get_event_loop()
                executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
                future = loop.run_in_executor(executor, sync_gaps)

                while not future.done():
                    await asyncio.sleep(0.5)
                    while not status_q.empty():
                        msg = status_q.get_nowait()
                        await websocket.send(json.dumps({'action': 'status', 'message': msg}))

                success, researched, found, error = await future
                while not status_q.empty():
                    await websocket.send(json.dumps({'action': 'status', 'message': status_q.get_nowait()}))

                if success:
                    await websocket.send(json.dumps({
                        'action': 'reload',
                        'message': f'Gap research: {researched} gaps investigated, {found} connections found'
                    }))
                else:
                    await websocket.send(json.dumps({'action': 'error', 'message': error or 'Gap research failed'}))

            elif action == 'report':
                entity_id = data.get('id', '')
                entity_name = data.get('label', '')
                print(f"[WS] Report: {entity_name}")
                await websocket.send(json.dumps({'action': 'status', 'message': f'Generating report for {entity_name}...'}))
                loop = asyncio.get_event_loop()
                success, path, error = await loop.run_in_executor(None, do_generate_report, entity_id, entity_name)
                if success:
                    await websocket.send(json.dumps({'action': 'status', 'message': f'Report saved: {path}'}))
                else:
                    await websocket.send(json.dumps({'action': 'error', 'message': error or 'Report failed'}))

            elif action == 'scan_dataset':
                folder_path = data.get('path', '')
                print(f"[WS] Scan dataset: {folder_path}")

                async def ws_status(msg):
                    await websocket.send(json.dumps({'action': 'scan_status', 'message': msg}))

                # Can't pass async callback to sync function, use thread + queue
                import queue
                status_q = queue.Queue()

                def sync_scan():
                    def cb(msg):
                        status_q.put(msg)
                    return do_scan_dataset(folder_path, status_callback=cb)

                loop = asyncio.get_event_loop()
                # Start scan in thread
                import concurrent.futures
                executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
                future = loop.run_in_executor(executor, sync_scan)

                # Poll for status updates while scan runs
                while not future.done():
                    await asyncio.sleep(0.5)
                    while not status_q.empty():
                        msg = status_q.get_nowait()
                        await websocket.send(json.dumps({'action': 'scan_status', 'message': msg}))

                success, files_indexed, entities_added, error = await future
                # Drain remaining status messages
                while not status_q.empty():
                    msg = status_q.get_nowait()
                    await websocket.send(json.dumps({'action': 'scan_status', 'message': msg}))

                if success:
                    await websocket.send(json.dumps({
                        'action': 'scan_done',
                        'message': f'{files_indexed} files scanned, {entities_added} entities added'
                    }))
                    await websocket.send(json.dumps({'action': 'reload', 'message': 'Dataset scan complete'}))
                else:
                    await websocket.send(json.dumps({
                        'action': 'error',
                        'message': error or 'Scan failed'
                    }))
        except Exception as e:
            print(f"[WS] Error: {e}")
            await websocket.send(json.dumps({'action': 'error', 'message': str(e)}))


from socketserver import ThreadingMixIn

class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    allow_reuse_address = True
    daemon_threads = True

def start_http(port=8766):
    """Start threaded HTTP server — handles concurrent requests."""
    server = ThreadedHTTPServer(('localhost', port), ExpandHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    print(f"[DiveServer] HTTP on http://localhost:{port} (threaded)")


async def main():
    global GRAPH, INV_PATH, ENGINES

    import argparse
    parser = argparse.ArgumentParser(description="DeepDive Server")
    parser.add_argument("investigation", nargs="?", default=None, help="Path to investigation directory (optional)")
    parser.add_argument("--search", "-s", default=None,
                        help="Search engine (ddg, searxng, none)")
    parser.add_argument("--docs", help="Local document corpus path")
    args = parser.parse_args()

    # Check Claude SDK is available
    if not BRIDGE.is_available():
        print("[DiveServer] Claude CLI not found. Run 'claude login' first.")
        return
    print(f"[DiveServer] Engine: Claude Agent SDK")

    # Load investigation if specified
    if args.investigation:
        INV_PATH = args.investigation
        json_files = [f for f in os.listdir(INV_PATH) if f.endswith('.json')]
        if json_files:
            GRAPH = InvestigationGraph.load(os.path.join(INV_PATH, json_files[0]))
            print(f"[DiveServer] Loaded: {GRAPH.name} ({len(GRAPH.entities)} entities)")
        else:
            print(f"[DiveServer] No investigation data in {INV_PATH}")
    else:
        print(f"[DiveServer] No investigation loaded — create one from the app")

    # Setup search (optional — SDK has WebSearch built in, but DDG is no-auth)
    if args.search != "none":
        try:
            sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'cli'))
            from deepdive_cli import get_search_engines
            ENGINES = get_search_engines(search_pref=args.search, docs_dir=args.docs)
        except:
            pass  # SDK handles web search via built-in WebSearch tool

    # Start HTTP fallback
    start_http(8766)

    # Start WebSocket
    import websockets
    print(f"[DiveServer] WebSocket on ws://localhost:8765")
    print(f"[DiveServer] Open the board and click 'Dive Deeper' on any node")
    async with websockets.serve(handle_ws, "localhost", 8765):
        await asyncio.Future()


if __name__ == '__main__':
    asyncio.run(main())
