"""
OSINT Routes — feed queries, AI traces, analyze endpoint.
"""

import server.state as state
from graph import Entity, Connection
from extractors import extract_entities


def handle_osint_tool(tool, entity):
    """Handle all OSINT tool requests. Returns response dict."""
    result = {'success': True, 'message': '', 'results': [], 'reload': False}

    if tool in ('timeline', 'money', 'social', 'wayback'):
        return _handle_ai_trace(tool, entity)
    elif tool in ('feeds', 'patents', 'gov', 'sanctions', 'bluesky',
                  'conflicts', 'who', 'cisa', 'humanitarian',
                  'flights', 'satellites', 'earthquakes', 'weather',
                  'fires', 'launches', 'ships', 'sec', 'stock',
                  'gdelt', 'reddit', 'news', 'ofac'):
        return _handle_data_feed(tool, entity)
    elif tool == 'darkweb':
        return _handle_darkweb(entity)
    else:
        return {'success': False, 'error': f'Unknown tool: {tool}'}


def handle_analyze(entity, feed_data, feed_source):
    """Take raw OSINT feed data and send to AI for entity extraction."""
    if not state.GRAPH:
        return {'success': False, 'error': 'No investigation loaded'}

    prompt = f"""Analyze this {feed_source} data related to "{entity}" in the context of investigation "{state.GRAPH.name}".

FEED DATA:
{feed_data[:8000]}

Extract ALL people, companies, locations, events, and money connections.
Output each as: ENTITY_NAME | ENTITY_TYPE | RELATIONSHIP | CONFIDENCE (high/medium/low)"""

    response, _ = state.BRIDGE.research(entity, "feed_analysis", prompt)
    if not response or response.startswith("Error"):
        return {'success': False, 'error': response or 'Analysis failed'}

    extracted = extract_entities(response)
    added = 0
    entity_id = entity.lower().replace(' ', '_')
    parent_id = entity_id if entity_id in state.GRAPH.entities else list(state.GRAPH.entities.keys())[0]

    for name, etype, rel, conf in extracted:
        ent = Entity(name, etype, {"source": feed_source})
        ent.depth = 2
        if state.GRAPH.add_entity(ent):
            added += 1
        state.GRAPH.add_connection(Connection(parent_id, ent.id, rel, conf))

    if added:
        state.GRAPH.save(state.INV_PATH)
        from server.routes.investigation import _rebuild_board
        _rebuild_board()

    return {
        'success': True,
        'message': f'AI extracted {added} entities from {feed_source} data',
        'added': added,
        'reload': added > 0,
    }


def _handle_ai_trace(tool, entity):
    """Handle AI-powered OSINT traces (timeline, money, social, wayback)."""
    tool_fns = {
        'timeline': state.BRIDGE.trace_timeline,
        'money': state.BRIDGE.trace_money,
        'social': state.BRIDGE.scan_social_media,
        'wayback': state.BRIDGE.check_wayback,
    }
    tool_labels = {
        'timeline': 'timeline events',
        'money': 'money connections',
        'social': 'social media findings',
        'wayback': 'archived findings',
    }

    raw = tool_fns[tool](entity)
    extracted = extract_entities(raw)

    added = 0
    added_list = []
    entity_id = entity.lower().replace(' ', '_')

    for name, etype, rel, conf in extracted:
        ent = Entity(name, etype)
        ent.depth = 2
        is_new = state.GRAPH.add_entity(ent)
        if is_new:
            added += 1
        added_list.append({
            'title': name,
            'source': f'AI {tool} trace',
            'date': rel.replace('_', ' '),
            'extra': {'type': etype, 'confidence': conf, 'new': is_new},
        })
        state.GRAPH.add_connection(Connection(entity_id, ent.id, rel, conf))

    if added:
        state.GRAPH.save(state.INV_PATH)
        from server.routes.investigation import _rebuild_board
        _rebuild_board()

    return {
        'success': True,
        'message': f'{added} {tool_labels[tool]} ({len(extracted)} total analyzed)',
        'reload': added > 0,
        'results': added_list,
    }


def _handle_data_feed(tool, entity):
    """Handle data-only OSINT feeds (no AI, just fetch and display)."""
    from search.osint_feeds import OSINTFeeds
    feeds = OSINTFeeds()

    if tool == 'feeds':
        data = feeds.search_all(entity)
        items = []
        for source, entries in data.items():
            for entry in (entries or [])[:5]:
                items.append({
                    'title': entry.get('title', entry.get('name', '')),
                    'source': source,
                    'url': entry.get('url', ''),
                    'date': entry.get('date', ''),
                })
        return {
            'success': True,
            'message': f'{len(items)} feed results',
            'results': items,
            'reload': False,
        }
    else:
        items = feeds.search_targeted(entity, tool)
        formatted = []
        for item in (items or []):
            if isinstance(item, dict):
                title = item.get('title', item.get('name', item.get('event',
                        item.get('headline', item.get('cve', str(item)[:80])))))
                formatted.append({
                    'title': str(title)[:200],
                    'source': item.get('source', tool.upper()),
                    'url': item.get('url', item.get('archive_url', '')),
                    'date': item.get('date', item.get('date_added', item.get('effective', ''))),
                    'extra': {k: str(v)[:100] for k, v in item.items()
                              if k not in ('title', 'source', 'url', 'date', 'name') and v},
                })
        return {
            'success': True,
            'message': f'{len(formatted)} {tool} results',
            'results': formatted,
            'reload': False,
        }


def _handle_darkweb(entity):
    """Handle dark web search via Tor/SICRY."""
    import sys, os, importlib.util, socket

    # Check Tor SOCKS port first
    def tor_reachable():
        try:
            s = socket.socket()
            s.settimeout(2)
            result = s.connect_ex(('127.0.0.1', 9050))
            s.close()
            return result == 0
        except Exception:
            return False

    if not tor_reachable():
        return {
            'success': False,
            'message': 'Tor is not running. Start it with: sudo systemctl start tor',
            'results': [],
            'reload': False,
        }

    try:
        # darkweb.py IS the sicry library — load it as 'sicry' if not already
        if 'sicry' not in sys.modules:
            search_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'core', 'search')
            darkweb_path = os.path.join(search_dir, 'darkweb.py')
            spec = importlib.util.spec_from_file_location('sicry', darkweb_path)
            mod = importlib.util.module_from_spec(spec)
            sys.modules['sicry'] = mod
            spec.loader.exec_module(mod)

        import sicry

        # Verify Tor is live
        tor_info = sicry.check_tor()
        if not tor_info.get('tor_active'):
            return {
                'success': False,
                'message': 'Tor is not active. Run: sudo systemctl start tor',
                'results': [],
                'reload': False,
            }

        results = sicry.search(entity, max_results=15)
        items = []
        for r in (results if isinstance(results, list) else []):
            title = r.get('title') or r.get('name') or r.get('url', '')
            url = r.get('url') or r.get('link', '')
            engine = r.get('engine', 'onion')
            if title or url:
                items.append({
                    'title': title[:200],
                    'source': f'Dark Web ({engine})',
                    'url': url,
                    'date': '',
                })

        exit_ip = tor_info.get('exit_ip', 'unknown')
        return {
            'success': True,
            'message': f'{len(items)} dark web results (exit node: {exit_ip})',
            'results': items,
            'reload': False,
        }

    except Exception as e:
        return {
            'success': False,
            'message': f'Dark web search error: {e}',
            'results': [],
            'reload': False,
        }
