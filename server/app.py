#!/usr/bin/env python3
"""
DeepDive Server — Main entry point.
HTTP server (port 8766) + WebSocket server (port 8765).
Routes are handled by modules in server/routes/.
"""

import asyncio
import json
import os
import sys
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn

# Setup paths
_root = os.path.join(os.path.dirname(__file__), '..')
sys.path.insert(0, os.path.join(_root, 'core'))
sys.path.insert(0, os.path.join(_root, 'cli'))
sys.path.insert(0, os.path.join(_root, 'src'))

import server.state as state
from server.routes import investigation, osint
from graph import InvestigationGraph, Entity, Connection
from interview import InvestigationConfig, get_focus_categories, get_depth_levels
from node_actions import prune_node, pin_node, add_note, get_pinned
from views.timeline import build_timeline
from views.report import build_report
from views.money_flow import build_money_flow
from views.settings import build_settings_page, load_settings, save_settings
from plugins import create_plugin_template


def pick_folder_dialog():
    """Open a native OS folder picker dialog."""
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


class RequestHandler(BaseHTTPRequestHandler):
    """HTTP request handler — routes to appropriate module."""

    def do_GET(self):
        if self.path == '/settings':
            self._serve_html(build_settings_page())

        elif self.path == '/report-view':
            if state.GRAPH and state.INV_PATH:
                rpt_path = os.path.join(state.INV_PATH, 'report_full.html')
                build_report(state.GRAPH, rpt_path, f'Investigation Report: {state.GRAPH.name}')
                self._serve_file(rpt_path, 'text/html')
            else:
                self._not_found()

        elif self.path == '/timeline':
            if state.GRAPH and state.INV_PATH:
                tl_path = os.path.join(state.INV_PATH, 'timeline.html')
                build_timeline(state.GRAPH, tl_path, f'Timeline: {state.GRAPH.name}')
                self._serve_file(tl_path, 'text/html')
            else:
                self._not_found()

        elif self.path == '/money-flow':
            if state.GRAPH and state.INV_PATH:
                mf_path = os.path.join(state.INV_PATH, 'money_flow.html')
                build_money_flow(state.GRAPH, mf_path, f'Money Flow: {state.GRAPH.name}')
                self._serve_file(mf_path, 'text/html')
            else:
                self._not_found()

        elif self.path == '/board' or self.path == '/':
            if not state.GRAPH:
                investigation.create_empty_investigation()
            index_path = os.path.join(state.get_frontend_dir(), 'index.html')
            if os.path.exists(index_path):
                self._serve_file(index_path, 'text/html')
            else:
                self._not_found()

        elif self.path.startswith('/static/'):
            self._serve_static()

        else:
            self._not_found()

    def do_POST(self):
        length = int(self.headers.get('Content-Length', 0))
        body = json.loads(self.rfile.read(length)) if length > 0 else {}

        try:
            self._route_post(body)
        except Exception as e:
            print(f"[HTTP Error] {self.path}: {e}")
            import traceback; traceback.print_exc()
            self._json({'success': False, 'error': str(e)})

    def _route_post(self, body):
        path = self.path

        # ── Board Data API ──
        if path == '/api/board-data':
            if not state.GRAPH:
                investigation.create_empty_investigation()
            stats = state.GRAPH.get_stats()
            nodes = []
            for eid, entity in state.GRAPH.entities.items():
                color = state.COLORS.get(entity.type, '#6B7280')
                conns = len(state.GRAPH.get_connections_for(eid))
                nodes.append({
                    'id': eid, 'label': entity.name, 'type': entity.type,
                    'color': color, 'size': min(2 + conns * 0.4, 10),
                    'depth': entity.depth, 'investigated': entity.investigated,
                    'metadata': entity.metadata, 'connections': conns,
                })
            edges = [{'from': c.source_id, 'to': c.target_id,
                      'label': c.relationship.replace('_', ' '), 'confidence': c.confidence}
                     for c in state.GRAPH.connections]
            title = f'Investigation: {state.GRAPH.name}' if state.GRAPH.name != 'New Investigation' else 'DeepDive'
            self._json({'nodes': nodes, 'edges': edges, 'colors': state.COLORS,
                        'title': title, 'stats': stats, 'findings': state.GRAPH.findings or []})

        # ── Investigation ──
        elif path == '/expand':
            eid = body.get('id', '')
            label = body.get('label', '')
            mode = body.get('search_mode', 'web')
            feeds = body.get('enabled_feeds', None)
            preview = body.get('preview_only', False)
            success, added, added_entities, feed_data, error = investigation.do_expand(eid, label, mode, feeds, preview)
            self._json({'success': success, 'added': added, 'error': error,
                        'added_entities': added_entities or [], 'feed_data': feed_data or {}})

        elif path == '/stage_entities':
            # Stage entities from a direct expand call for approval
            from server.routes.approval import stage_entities
            entities = body.get('entities', [])
            source_id = body.get('source_id', '')
            source_label = body.get('source_label', '')
            tuples = [(e['name'], e['type'], e['relationship'], e.get('confidence', 0.5)) for e in entities]
            connections = [(source_id, e['name'].lower().replace(' ', '_')) for e in entities]
            batch_id, staged = stage_entities(tuples, connections, f"Expand: {source_label}")
            self._json({'success': True, 'batch_id': batch_id, 'staged': len(staged)})

        elif path == '/investigate':
            subject = body.get('subject', '')
            success, entities, error = investigation.do_investigate(subject)
            self._json({'success': success, 'entities': entities, 'error': error})

        elif path == '/interview/options':
            self._json({'focus_categories': get_focus_categories(), 'depth_levels': get_depth_levels()})

        elif path == '/interview/start':
            config = InvestigationConfig.from_dict(body)
            expand = body.get('mode') == 'expand'
            success, entities, error = investigation.do_investigate_with_config(config, expand_current=expand)
            self._json({'success': success, 'entities': entities, 'error': error})

        elif path == '/home':
            investigation.reset_to_home()
            self._json({'success': True})

        elif path == '/list_investigations':
            self._json({'investigations': investigation.list_investigations()})

        elif path == '/switch':
            inv_dir = body.get('dir', '')
            success, error, board_url = investigation.switch_investigation(inv_dir)
            self._json({'success': success, 'error': error, 'board_url': board_url})

        elif path == '/new_investigation':
            name = body.get('name', '')
            success, error, board_url = investigation.create_new_investigation(name)
            self._json({'success': success, 'error': error, 'board_url': board_url})

        # ── Reports ──
        elif path == '/report':
            eid = body.get('id', '')
            label = body.get('label', '')
            success, rpath, error = investigation.do_generate_report(eid, label)
            self._json({'success': success, 'path': rpath, 'error': error})

        elif path == '/report/get':
            eid = body.get('id', '')
            if state.INV_PATH:
                reports_dir = os.path.join(state.INV_PATH, 'reports')
                for fname in os.listdir(reports_dir) if os.path.isdir(reports_dir) else []:
                    if fname[:-3].lower().replace(' ', '_') == eid:
                        with open(os.path.join(reports_dir, fname)) as f:
                            self._json({'exists': True, 'content': f.read()})
                        return
            self._json({'exists': False})

        elif path == '/list_reports':
            self._json({'reports': investigation.list_reports()})

        # ── Gaps ──
        elif path == '/list_gaps':
            gaps = state.GRAPH.detect_gaps() if state.GRAPH else []
            self._json({'gaps': gaps[:20]})

        elif path == '/research_gaps':
            max_gaps = body.get('max_gaps', 5)
            success, researched, found, error = investigation.do_research_gaps(max_gaps)
            self._json({'success': success, 'gaps_researched': researched, 'gaps_found': found, 'error': error})

        # ── Nodes ──
        elif path == '/node/prune':
            eid = body.get('id', '')
            if state.GRAPH:
                success, error = prune_node(state.GRAPH, eid)
                if success:
                    state.GRAPH.save(state.INV_PATH)
                    investigation._rebuild_board()
                self._json({'success': success, 'error': error})
            else:
                self._json({'success': False, 'error': 'No investigation'})

        elif path == '/node/pin':
            eid = body.get('id', '')
            if state.GRAPH:
                success, pinned = pin_node(state.GRAPH, eid)
                self._json({'success': success, 'pinned': pinned})
            else:
                self._json({'success': False})

        elif path == '/node/note':
            eid = body.get('id', '')
            note = body.get('note', '')
            if state.GRAPH:
                success, count = add_note(state.GRAPH, eid, note)
                self._json({'success': success, 'count': count})
            else:
                self._json({'success': False})

        elif path == '/node/pinned':
            if state.GRAPH:
                self._json({'pinned': get_pinned(state.GRAPH)})
            else:
                self._json({'pinned': []})

        # ── OSINT ──
        elif path == '/osint/analyze':
            entity = body.get('entity', '')
            data = body.get('data', '')
            source = body.get('source', 'OSINT feed')
            result = osint.handle_analyze(entity, data, source)
            self._json(result)

        elif path.startswith('/osint/'):
            tool = path.split('/osint/')[1]
            entity = body.get('entity', '')
            print(f"[HTTP] OSINT tool: {tool} on {entity}")
            result = osint.handle_osint_tool(tool, entity)
            self._json(result)

        # ── Settings ──
        elif path == '/settings/save':
            success = save_settings(body)
            self._json({'success': success})

        elif path == '/settings/load':
            self._json(load_settings())

        # ── Plugins ──
        elif path == '/plugins/list':
            self._json({'plugins': [p.to_dict() for p in state.PLUGIN_MGR.plugins]})

        elif path == '/plugins/toggle':
            name = body.get('name', '')
            state.PLUGIN_MGR.toggle(name)
            self._json({'success': True})

        elif path == '/plugins/install':
            source = body.get('source', '')
            success = state.PLUGIN_MGR.install(source)
            self._json({'success': success})

        elif path == '/plugins/create':
            name = body.get('name', 'my-plugin')
            path_out = create_plugin_template(name)
            self._json({'success': True, 'path': path_out})

        # ── Approval ──
        elif path == '/approve':
            from server.routes.approval import approve_entities
            batch_id = body.get('batch_id', '')
            indices = body.get('approved_indices', None)
            added, skipped, error = approve_entities(batch_id, indices)
            self._json({'success': error is None, 'added': added, 'skipped': skipped, 'error': error})

        elif path == '/reject':
            from server.routes.approval import reject_batch
            batch_id = body.get('batch_id', '')
            success = reject_batch(batch_id)
            self._json({'success': success})

        # ── Task Manager / Heartbeat ──
        elif path == '/heartbeat':
            from server.task_manager import TASK_MGR
            self._json(TASK_MGR.get_status_summary())

        elif path == '/tasks':
            from server.task_manager import TASK_MGR
            unfinished = TASK_MGR.get_unfinished()
            self._json({'tasks': [t.to_dict() for t in unfinished]})

        # ── Onboarding ──
        elif path == '/onboarding/state':
            from server.routes.onboarding import get_onboarding_state
            self._json(get_onboarding_state())

        elif path == '/onboarding/step':
            from server.routes.onboarding import process_onboarding_step
            step_id = body.get('step_id', '')
            user_input = body.get('input', '')
            result, is_complete = process_onboarding_step(step_id, user_input)
            self._json({**result, 'complete': is_complete})

        elif path == '/onboarding/greeting':
            from server.routes.onboarding import get_greeting
            self._json(get_greeting())

        # ── Auth / Usage ──
        elif path == '/auth/status':
            available = state.BRIDGE.is_available()
            settings = state.BRIDGE._get_settings()
            self._json({'authenticated': available, 'provider': settings.get('provider', 'claude'),
                        'user': {'method': settings.get('provider', 'claude')}})

        elif path == '/usage':
            from auth.bridge import USAGE
            self._json(USAGE.get_stats())

        elif path == '/kill':
            from auth.bridge import USAGE
            USAGE.kill()
            self._json({'success': True, 'message': 'Kill signal sent'})

        elif path == '/kill/reset':
            from auth.bridge import USAGE
            USAGE.reset_kill()
            self._json({'success': True})

        # ── File Memory ──
        elif path == '/files/memory':
            try:
                from file_memory import get_all
                data = get_all()
                self._json(data)
            except Exception as e:
                self._json({'corpora': [], 'individual_files': [], 'error': str(e)})

        # ── Knowledge Graph / Obsidian ──
        elif path == '/export/obsidian':
            if not state.GRAPH:
                self._json({'success': False, 'error': 'No investigation loaded'})
                return
            vault_path = body.get('vault_path', '')
            if not vault_path:
                # Default: alongside the investigation files
                vault_path = os.path.join(state.INV_PATH, 'obsidian_vault')
            try:
                from obsidian_export import export_to_vault
                result = export_to_vault(state.GRAPH, vault_path)
                self._json({
                    'success': True,
                    'written': result['written'],
                    'skipped': result['skipped'],
                    'vault_path': result['vault_path'],
                    'index_path': result['index_path'],
                    'message': f"Exported {result['written']} entity notes to {result['vault_path']}",
                })
            except Exception as e:
                import traceback; traceback.print_exc()
                self._json({'success': False, 'error': str(e)})

        elif path == '/crosslinks/scan':
            try:
                from cross_linker import find_cross_links
                inv_dir = state.get_investigations_dir()
                current = state.GRAPH.name if state.GRAPH else None
                result = find_cross_links(inv_dir, current_investigation_name=current)
                self._json({'success': True, **result})
            except Exception as e:
                import traceback; traceback.print_exc()
                self._json({'success': False, 'error': str(e)})

        # ── Export ──
        elif path == '/export/json':
            if state.GRAPH:
                export = {
                    'name': state.GRAPH.name,
                    'entities': {eid: {'name': e.name, 'type': e.type, 'metadata': e.metadata,
                                       'depth': e.depth, 'investigated': e.investigated}
                                 for eid, e in state.GRAPH.entities.items()},
                    'connections': [{'source': c.source_id, 'target': c.target_id,
                                     'relationship': c.relationship, 'confidence': c.confidence}
                                    for c in state.GRAPH.connections],
                    'findings': state.GRAPH.findings,
                    'gaps': state.GRAPH.gaps[:50] if state.GRAPH.gaps else [],
                }
                self._json(export)
            else:
                self._json({'error': 'No investigation loaded'})

        elif path == '/export/markdown':
            if state.GRAPH:
                md = f"# Investigation: {state.GRAPH.name}\n\n"
                by_type = {}
                for eid, e in state.GRAPH.entities.items():
                    by_type.setdefault(e.type, []).append(e)
                for t, entities in sorted(by_type.items()):
                    md += f"## {t.title()}s ({len(entities)})\n\n"
                    for e in entities:
                        md += f"- **{e.name}**\n"
                    md += "\n"
                self.send_response(200)
                self.send_header('Content-Type', 'text/markdown')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(md.encode())
            else:
                self._json({'error': 'No investigation loaded'})

        # ── File Browser ──
        elif path == '/pick_folder':
            folder = pick_folder_dialog()
            self._json({'path': folder})

        elif path == '/browse_dir':
            target = body.get('path', '/home')
            try:
                if not os.path.isdir(target):
                    target = os.path.dirname(target) or '/home'
                dirs = [{'name': name, 'path': os.path.join(target, name)}
                        for name in sorted(os.listdir(target))
                        if os.path.isdir(os.path.join(target, name)) and not name.startswith('.')]
                parent = os.path.dirname(target.rstrip('/')) or '/'
                self._json({'success': True, 'path': target, 'parent': parent, 'dirs': dirs})
            except PermissionError:
                self._json({'success': False, 'error': 'Permission denied'})
            except Exception as e:
                self._json({'success': False, 'error': str(e)})

        # ── File Ingestion ──
        elif path == '/ingest/count':
            from server.routes.file_ingest import count_documents
            folder = body.get('path', '')
            count, error = count_documents(folder)
            self._json({'count': count, 'error': error})

        elif path == '/ingest/batch':
            from server.routes.file_ingest import process_batch
            folder = body.get('path', '')
            batch_idx = body.get('batch_index', 0)
            result = process_batch(folder, batch_idx)
            self._json(result)

        # ── Scan Dataset (legacy) ──
        elif path == '/scan':
            folder = body.get('path', '')
            success, files, added, error = investigation.do_scan_dataset(folder)
            self._json({'success': success, 'files_indexed': files, 'entities_added': added, 'error': error})

        # ── Timeline View Data ──
        elif path == '/view/timeline':
            if state.GRAPH and state.INV_PATH:
                tl_path = os.path.join(state.INV_PATH, 'timeline.html')
                build_timeline(state.GRAPH, tl_path, f'Timeline: {state.GRAPH.name}')
                self._json({'success': True, 'url': '/timeline'})
            else:
                self._json({'success': False, 'error': 'No investigation'})

        else:
            self.send_response(404)
            self.end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def log_message(self, format, *args):
        pass  # Suppress default logging

    # ── Response helpers ──

    def _json(self, data):
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def _serve_html(self, html_content):
        self.send_response(200)
        self.send_header('Content-Type', 'text/html')
        self.end_headers()
        self.wfile.write(html_content.encode())

    def _serve_file(self, file_path, content_type):
        if os.path.exists(file_path):
            self.send_response(200)
            self.send_header('Content-Type', content_type)
            self.end_headers()
            with open(file_path, 'rb') as f:
                self.wfile.write(f.read())
        else:
            self._not_found()

    def _serve_static(self):
        frontend_dir = state.get_frontend_dir()
        rel_path = self.path[len('/static/'):]
        file_path = os.path.realpath(os.path.join(frontend_dir, rel_path))
        frontend_real = os.path.realpath(frontend_dir)

        if not file_path.startswith(frontend_real) or not os.path.isfile(file_path):
            self._not_found()
            return

        ext = os.path.splitext(file_path)[1].lower()
        content_types = {
            '.css': 'text/css', '.js': 'application/javascript',
            '.html': 'text/html', '.svg': 'image/svg+xml',
            '.png': 'image/png', '.jpg': 'image/jpeg',
            '.ico': 'image/x-icon', '.json': 'application/json',
            '.woff2': 'font/woff2', '.woff': 'font/woff',
        }
        ct = content_types.get(ext, 'application/octet-stream')
        self.send_response(200)
        self.send_header('Content-Type', ct)
        self.send_header('Cache-Control', 'no-cache')
        self.end_headers()
        with open(file_path, 'rb') as f:
            self.wfile.write(f.read())

    def _not_found(self):
        self.send_response(404)
        self.end_headers()


# ── WebSocket Server ──

async def handle_ws(websocket):
    """Handle WebSocket connections for live updates and chat."""
    print(f"[WS] Client connected")
    async for message in websocket:
        try:
            data = json.loads(message)
            action = data.get('action')

            # ── Node Selection ──
            if action == 'select_node':
                websocket._selected_node = data.get('node_name', '')
                websocket._selected_node_id = data.get('node_id', '')
                websocket._selected_node_type = data.get('node_type', '')
                websocket._last_discussed_entity = data.get('node_name', '')
                continue

            # ── Chat Messages ──
            if action == 'chat':
                from server.routes.chat import handle_chat_message
                user_msg = data.get('message', '')
                print(f"[WS Chat] User: {user_msg[:80]}")
                try:
                    response = await handle_chat_message(websocket, user_msg)
                    # CLI mode returns text that hasn't been sent yet
                    # API mode already sent via agent_message, but sending again is harmless
                    if response:
                        await websocket.send(json.dumps({
                            'type': 'agent_message',
                            'text': response,
                        }))
                    await websocket.send(json.dumps({'type': 'chat_done'}))
                except Exception as e:
                    traceback.print_exc()
                    await websocket.send(json.dumps({
                        'type': 'agent_message',
                        'text': f'I encountered an error: {e}'
                    }))
                    await websocket.send(json.dumps({'type': 'chat_done'}))
                continue

            if action == 'investigate':
                subject = data.get('subject', '')
                await websocket.send(json.dumps({'action': 'status', 'message': f'Investigating {subject}...'}))
                loop = asyncio.get_event_loop()
                success, entities, error = await loop.run_in_executor(None, investigation.do_investigate, subject)
                if success:
                    await websocket.send(json.dumps({'action': 'reload', 'message': f'{subject}: {entities} entities found'}))
                else:
                    await websocket.send(json.dumps({'action': 'error', 'message': error or 'Failed'}))

            elif action == 'expand':
                eid = data.get('id', '')
                label = data.get('label', '')
                search_mode = data.get('search_mode', 'web')
                enabled_feeds = data.get('enabled_feeds', None)
                feeds_msg = f" + {len(enabled_feeds)} OSINT feeds" if enabled_feeds else ""
                await websocket.send(json.dumps({'action': 'status', 'message': f'Searching for {label} ({search_mode}{feeds_msg})...'}))
                loop = asyncio.get_event_loop()
                success, added, added_entities, feed_data, error = await loop.run_in_executor(
                    None, investigation.do_expand, eid, label, search_mode, enabled_feeds)
                if success:
                    await websocket.send(json.dumps({
                        'action': 'expand_done', 'message': f'{label}: +{added} new entities',
                        'added': added, 'added_entities': added_entities or [], 'feed_data': feed_data or {},
                    }))
                else:
                    await websocket.send(json.dumps({'action': 'error', 'message': error or 'Failed'}))

            elif action == 'research_gaps':
                max_gaps = data.get('max_gaps', 5)
                import queue, concurrent.futures
                status_q = queue.Queue()
                def sync_gaps():
                    return investigation.do_research_gaps(max_gaps, status_callback=lambda msg: status_q.put(msg))
                loop = asyncio.get_event_loop()
                executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
                future = loop.run_in_executor(executor, sync_gaps)
                while not future.done():
                    await asyncio.sleep(0.5)
                    while not status_q.empty():
                        await websocket.send(json.dumps({'action': 'status', 'message': status_q.get_nowait()}))
                success, researched, found, error = await future
                if success:
                    await websocket.send(json.dumps({'action': 'reload', 'message': f'Gap research: {researched} gaps, {found} connections'}))
                else:
                    await websocket.send(json.dumps({'action': 'error', 'message': error or 'Failed'}))

            elif action == 'report':
                eid = data.get('id', '')
                label = data.get('label', '')
                await websocket.send(json.dumps({'action': 'status', 'message': f'Generating report for {label}...'}))
                loop = asyncio.get_event_loop()
                success, path, error = await loop.run_in_executor(None, investigation.do_generate_report, eid, label)
                if success:
                    await websocket.send(json.dumps({'action': 'status', 'message': f'Report saved: {path}'}))
                else:
                    await websocket.send(json.dumps({'action': 'error', 'message': error or 'Failed'}))

            elif action == 'scan_dataset':
                folder_path = data.get('path', '')
                import queue, concurrent.futures
                status_q = queue.Queue()
                def sync_scan():
                    return investigation.do_scan_dataset(folder_path, status_callback=lambda msg: status_q.put(msg))
                loop = asyncio.get_event_loop()
                executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
                future = loop.run_in_executor(executor, sync_scan)
                while not future.done():
                    await asyncio.sleep(0.5)
                    while not status_q.empty():
                        await websocket.send(json.dumps({'action': 'scan_status', 'message': status_q.get_nowait()}))
                success, files_indexed, entities_added, error = await future
                while not status_q.empty():
                    await websocket.send(json.dumps({'action': 'scan_status', 'message': status_q.get_nowait()}))
                if success:
                    await websocket.send(json.dumps({'action': 'scan_done', 'message': f'{files_indexed} files, {entities_added} entities'}))
                    await websocket.send(json.dumps({'action': 'reload', 'message': 'Scan complete'}))
                else:
                    await websocket.send(json.dumps({'action': 'error', 'message': error or 'Failed'}))

        except Exception as e:
            print(f"[WS] Error: {e}")
            await websocket.send(json.dumps({'action': 'error', 'message': str(e)}))


# ── Server Setup ──

class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    allow_reuse_address = True
    daemon_threads = True


def start_http(port=8766):
    server = ThreadedHTTPServer(('localhost', port), RequestHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    print(f"[DiveServer] HTTP on http://localhost:{port}")


async def main():
    import argparse
    parser = argparse.ArgumentParser(description="DeepDive Server")
    parser.add_argument("investigation", nargs="?", default=None, help="Investigation directory path")
    parser.add_argument("--search", "-s", default=None, help="Search engine (ddg, searxng, none)")
    parser.add_argument("--docs", help="Local document corpus path")
    args = parser.parse_args()

    if not state.BRIDGE.is_available():
        print("[DiveServer] Warning: no AI provider configured. Go to Settings to set up Ollama or an API key.")
    else:
        settings = state.BRIDGE._get_settings()
        provider = settings.get('provider', 'ollama')
        model = settings.get('ollama_model', '') if provider == 'ollama' else settings.get('openai_model', '')
        print(f"[DiveServer] Engine: {provider}{(' / ' + model) if model else ''}")

    # ── Tor / dark web ──
    import socket as _sock
    def _tor_up():
        try:
            s = _sock.socket(); s.settimeout(2)
            r = s.connect_ex(('127.0.0.1', 9050)); s.close(); return r == 0
        except Exception: return False

    if _tor_up():
        print("[DiveServer] Tor: running on 127.0.0.1:9050 — dark web search enabled")
    else:
        print("[DiveServer] Tor: not detected — attempting to start...")
        try:
            import subprocess
            result = subprocess.run(['sudo', '-S', 'systemctl', 'start', 'tor'],
                input='3701\n', capture_output=True, text=True, timeout=10)
            import time as _time; _time.sleep(3)
            if _tor_up():
                print("[DiveServer] Tor: started successfully — dark web search enabled")
            else:
                print("[DiveServer] Tor: could not start — dark web search unavailable")
                print("[DiveServer]   Install: sudo apt install tor && sudo systemctl start tor")
        except Exception as e:
            print(f"[DiveServer] Tor: auto-start failed ({e}) — dark web search unavailable")

    if args.investigation:
        state.INV_PATH = args.investigation
        json_files = [f for f in os.listdir(state.INV_PATH) if f.endswith('.json')]
        if json_files:
            state.GRAPH = InvestigationGraph.load(os.path.join(state.INV_PATH, json_files[0]))
            print(f"[DiveServer] Loaded: {state.GRAPH.name} ({len(state.GRAPH.entities)} entities)")
    else:
        print(f"[DiveServer] No investigation loaded — create one from the app")

    if args.search != "none":
        try:
            from deepdive_cli import get_search_engines
            state.ENGINES = get_search_engines(search_pref=args.search, docs_dir=args.docs)
        except:
            pass

    start_http(8766)

    import websockets
    print(f"[DiveServer] WebSocket on ws://localhost:8765")
    print(f"[DiveServer] Open http://localhost:8766 in your browser")
    async with websockets.serve(handle_ws, "localhost", 8765):
        await asyncio.Future()


if __name__ == '__main__':
    asyncio.run(main())
