"""
Chat Routes — WebSocket chat handler with tool execution loop.
Receives user messages, sends to AI with harness + tools,
executes tool calls, returns results.
"""

import json
import asyncio
import os
import traceback

import server.state as state
from server.routes import investigation, osint
from server.task_manager import TASK_MGR
from core.harness.system_prompt import build_system_prompt
from core.harness.tools import get_tools_for_claude
from core.harness.persona import load_persona, save_persona, is_first_run


def get_investigation_state():
    """Build current investigation state dict for the system prompt."""
    if not state.GRAPH:
        return None

    stats = state.GRAPH.get_stats()

    # Top entities by connection count
    top = []
    for eid, entity in sorted(state.GRAPH.entities.items(),
                               key=lambda x: -len(state.GRAPH.get_connections_for(x[0])))[:10]:
        top.append(entity.name)

    return {
        'name': state.GRAPH.name,
        'entity_count': stats.get('total_entities', 0),
        'connection_count': stats.get('total_connections', 0),
        'gap_count': stats.get('gaps_found', 0),
        'investigated_count': stats.get('investigated', 0),
        'report_count': len(investigation.list_reports()),
        'top_entities': top,
        'recent_findings': (state.GRAPH.findings or [])[-5:],
    }


async def handle_chat_message(websocket, user_message):
    """Process a chat message through the AI with tool calling loop."""

    # Build system prompt with current state + file memory
    inv_state = get_investigation_state()
    try:
        from file_memory import get_corpus_summary
        file_summary = get_corpus_summary()
    except Exception:
        file_summary = None
    system_prompt = build_system_prompt(inv_state, file_memory_summary=file_summary)
    tools = get_tools_for_claude()

    # Get conversation history from the session (stored on websocket object)
    if not hasattr(websocket, '_chat_history'):
        websocket._chat_history = []

    # Add user message to history
    websocket._chat_history.append({"role": "user", "content": user_message})

    # Keep history manageable (last 20 messages)
    if len(websocket._chat_history) > 40:
        websocket._chat_history = websocket._chat_history[-40:]

    try:
        # Call the AI with tool loop
        response_text = await _run_tool_loop(
            websocket, system_prompt, websocket._chat_history, tools)

        # Add assistant response to history
        if response_text:
            websocket._chat_history.append({"role": "assistant", "content": response_text})

        # Send the response here — return None so app.py doesn't double-send
        if response_text:
            await websocket.send(json.dumps({
                'type': 'agent_message',
                'text': response_text,
            }))

        return None  # Already sent

    except Exception as e:
        error_msg = f"Error: {str(e)}"
        traceback.print_exc()
        return error_msg


async def _run_tool_loop(websocket, system_prompt, messages, tools):
    """Run the AI → tool_use → result → AI loop until done.
    Returns the final text response."""

    import requests

    settings = state.BRIDGE._get_settings()
    provider = settings.get('provider', 'claude')

    if provider == 'claude_api':
        api_key = settings.get('api_keys', {}).get('claude_api', '')
        if not api_key:
            return "I need an API key to work. Please go to Settings and add your Anthropic API key."
        return await _run_claude_api_loop(websocket, system_prompt, messages, tools, api_key)
    else:
        # Claude CLI mode — single call, no tool loop (CLI handles tools internally)
        return await _run_claude_cli(websocket, system_prompt, messages)


async def _run_claude_api_loop(websocket, system_prompt, messages, tools, api_key):
    """Run the tool loop using Claude API directly."""

    import requests

    max_iterations = 10  # Safety limit
    iteration = 0
    current_messages = list(messages)

    while iteration < max_iterations:
        iteration += 1

        # Send status
        await websocket.send(json.dumps({
            'type': 'status',
            'message': 'Thinking...' if iteration == 1 else f'Processing tool results (step {iteration})...'
        }))

        # Call Claude API
        try:
            response = requests.post(
                'https://api.anthropic.com/v1/messages',
                headers={
                    'x-api-key': api_key,
                    'anthropic-version': '2023-06-01',
                    'content-type': 'application/json',
                },
                json={
                    'model': 'claude-sonnet-4-5-20250929',
                    'max_tokens': 4096,
                    'system': system_prompt,
                    'messages': current_messages,
                    'tools': tools,
                },
                timeout=300,
            )
        except requests.Timeout:
            return "Request timed out. The investigation might be too complex for a single call."
        except Exception as e:
            return f"API error: {e}"

        if response.status_code != 200:
            return f"API error ({response.status_code}): {response.text[:200]}"

        data = response.json()
        content_blocks = data.get('content', [])
        stop_reason = data.get('stop_reason', '')

        # Extract text and tool_use blocks
        text_parts = []
        tool_calls = []
        for block in content_blocks:
            if block.get('type') == 'text':
                text_parts.append(block['text'])
            elif block.get('type') == 'tool_use':
                tool_calls.append(block)

        # If there are text parts, stream them to the client
        combined_text = '\n'.join(text_parts)
        if combined_text:
            await websocket.send(json.dumps({
                'type': 'agent_message',
                'text': combined_text,
            }))

        # If no tool calls, we're done (already sent via agent_message above)
        if stop_reason != 'tool_use' or not tool_calls:
            return None  # Already sent to client

        # Execute tool calls
        # Add the assistant message with tool_use to history
        current_messages.append({"role": "assistant", "content": content_blocks})

        # Execute each tool and collect results
        tool_results = []
        for tool_call in tool_calls:
            tool_name = tool_call['name']
            tool_input = tool_call['input']
            tool_id = tool_call['id']

            # Send status about which tool is being used
            await websocket.send(json.dumps({
                'type': 'tool_status',
                'tool': tool_name,
                'input': tool_input,
            }))

            # Execute the tool
            try:
                result = await _execute_tool(tool_name, tool_input)
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tool_id,
                    "content": json.dumps(result) if isinstance(result, (dict, list)) else str(result),
                })
            except Exception as e:
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tool_id,
                    "content": f"Error executing {tool_name}: {e}",
                    "is_error": True,
                })

        # Add tool results to messages
        current_messages.append({"role": "user", "content": tool_results})

    return "Reached maximum processing steps. The investigation may need to be broken into smaller parts."


async def _run_claude_cli(websocket, system_prompt, messages):
    """Run via Claude CLI — detects user intent, executes server functions,
    then has Claude respond about the results."""

    from core.harness.persona import load_persona
    persona = load_persona()
    agent_name = persona.get('investigator_name') or 'Investigator'
    user_name = persona.get('user_name') or 'User'

    # Get the user's message
    last_user_msg = ""
    for msg in reversed(messages):
        if msg['role'] == 'user':
            last_user_msg = msg['content'] if isinstance(msg['content'], str) else str(msg['content'])
            break

    if not last_user_msg:
        return "What would you like me to investigate?"

    loop = asyncio.get_event_loop()

    # ── Detect intent and execute actions ──
    action_result = await _detect_and_execute(websocket, last_user_msg, agent_name, user_name, loop)

    if action_result:
        action_context, action_data = action_result

        # If an approval list was already sent, skip the model summary —
        # the entities are displayed in the chat, no need for prose
        if action_data and (action_data.get('found') or action_data.get('batch_id') or
                            action_data.get('gaps_shown') or action_data.get('path')):
            return action_context

        # For other actions, have the model summarize briefly
        prompt = f"""You are {agent_name}, OSINT investigator for {user_name}. Stay in character. Be concise. Report facts only — no opinions, no moral judgments, no defending or dismissing subjects. Summarize findings, then suggest ONE next action.

{user_name} asked: "{last_user_msg}"

Results:
{action_context}

Briefly tell {user_name} what you found. Then suggest the single most promising next lead. End with a clear question like "Want me to trace X?" or "Should I check Y?"

{agent_name}:"""

        await websocket.send(json.dumps({
            'type': 'status',
            'message': f'{agent_name} is reviewing results...'
        }))

        try:
            response = await asyncio.wait_for(
                loop.run_in_executor(None, state.BRIDGE._call, prompt),
                timeout=300
            )
        except (asyncio.TimeoutError, Exception) as e:
            # Fall back to just showing the raw results
            return action_context

        if response and not response.startswith("Error"):
            response = _strip_thinking(response)
            # Parse model's text for suggestions
            _store_suggestion(websocket, response)
            # Also store concrete pending action based on what we just found
            if action_data and action_data.get('entities'):
                # After expand, the logical next action is to expand the most interesting found entity
                top = action_data['entities'][0] if action_data['entities'] else None
                if top:
                    _store_pending_action(websocket, 'expand', top['name'])
            return response
        return action_context
    else:
        # No action detected — just have Claude respond conversationally
        inv_context = ""
        if state.GRAPH:
            stats = state.GRAPH.get_stats()
            top_entities = sorted(state.GRAPH.entities.items(),
                                  key=lambda x: -len(state.GRAPH.get_connections_for(x[0])))[:8]
            top_names = [e.name for _, e in top_entities]
            inv_context = f"""Current investigation: {state.GRAPH.name}
Entities: {stats.get('total_entities', 0)} | Connections: {stats.get('total_connections', 0)} | Gaps: {stats.get('gaps_found', 0)}
Top entities: {', '.join(top_names)}"""

        # Build recent conversation
        recent = messages[-6:] if len(messages) > 6 else messages
        conv_parts = []
        for msg in recent:
            content = msg['content'] if isinstance(msg['content'], str) else str(msg['content'])
            if msg['role'] == 'user':
                conv_parts.append(f"{user_name}: {content}")
            elif msg['role'] == 'assistant':
                conv_parts.append(f"{agent_name}: {content}")

        prompt = f"""You are {agent_name}, an OSINT investigator for {user_name}. Stay in character. Be concise — 2-4 sentences max. RULES: Never editorialize or defend subjects. Never ask clarifying questions about entities that are already in the investigation — just investigate them. Report facts and connections only. Don't summarize from memory — use the search results provided.

{inv_context}

{chr(10).join(conv_parts)}

{agent_name}:"""

        await websocket.send(json.dumps({
            'type': 'status',
            'message': f'{agent_name} is thinking...'
        }))

        try:
            response = await asyncio.wait_for(
                loop.run_in_executor(None, state.BRIDGE._call, prompt),
                timeout=300
            )
        except asyncio.TimeoutError:
            return f"I took too long on that one. Try a more specific question?"
        except Exception as e:
            return f"Hit a snag: {e}"

        if response and not response.startswith("Error"):
            response = _strip_thinking(response)
            _store_suggestion(websocket, response)
            return response
        return f"I ran into an issue. Could you rephrase?"


async def _detect_and_execute(websocket, user_msg, agent_name, user_name, loop):
    """Detect user intent from message and execute the appropriate server function.
    Returns (context_string, result_data) if action was taken, or None for conversation-only."""

    msg_lower = user_msg.lower()

    # ── Store selected node context when it comes through (GAP 1) ──
    # (Node clicks are handled in app.js which sends the message with the entity name)

    # ── User nudge — "where are the results?" / "didn't you say you'd..." (reminder) ──
    if any(phrase in msg_lower for phrase in ['where are', 'what happened to', "didn't you",
                                               'didnt you', 'you said you', 'you were going to',
                                               'still waiting', 'any results', 'what about the',
                                               'are you done', 'are you still', 'you offered to',
                                               'what about']):
        # Check for forgotten/stalled tasks
        forgotten = TASK_MGR.get_forgotten_task()
        if forgotten:
            # Execute the forgotten task
            await websocket.send(json.dumps({
                'type': 'status',
                'message': f'{agent_name} resuming: {forgotten.description}...'
            }))
            TASK_MGR.start_task(forgotten.id)
            result = await _execute_task_action(websocket, forgotten, agent_name, user_name, loop)
            if result:
                return result

        # Check pending actions too
        if hasattr(websocket, '_pending_action') and websocket._pending_action:
            action = websocket._pending_action
            websocket._pending_action = None
            task = TASK_MGR.create_task(action['type'], action['entity'],
                                        f"{action['type'].replace('_', ' ').title()} {action['entity']}")
            TASK_MGR.start_task(task.id)
            result = await _execute_task_action(websocket, task, agent_name, user_name, loop)
            if result:
                return result

        # No forgotten tasks — let conversational handler respond

    # ── Rejections — clear pending actions (GAP 8) ──
    if any(phrase in msg_lower for phrase in ['no', 'skip', 'next', 'pass', 'nah', 'not now',
                                               'nevermind', 'never mind', 'forget it', 'cancel']):
        if hasattr(websocket, '_pending_action'):
            websocket._pending_action = None
        if hasattr(websocket, '_last_suggestion'):
            websocket._last_suggestion = None
        TASK_MGR.clear_pending()
        return None  # Let conversational handler respond

    # ── Investigate gaps (after user saw the list and chose) ──
    if 'investigate all gaps' in msg_lower or 'investigate top' in msg_lower:
        max_gaps = 3 if 'top 3' in msg_lower else 5
        await websocket.send(json.dumps({
            'type': 'status',
            'message': f'{agent_name} is researching {max_gaps} gaps...'
        }))
        success, researched, found, error = await loop.run_in_executor(
            None, investigation.do_research_gaps, max_gaps)
        if success:
            context = f"Gap research complete: {researched} gaps investigated, {found} new connections found."
            return context, {'researched': researched, 'found': found}
        return f"Gap research failed: {error}", None

    # ── Investigate a specific gap by number or entity names ──
    if 'investigate' in msg_lower and hasattr(websocket, '_shown_gaps') and websocket._shown_gaps:
        import re
        num_match = re.search(r'(\d+)', user_msg)
        selected_gap = None
        if num_match:
            idx = int(num_match.group(1)) - 1
            if 0 <= idx < len(websocket._shown_gaps):
                selected_gap = websocket._shown_gaps[idx]
        if not selected_gap:
            for g in websocket._shown_gaps:
                if g['a_name'].lower() in msg_lower or g['c_name'].lower() in msg_lower:
                    selected_gap = g
                    break
        if selected_gap:
            a_name = selected_gap['a_name']
            c_name = selected_gap['c_name']
            b_name = selected_gap['b_name']
            await websocket.send(json.dumps({
                'type': 'status',
                'message': f'{agent_name} is investigating gap: {a_name} ↔ {c_name}...'
            }))
            context_prompt = f"Search for any connection between {a_name} and {c_name}. They both connect to {b_name}."
            response = await loop.run_in_executor(None, state.BRIDGE._call, context_prompt)
            _store_pending_action(websocket, 'trace_money', a_name)
            if response:
                _store_suggestion(websocket, response)
            context = f"Gap investigation: {a_name} ↔ {c_name} (via {b_name})\n\nFindings:\n{response[:1000] if response else 'No results'}"
            return context, {'gap': f'{a_name} ↔ {c_name}'}

    # ── Relationship between two entities (GAP 14) ──
    if any(phrase in msg_lower for phrase in ['relationship between', 'connection between',
                                               'how are', 'connected to', 'related to',
                                               'link between', 'path between']):
        import re
        # Try to find two entity names
        matches = _find_multiple_matches(user_msg)
        if len(matches) >= 2:
            path = _find_path_between(matches[0], matches[1])
            if path:
                context = f"Connection path between **{matches[0]}** and **{matches[1]}**:\n\n"
                context += "\n".join(f"{i+1}. {step}" for i, step in enumerate(path))
                return context, {'path': path}
            else:
                return f"No direct or indirect connection found between {matches[0]} and {matches[1]}.", None

    # ── Informational questions (GAP 3) ──
    if any(phrase in msg_lower for phrase in ['who is', 'what is', 'tell me about',
                                               'what do you know about', 'info on',
                                               'details on', 'show me info']):
        entity_name = _resolve_entity(user_msg, websocket)
        if entity_name:
            info = _get_entity_info(entity_name)
            if info:
                _store_pending_action(websocket, 'expand', entity_name)
                return info + "\n\nWant me to dive deeper into this?", {'entity': entity_name}

    # ── View navigation (GAP 6) ──
    if any(phrase in msg_lower for phrase in ['show me the timeline', 'open timeline',
                                               'show timeline', 'view timeline']):
        await websocket.send(json.dumps({'type': 'navigate', 'url': '/timeline'}))
        return "Opening the timeline view.", None
    if any(phrase in msg_lower for phrase in ['show me the money', 'money flow',
                                               'show money', 'financial flow']):
        await websocket.send(json.dumps({'type': 'navigate', 'url': '/money-flow'}))
        return "Opening the money flow view.", None
    if any(phrase in msg_lower for phrase in ['show report', 'open report', 'full report']):
        await websocket.send(json.dumps({'type': 'navigate', 'url': '/report-view'}))
        return "Opening the full report.", None

    # ── Remove/undo entity (GAP 10) ──
    if any(phrase in msg_lower for phrase in ['remove ', 'delete ', 'take out ', 'undo ']):
        entity_name = _resolve_entity(user_msg, websocket)
        if entity_name and state.GRAPH:
            entity_id = entity_name.lower().replace(' ', '_')
            if entity_id in state.GRAPH.entities:
                await websocket.send(json.dumps({
                    'type': 'choices',
                    'choices': [
                        {'label': f'Yes, remove {entity_name}', 'action': f'confirm remove {entity_name}'},
                        {'label': 'Cancel', 'action': 'cancel'},
                    ],
                }))
                return f"Remove **{entity_name}** from the graph? This can't be undone.", None

    # ── Confirm removal ──
    if 'confirm remove' in msg_lower:
        entity_name = msg_lower.replace('confirm remove ', '').strip()
        entity_id = entity_name.lower().replace(' ', '_')
        if state.GRAPH and entity_id in state.GRAPH.entities:
            from node_actions import prune_node as _prune
            success, error = _prune(state.GRAPH, entity_id)
            if success:
                state.GRAPH.save(state.INV_PATH)
                investigation._rebuild_board()
                return f"Removed **{entity_name}** from the graph.", None
            return f"Failed to remove: {error}", None

    # ── File path detection (GAP 9) ──
    import re
    path_match = re.search(r'(/(?:home|mnt|tmp|var|opt|usr)/\S+)', user_msg)
    if path_match:
        import os
        fpath = path_match.group(1)
        if os.path.isdir(fpath):
            from server.routes.file_ingest import count_documents
            count, _ = count_documents(fpath)
            _store_pending_action(websocket, 'scan', fpath, {'count': count})
            return f"Found **{count}** documents in `{fpath}`. Want me to process them?", None
        elif os.path.isfile(fpath):
            _store_pending_action(websocket, 'scan', os.path.dirname(fpath))
            return f"I see the file `{fpath}`. Want me to scan that folder?", None

    # ── New investigation from chat (GAP 4) ──
    if any(phrase in msg_lower for phrase in ['new investigation', 'start investigating',
                                               'start a new', 'fresh case', 'new case']):
        entity_name = _extract_entity_from_msg(user_msg)
        if not entity_name:
            return None  # Let conversational handler ask what to investigate
        # Create new investigation
        success, error, url = await loop.run_in_executor(
            None, investigation.create_new_investigation, entity_name)
        if success:
            # Now expand the seed entity
            eid = entity_name.lower().replace(' ', '_')
            success2, found, found_entities, feed_data, error2 = await loop.run_in_executor(
                None, investigation.do_expand, eid, entity_name, 'web', None, True)
            if success2 and found_entities:
                from server.routes.approval import stage_entities
                connections = [(e.get('source_id', eid), e['name'].lower().replace(' ', '_')) for e in found_entities]
                tuples = [(e['name'], e['type'], e['relationship'], e.get('confidence', 0.5)) for e in found_entities]
                batch_id, _ = stage_entities(tuples, connections, f"New investigation: {entity_name}")
                await websocket.send(json.dumps({
                    'type': 'approval_list',
                    'text': f'Started new investigation on **{entity_name}**. Found **{found}** connections:',
                    'items': found_entities, 'batch_id': batch_id,
                }))
                return f"New investigation: {entity_name}. Found {found} entities.", {'new': True}
            return f"Started investigation on **{entity_name}**. No connections found yet — try diving deeper.", None
        return f"Failed to create investigation: {error}", None

    # ── Meta commands — "add to graph", "expand the graph", "use those results" ──
    if any(phrase in msg_lower for phrase in ['add to graph', 'expand the graph', 'add those',
                                               'add these', 'use those results', 'use these results',
                                               'put that in the graph', 'add the results',
                                               'expand with', 'add what you found']):
        # User wants to add previously found data — check for pending approval
        if hasattr(websocket, '_pending_action') and websocket._pending_action:
            action = websocket._pending_action
            websocket._pending_action = None
            task = TASK_MGR.create_task(action['type'], action['entity'],
                                        f"{action['type'].replace('_', ' ').title()} {action['entity']}")
            TASK_MGR.start_task(task.id)
            result = await _execute_task_action(websocket, task, agent_name, user_name, loop)
            if result:
                return result
        # Check for any stalled tasks
        forgotten = TASK_MGR.get_forgotten_task()
        if forgotten:
            TASK_MGR.start_task(forgotten.id)
            result = await _execute_task_action(websocket, forgotten, agent_name, user_name, loop)
            if result:
                return result
        # If there's a selected node, expand it
        entity = _resolve_entity(user_msg, websocket)
        if entity:
            # Redirect to expand intent
            return await _detect_and_execute(websocket, f"investigate {entity}", agent_name, user_name, loop)
        return "I don't have pending results to add. Click a node and ask me to investigate it.", None

    # ── Dive deeper / expand / check ──
    if any(phrase in msg_lower for phrase in ['dive deeper', 'dive into', 'expand on', 'look into',
                                               'investigate', 'check ', 'search for', 'find out',
                                               'dig into', 'research']):
        entity_name = _resolve_entity(user_msg, websocket)

        if entity_name:
            entity_id = entity_name.lower().replace(' ', '_')
            task = TASK_MGR.create_task('expand', entity_name, f'Investigate {entity_name}')
            TASK_MGR.start_task(task.id)
            await websocket.send(json.dumps({
                'type': 'status',
                'message': f'{agent_name} is investigating {entity_name}...'
            }))
            await websocket.send(json.dumps({
                'type': 'task_status',
                'task': task.to_dict(),
            }))

            # Preview only — find entities but don't add to graph yet
            success, found, found_entities, feed_data, error = await loop.run_in_executor(
                None, investigation.do_expand, entity_id, entity_name, 'web', None, True)

            if success and found_entities:
                # Stage entities for approval
                from server.routes.approval import stage_entities
                connections = [(e['source_id'], e['name'].lower().replace(' ', '_')) for e in found_entities]
                entities_tuples = [(e['name'], e['type'], e['relationship'], e.get('confidence', 0.5)) for e in found_entities]
                batch_id, staged = stage_entities(entities_tuples, connections, f"Expansion of {entity_name}")

                # Send approval list to chat — no page reload
                await websocket.send(json.dumps({
                    'type': 'approval_list',
                    'text': f'I found **{found} connections** for **{entity_name}**:',
                    'items': found_entities,
                    'batch_id': batch_id,
                }))

                entity_list = '\n'.join(
                    f"- {e['name']} ({e['type']}) — {e['relationship']}"
                    for e in found_entities
                )
                TASK_MGR.complete_task(task.id, f'{found} entities found')
                context = f"Found {found} entities for {entity_name} (pending your approval):\n{entity_list}"
                return context, {'found': found, 'batch_id': batch_id}
            elif success:
                TASK_MGR.complete_task(task.id, 'No new connections')
                return f"No new connections found for {entity_name}.", None
            else:
                TASK_MGR.fail_task(task.id, error)
                return f"Investigation failed for {entity_name}: {error}", None

    # ── Generate report ──
    if any(phrase in msg_lower for phrase in ['report', 'brief', 'summary', 'write up']):
        entity_name = _resolve_entity(user_msg, websocket)

        if entity_name:
            entity_id = entity_name.lower().replace(' ', '_')
            await websocket.send(json.dumps({
                'type': 'status',
                'message': f'{agent_name} is writing a report on {entity_name}...'
            }))

            success, path, error = await loop.run_in_executor(
                None, investigation.do_generate_report, entity_id, entity_name)

            if success:
                context = f"Report generated for {entity_name} and saved to {path}"
                return context, {'path': path}
            else:
                return f"Report failed: {error}", None

    # ── Gap analysis ──
    if any(phrase in msg_lower for phrase in ['gap', 'missing connection', 'suspicious']):
        if state.GRAPH:
            gaps = state.GRAPH.detect_gaps()
            if gaps:
                top_gaps = [g for g in gaps if not g.get('researched', False)][:10]
                if top_gaps:
                    # Present gaps as choices
                    gap_text = f"I found **{len(gaps)} gaps** in the investigation. Here are the top {len(top_gaps)} most suspicious:\n\n"
                    for i, g in enumerate(top_gaps):
                        gap_text += f"{i+1}. **{g['a_name']}** ↔ **{g['c_name']}** (via {g['b_name']}, suspicion: {g['score']}/10)\n"
                    gap_text += "\nWant me to investigate all of these, or pick a specific one by number?"

                    # Store gaps on websocket so user can reference by number later
                    websocket._shown_gaps = top_gaps

                    choices = [
                        {'label': 'Investigate All', 'action': 'investigate all gaps'},
                        {'label': 'Top 3 Only', 'action': 'investigate top 3 gaps'},
                        {'label': 'Skip', 'action': 'skip gaps'},
                    ]
                    await websocket.send(json.dumps({
                        'type': 'agent_message',
                        'text': gap_text,
                    }))
                    await websocket.send(json.dumps({
                        'type': 'choices',
                        'choices': choices,
                    }))
                    # Store the top gap as pending action in case user says "yes"
                    top_gap = top_gaps[0]
                    _store_pending_action(websocket, 'gap', top_gap['a_name'], {
                        'a_name': top_gap['a_name'],
                        'c_name': top_gap['c_name'],
                        'b_name': top_gap['b_name'],
                    })

                    context = gap_text
                    return context, {'gaps_shown': len(top_gaps)}
                else:
                    return "All gaps have been researched already.", None
            else:
                return "No gaps detected in the current investigation.", None

    # ── Timeline trace ──
    if any(phrase in msg_lower for phrase in ['timeline', 'chronolog', 'history of', 'events']):
        entity_name = _resolve_entity(user_msg, websocket)
        if entity_name:
            await websocket.send(json.dumps({
                'type': 'status',
                'message': f'{agent_name} is tracing timeline for {entity_name}...'
            }))
            result = await loop.run_in_executor(
                None, osint.handle_osint_tool, 'timeline', entity_name)
            if result.get('success'):
                items = result.get('results', [])
                context = f"Timeline trace for {entity_name}: {len(items)} events found."
                if items:
                    context += "\n" + "\n".join(f"- {i['title']}" for i in items[:10])
                return context, result

    # ── Money trace ──
    if any(phrase in msg_lower for phrase in ['money', 'financial', 'funding', 'payment', 'investment']):
        entity_name = _resolve_entity(user_msg, websocket)
        if entity_name:
            await websocket.send(json.dumps({
                'type': 'status',
                'message': f'{agent_name} is tracing money for {entity_name}...'
            }))
            result = await loop.run_in_executor(
                None, osint.handle_osint_tool, 'money', entity_name)
            if result.get('success'):
                items = result.get('results', [])
                context = f"Money trace for {entity_name}: {len(items)} financial connections found."
                if items:
                    context += "\n" + "\n".join(f"- {i['title']}" for i in items[:10])
                return context, result

    # ── List investigations ──
    if any(phrase in msg_lower for phrase in ['list', 'show cases', 'previous', 'my investigations']):
        invs = await loop.run_in_executor(None, investigation.list_investigations)
        inv_list = '\n'.join(
            f"- {i['name']} ({i['entities']} entities, {i['connections']} connections)"
            for i in invs
        )
        context = f"Your investigations ({len(invs)} total):\n{inv_list}"
        return context, {'investigations': invs}

    # ── Switch investigation ──
    if any(phrase in msg_lower for phrase in ['switch to', 'open case', 'load']):
        # Try to find the investigation name in the message
        if state.GRAPH:
            invs = await loop.run_in_executor(None, investigation.list_investigations)
            for inv in invs:
                if inv['name'].lower() in msg_lower:
                    success, error, url = await loop.run_in_executor(
                        None, investigation.switch_investigation, inv['dir'])
                    if success:
                        context = f"Switched to {inv['name']} — {inv['entities']} entities, {inv['connections']} connections."
                        return context, inv

    # ── Investigate gaps (after user saw the list and chose) ──
    if 'investigate all gaps' in msg_lower or 'investigate top' in msg_lower:
        max_gaps = 3 if 'top 3' in msg_lower else 5
        await websocket.send(json.dumps({
            'type': 'status',
            'message': f'{agent_name} is researching {max_gaps} gaps...'
        }))
        success, researched, found, error = await loop.run_in_executor(
            None, investigation.do_research_gaps, max_gaps)
        if success:
            context = f"Gap research complete: {researched} gaps investigated, {found} new connections found."
            return context, {'researched': researched, 'found': found}
        return f"Gap research failed: {error}", None

    # ── Investigate a specific gap by number or entity names ──
    if 'investigate' in msg_lower and hasattr(websocket, '_shown_gaps') and websocket._shown_gaps:
        import re
        # Check for a number reference like "investigate #6" or "6." or "number 6"
        num_match = re.search(r'(\d+)', user_msg)
        selected_gap = None
        if num_match:
            idx = int(num_match.group(1)) - 1  # User sees 1-based
            if 0 <= idx < len(websocket._shown_gaps):
                selected_gap = websocket._shown_gaps[idx]

        # Also try matching entity names from the message
        if not selected_gap:
            for g in websocket._shown_gaps:
                if g['a_name'].lower() in msg_lower or g['c_name'].lower() in msg_lower:
                    selected_gap = g
                    break

        if selected_gap:
            a_name = selected_gap['a_name']
            c_name = selected_gap['c_name']
            b_name = selected_gap['b_name']
            await websocket.send(json.dumps({
                'type': 'status',
                'message': f'{agent_name} is investigating gap: {a_name} ↔ {c_name}...'
            }))
            # Research this specific gap
            context_prompt = f"""INVESTIGATING A GAP in "{state.GRAPH.name}":
{a_name} and {c_name} both connect to {b_name} but have NO direct connection.
Suspicion score: {selected_gap['score']}/10
Search for ANY connection between {a_name} and {c_name}."""

            response = await loop.run_in_executor(
                None, state.BRIDGE._call, context_prompt)

            context = f"Gap investigation: {a_name} ↔ {c_name} (via {b_name})\n\nFindings:\n{response[:1000] if response else 'No results'}"
            # Store follow-up: trace money or expand on the entities
            _store_pending_action(websocket, 'trace_money', a_name)
            if response:
                _store_suggestion(websocket, response)
            return context, {'gap': f'{a_name} ↔ {c_name}'}

    # ── Continue investigation — pick top unexpanded node ──
    if any(phrase in msg_lower for phrase in ['continue the investigation', 'continue investigating',
                                               'keep going', 'keep investigating', 'continue the dive',
                                               'continue this investigation']):
        if state.GRAPH:
            # Find top unexpanded node by connection count
            candidates = [
                (eid, entity, len(state.GRAPH.get_connections_for(eid)))
                for eid, entity in state.GRAPH.entities.items()
                if not entity.investigated
            ]
            if candidates:
                candidates.sort(key=lambda x: -x[2])
                eid, entity, conns = candidates[0]
                await websocket.send(json.dumps({
                    'type': 'status',
                    'message': f'{agent_name} is expanding {entity.name}...'
                }))
                success, found, found_entities, feed_data, error = await loop.run_in_executor(
                    None, investigation.do_expand, eid, entity.name, 'web', None, True)
                if success and found_entities:
                    from server.routes.approval import stage_entities as _stage
                    conns = [(e.get('source_id', eid), e['name'].lower().replace(' ', '_')) for e in found_entities]
                    tuples = [(e['name'], e['type'], e['relationship'], e.get('confidence', 0.5)) for e in found_entities]
                    bid, _ = _stage(tuples, conns, f"Continue: {entity.name}")
                    await websocket.send(json.dumps({
                        'type': 'approval_list',
                        'text': f'Investigating **{entity.name}** — found **{found}** connections:',
                        'items': found_entities, 'batch_id': bid,
                    }))
                    return f"Found {found} entities for {entity.name} (pending approval).", {'found': found, 'batch_id': bid}
                elif success:
                    return f"No new connections found for {entity.name}.", None
                else:
                    return f"Failed: {error}", None
            else:
                return "All entities investigated. Try researching gaps or picking a specific node.", None

    # ── Confirmations (yes/do it/go ahead/trace it/do that) ──
    is_confirmation = (
        msg_lower.strip() in ('yes', 'do it', 'go ahead', 'sure', 'proceed', 'yeah', 'yep',
                               'ok', 'y', 'yes please', 'go for it', 'do that') or
        any(phrase in msg_lower for phrase in ['lets go', "let's go", 'trace it', 'trace that',
                                               'do that', 'check it', 'yes trace', 'yes investigate',
                                               'yes check', 'go ahead'])
    )
    if is_confirmation:
        # Check for a stored pending action first (most reliable)
        if hasattr(websocket, '_pending_action') and websocket._pending_action:
            action = websocket._pending_action
            websocket._pending_action = None
            atype = action['type']
            entity = action['entity']

            if atype == 'expand':
                eid = entity.lower().replace(' ', '_')
                await websocket.send(json.dumps({'type': 'status', 'message': f'{agent_name} is investigating {entity}...'}))
                success, found, found_entities, feed_data, error = await loop.run_in_executor(
                    None, investigation.do_expand, eid, entity, 'web', None, True)
                if success and found_entities:
                    from server.routes.approval import stage_entities as _stg
                    conns = [(e.get('source_id', eid), e['name'].lower().replace(' ', '_')) for e in found_entities]
                    tuples = [(e['name'], e['type'], e['relationship'], e.get('confidence', 0.5)) for e in found_entities]
                    bid, _ = _stg(tuples, conns, f"Investigate: {entity}")
                    await websocket.send(json.dumps({'type': 'approval_list', 'text': f'Found **{found}** connections for **{entity}**:', 'items': found_entities, 'batch_id': bid}))
                    return f"Found {found} entities for {entity}.", {'found': found}
                return f"No new connections found for {entity}.", None

            elif atype == 'trace_money':
                await websocket.send(json.dumps({'type': 'status', 'message': f'{agent_name} is tracing money for {entity}...'}))
                result = await loop.run_in_executor(None, osint.handle_osint_tool, 'money', entity)
                if result.get('results'):
                    items = result['results']
                    context = f"Money trace for {entity}: {len(items)} financial connections found.\n"
                    context += "\n".join(f"- {i['title']}" for i in items[:10])
                    return context, result
                return f"No financial connections found for {entity}.", None

            elif atype == 'trace_timeline':
                await websocket.send(json.dumps({'type': 'status', 'message': f'{agent_name} is tracing timeline for {entity}...'}))
                result = await loop.run_in_executor(None, osint.handle_osint_tool, 'timeline', entity)
                if result.get('results'):
                    items = result['results']
                    context = f"Timeline for {entity}: {len(items)} events found.\n"
                    context += "\n".join(f"- {i['title']}" for i in items[:10])
                    return context, result
                return f"No timeline events found for {entity}.", None

            elif atype == 'report':
                eid = entity.lower().replace(' ', '_')
                await websocket.send(json.dumps({'type': 'status', 'message': f'{agent_name} is generating report on {entity}...'}))
                success, path, error = await loop.run_in_executor(None, investigation.do_generate_report, eid, entity)
                if success:
                    return f"Report generated for {entity} — saved to {path}", {'path': path}
                return f"Report failed: {error}", None

            elif atype == 'gap':
                gap_data = action.get('extra', {})
                a_name = gap_data.get('a_name', entity)
                c_name = gap_data.get('c_name', '')
                b_name = gap_data.get('b_name', '')
                await websocket.send(json.dumps({'type': 'status', 'message': f'{agent_name} is investigating gap: {a_name} ↔ {c_name}...'}))
                prompt = f"Search for any connection between {a_name} and {c_name}. They both connect to {b_name}."
                response = await loop.run_in_executor(None, state.BRIDGE._call, prompt)
                return f"Gap investigation: {a_name} ↔ {c_name}\n\n{response[:1000] if response else 'No results'}", None

        # Fall back to text-based suggestion
        if hasattr(websocket, '_last_suggestion') and websocket._last_suggestion:
            suggestion = websocket._last_suggestion
            target = getattr(websocket, '_last_suggestion_entity', None) or suggestion
            websocket._last_suggestion = None
            websocket._last_suggestion_entity = None

            # Try to match against a graph entity first
            entity_name = _resolve_entity(suggestion, websocket)
            if entity_name:
                return await _detect_and_execute(websocket, f"investigate {entity_name}", agent_name, user_name, loop)

            # No graph entity match — do a free-form research call on the topic/target
            # This handles cases like "check property records in Florida for Zelníčková"
            await websocket.send(json.dumps({'type': 'status',
                'message': f'{agent_name} is researching: {target[:60]}...'}))

            # Build a research prompt using the conversation context
            recent_conv = []
            hist = getattr(websocket, '_chat_history', [])
            for m in hist[-6:]:
                content = m['content'] if isinstance(m['content'], str) else str(m['content'])
                role = user_name if m['role'] == 'user' else agent_name
                recent_conv.append(f"{role}: {content}")

            inv_context = f"Investigation: {state.GRAPH.name}" if state.GRAPH else ""
            research_prompt = f"""You are {agent_name}, an OSINT investigator. {inv_context}

Recent conversation:
{chr(10).join(recent_conv)}

The user confirmed: do what you offered. Execute this research task: {suggestion}

Search for specific facts, names, records, and connections. Report findings as bullet points. Then suggest the single most important next step."""

            try:
                response = await asyncio.wait_for(
                    loop.run_in_executor(None, state.BRIDGE._call, research_prompt),
                    timeout=300
                )
                if response and not response.startswith("Error"):
                    response = _strip_thinking(response)
                    _store_suggestion(websocket, response)
                    return response, None
            except Exception:
                pass
            return f"Researching: {suggestion}", None

        # Fall back to model's last suggested action (survives approval flow)
        if hasattr(websocket, '_model_suggested_action') and websocket._model_suggested_action:
            action = websocket._model_suggested_action
            websocket._model_suggested_action = None
            websocket._pending_action = action
            return await _detect_and_execute(websocket, f"investigate {action['entity']}", agent_name, user_name, loop)

        # Fall back to the last entity discussed — if user says "yes" we expand it
        if hasattr(websocket, '_last_discussed_entity') and websocket._last_discussed_entity:
            entity = websocket._last_discussed_entity
            return await _detect_and_execute(websocket, f"investigate {entity}", agent_name, user_name, loop)

        # Fall back to selected node
        if hasattr(websocket, '_selected_node') and websocket._selected_node:
            return await _detect_and_execute(websocket, f"investigate {websocket._selected_node}", agent_name, user_name, loop)

        # No pending suggestion but said "continue" — continue the investigation
        if 'continue' in msg_lower and state.GRAPH:
            candidates = [
                (eid, entity, len(state.GRAPH.get_connections_for(eid)))
                for eid, entity in state.GRAPH.entities.items()
                if not entity.investigated
            ]
            if candidates:
                candidates.sort(key=lambda x: -x[2])
                eid, entity, conns = candidates[0]
                await websocket.send(json.dumps({
                    'type': 'status',
                    'message': f'{agent_name} is expanding {entity.name}...'
                }))
                success, found, found_entities, feed_data, error = await loop.run_in_executor(
                    None, investigation.do_expand, eid, entity.name, 'web', None, True)
                if success and found_entities:
                    from server.routes.approval import stage_entities as _stage2
                    conns2 = [(e.get('source_id', eid), e['name'].lower().replace(' ', '_')) for e in found_entities]
                    tuples2 = [(e['name'], e['type'], e['relationship'], e.get('confidence', 0.5)) for e in found_entities]
                    bid2, _ = _stage2(tuples2, conns2, f"Continue: {entity.name}")
                    await websocket.send(json.dumps({
                        'type': 'approval_list',
                        'text': f'Investigating **{entity.name}** — found **{found}** connections:',
                        'items': found_entities, 'batch_id': bid2,
                    }))
                    return f"Found {found} entities for {entity.name} (pending approval).", {'found': found}

    # ── Rejections ──
    if any(phrase in msg_lower for phrase in ['no', 'skip', 'next', 'pass', 'nah', 'not now']):
        return None  # Let the conversational handler respond

    # No action detected — return None for conversational response
    return None


async def _execute_task_action(websocket, task, agent_name, user_name, loop):
    """Execute a task from the task manager. Used for stalled/forgotten tasks."""
    atype = task.action_type
    entity = task.entity

    if atype == 'expand':
        entity_id = entity.lower().replace(' ', '_')
        await websocket.send(json.dumps({
            'type': 'status',
            'message': f'{agent_name} is now executing: {task.description}...'
        }))
        success, found, found_entities, feed_data, error = await loop.run_in_executor(
            None, investigation.do_expand, entity_id, entity, 'web', None, True)
        if success and found_entities:
            from server.routes.approval import stage_entities
            connections = [(e.get('source_id', entity_id), e['name'].lower().replace(' ', '_')) for e in found_entities]
            tuples = [(e['name'], e['type'], e['relationship'], e.get('confidence', 0.5)) for e in found_entities]
            batch_id, _ = stage_entities(tuples, connections, f"Resumed: {entity}")
            await websocket.send(json.dumps({
                'type': 'approval_list',
                'text': f'Completed **{task.description}** — found **{found}** connections:',
                'items': found_entities, 'batch_id': batch_id,
            }))
            TASK_MGR.complete_task(task.id, f'{found} entities found')
            return f"Completed: {task.description}. Found {found} entities.", {'found': found}
        TASK_MGR.complete_task(task.id, 'No results')
        return f"Completed {task.description} but found no new connections.", None

    elif atype == 'trace_money':
        await websocket.send(json.dumps({
            'type': 'status',
            'message': f'{agent_name} is tracing money for {entity}...'
        }))
        result = await loop.run_in_executor(None, osint.handle_osint_tool, 'money', entity)
        TASK_MGR.complete_task(task.id, result.get('message', ''))
        if result.get('results'):
            items = result['results']
            context = f"Money trace for {entity}: {len(items)} financial connections.\n"
            context += "\n".join(f"- {i['title']}" for i in items[:10])
            return context, result
        return f"No financial connections found for {entity}.", None

    elif atype == 'trace_timeline':
        await websocket.send(json.dumps({
            'type': 'status',
            'message': f'{agent_name} is tracing timeline for {entity}...'
        }))
        result = await loop.run_in_executor(None, osint.handle_osint_tool, 'timeline', entity)
        TASK_MGR.complete_task(task.id, result.get('message', ''))
        if result.get('results'):
            items = result['results']
            context = f"Timeline for {entity}: {len(items)} events.\n"
            context += "\n".join(f"- {i['title']}" for i in items[:10])
            return context, result
        return f"No timeline events found for {entity}.", None

    elif atype == 'report':
        entity_id = entity.lower().replace(' ', '_')
        await websocket.send(json.dumps({
            'type': 'status',
            'message': f'{agent_name} is generating report on {entity}...'
        }))
        success, path, error = await loop.run_in_executor(None, investigation.do_generate_report, entity_id, entity)
        if success:
            TASK_MGR.complete_task(task.id, f'Report saved: {path}')
            return f"Report generated for {entity} — saved to {path}", {'path': path}
        TASK_MGR.fail_task(task.id, error)
        return f"Report failed: {error}", None

    elif atype == 'gap':
        extra = task.extra or {}
        a_name = extra.get('a_name', entity)
        c_name = extra.get('c_name', '')
        b_name = extra.get('b_name', '')
        await websocket.send(json.dumps({
            'type': 'status',
            'message': f'{agent_name} is investigating gap: {a_name} ↔ {c_name}...'
        }))
        prompt = f"Search for any connection between {a_name} and {c_name}. They both connect to {b_name}."
        response = await loop.run_in_executor(None, state.BRIDGE._call, prompt)
        TASK_MGR.complete_task(task.id, 'Gap investigated')
        return f"Gap investigation: {a_name} ↔ {c_name}\n\n{response[:1000] if response else 'No results'}", None

    TASK_MGR.fail_task(task.id, f'Unknown action type: {atype}')
    return None


def _store_suggestion(websocket, response):
    """Extract the investigator's suggested next action from its response.
    Stores both a text version (for re-parsing) and tries to identify
    the specific entity to act on."""
    import re
    response_lower = response.lower()

    # Look for patterns and extract the entity/target
    patterns = [
        r'(?:want me to|should I|shall I|I should|let me) (?:trace|investigate|check|look into|dive into|expand|search|research) (?:the )?(?:connection (?:between|to) )?(.+?)[\?\.]',
        r'(?:trace|investigate|check|look into|dive into|expand) (.+?)[\?\.]',
    ]

    for pat in patterns:
        match = re.search(pat, response_lower)
        if match:
            target = match.group(1).strip().rstrip('?').rstrip('.')
            # Clean up common filler
            target = re.sub(r'^(?:the |a |this |that )', '', target)

            # Determine action type from the verb used
            full_match = match.group(0).lower()
            if 'trace' in full_match and ('money' in full_match or 'financial' in full_match or 'connection' in full_match):
                action = f"trace money for {target}"
            elif 'trace' in full_match:
                action = f"trace money for {target}"
            elif 'gap' in full_match or 'connection between' in full_match:
                action = f"investigate gap {target}"
            else:
                action = f"investigate {target}"

            websocket._last_suggestion = action
            websocket._last_suggestion_entity = target
            websocket._last_discussed_entity = target
            return

    websocket._last_suggestion = None
    websocket._last_suggestion_entity = None


def _store_pending_action(websocket, action_type, entity_name, extra=None):
    """Store a specific pending action that 'yes' will trigger.
    Also creates a task in the task manager so stalls can be detected."""
    websocket._pending_action = {
        'type': action_type,
        'entity': entity_name,
        'extra': extra or {},
    }
    websocket._model_suggested_action = websocket._pending_action.copy()
    websocket._last_discussed_entity = entity_name
    # Create a task so the task manager can track if it gets executed
    desc = f"{action_type.replace('_', ' ').title()} {entity_name}"
    TASK_MGR.create_task(action_type, entity_name, desc, extra)


def _extract_entity_from_msg(msg):
    """Try to extract an entity name from a user message.
    Looks for quoted strings, text after key phrases, then tries graph matching."""
    import re

    # Check for quoted entity
    quoted = re.findall(r'"([^"]+)"', msg)
    if quoted:
        return quoted[0]

    # Check for text after action phrases
    for phrase in ['dive deeper into ', 'dive into ', 'look into ',
                   'investigate ', 'expand on ', 'expand ',
                   'report on ', 'timeline for ', 'money for ',
                   'financial connections for ', 'trace money for ',
                   'trace timeline for ', 'trace ', 'check ',
                   'search for ', 'find ', 'about ']:
        idx = msg.lower().find(phrase)
        if idx >= 0:
            rest = msg[idx + len(phrase):].strip()
            rest = re.split(r'[,\.\?!]', rest)[0].strip()
            # Remove filler words
            rest = re.sub(r'^(?:the |a |an |this |that |any |some |all )', '', rest, flags=re.I)
            if rest and len(rest) > 1:
                # Try to match against graph first (fixes GAP 2 — "corruption at Apple" → "Apple")
                graph_match = _match_entity_in_graph(rest)
                if graph_match:
                    return graph_match
                return rest

    return None


def _resolve_entity(msg, websocket=None):
    """Resolve an entity name from message, with fallback to selected node.
    Fixes GAP 1 — handles 'this', 'this entity', 'that node' etc."""

    # First try extracting from the message text
    entity = _extract_entity_from_msg(msg)
    if entity:
        return entity

    # Try matching any graph entity mentioned in the message
    entity = _match_entity_in_graph(msg)
    if entity:
        return entity

    # Fall back to the currently selected node (GAP 1)
    if websocket and hasattr(websocket, '_selected_node') and websocket._selected_node:
        return websocket._selected_node

    return None


def _match_entity_in_graph(msg):
    """Try to match an entity name from the current graph against the message.
    Returns the longest matching entity name found."""
    if not state.GRAPH:
        return None

    msg_lower = msg.lower()
    best_match = None
    best_len = 0

    for eid, entity in state.GRAPH.entities.items():
        name_lower = entity.name.lower()
        if name_lower in msg_lower and len(name_lower) > best_len:
            best_match = entity.name
            best_len = len(name_lower)

    return best_match


def _find_multiple_matches(msg):
    """Find all entities in the graph that match part of the message.
    Used for disambiguation (GAP 5)."""
    if not state.GRAPH:
        return []

    msg_lower = msg.lower()
    matches = []
    for eid, entity in state.GRAPH.entities.items():
        name_lower = entity.name.lower()
        if name_lower in msg_lower:
            matches.append(entity.name)
        # Also check if the search term is in the entity name
        # e.g., user says "Adams" and graph has "Katherine Adams" and "Kate Adams"
        words = [w for w in msg_lower.split() if len(w) > 2]
        for word in words:
            if word in name_lower and entity.name not in matches:
                matches.append(entity.name)

    return matches


def _strip_thinking(text):
    """Strip thinking/reasoning tags from model output (GAP 11)."""
    import re
    # Remove <thinking>...</thinking> blocks
    text = re.sub(r'<thinking>.*?</thinking>', '', text, flags=re.DOTALL)
    # Remove "Thinking..." or "Here's my thinking:" preambles
    text = re.sub(r'^(?:Thinking\.\.\.?\n|Here\'s (?:my )?(?:thinking|reasoning)[:\n].*?\n\n)', '', text, flags=re.DOTALL)
    # Remove leading/trailing whitespace
    return text.strip()


def _get_entity_info(entity_name):
    """Get graph info about an entity for informational questions (GAP 3)."""
    if not state.GRAPH:
        return None

    entity_id = entity_name.lower().replace(' ', '_')
    entity = state.GRAPH.entities.get(entity_id)
    if not entity:
        # Try fuzzy match
        for eid, e in state.GRAPH.entities.items():
            if e.name.lower() == entity_name.lower():
                entity = e
                entity_id = eid
                break
    if not entity:
        return None

    conns = state.GRAPH.get_connections_for(entity_id)
    connected = []
    for conn in conns[:15]:
        other_id = conn.target_id if conn.source_id == entity_id else conn.source_id
        other = state.GRAPH.entities.get(other_id)
        if other:
            connected.append(f"**{other.name}** ({other.type}) — {conn.relationship.replace('_', ' ')}")

    info = f"**{entity.name}** ({entity.type})\n"
    info += f"Depth: {entity.depth} | Connections: {len(conns)} | Investigated: {'Yes' if entity.investigated else 'No'}\n"
    if entity.metadata:
        meta = {k: v for k, v in entity.metadata.items() if k not in ('pinned', 'notes', 'config', 'source')}
        if meta:
            info += f"Details: {', '.join(f'{k}: {v}' for k, v in meta.items())}\n"
    if connected:
        info += f"\nConnections:\n" + "\n".join(f"- {c}" for c in connected)
    if entity.metadata.get('notes'):
        info += f"\n\nNotes: " + ", ".join(entity.metadata['notes'])

    return info


def _find_path_between(entity_a, entity_b):
    """Find connection path between two entities (GAP 14)."""
    if not state.GRAPH:
        return None

    id_a = entity_a.lower().replace(' ', '_')
    id_b = entity_b.lower().replace(' ', '_')

    if id_a not in state.GRAPH.entities or id_b not in state.GRAPH.entities:
        return None

    # BFS to find shortest path
    from collections import deque
    visited = {id_a}
    queue = deque([(id_a, [id_a])])

    while queue:
        current, path = queue.popleft()
        if current == id_b:
            # Build readable path
            result = []
            for i in range(len(path) - 1):
                e1 = state.GRAPH.entities.get(path[i])
                e2 = state.GRAPH.entities.get(path[i + 1])
                # Find the connection between them
                for conn in state.GRAPH.connections:
                    if (conn.source_id == path[i] and conn.target_id == path[i + 1]) or \
                       (conn.source_id == path[i + 1] and conn.target_id == path[i]):
                        result.append(f"**{e1.name if e1 else path[i]}** —({conn.relationship.replace('_', ' ')})→ **{e2.name if e2 else path[i+1]}**")
                        break
            return result

        for conn in state.GRAPH.get_connections_for(current):
            next_id = conn.target_id if conn.source_id == current else conn.source_id
            if next_id not in visited:
                visited.add(next_id)
                queue.append((next_id, path + [next_id]))
            if len(visited) > 500:  # Safety limit
                break

    return None


async def _execute_tool(tool_name, tool_input):
    """Execute a tool call and return the result."""

    loop = asyncio.get_event_loop()

    if tool_name == 'new_investigation':
        name = tool_input.get('name', '')
        success, error, url = await loop.run_in_executor(
            None, investigation.create_new_investigation, name)
        return {'success': success, 'error': error}

    elif tool_name == 'list_investigations':
        invs = await loop.run_in_executor(None, investigation.list_investigations)
        return {'investigations': invs}

    elif tool_name == 'switch_investigation':
        dir_path = tool_input.get('dir', '')
        success, error, url = await loop.run_in_executor(
            None, investigation.switch_investigation, dir_path)
        return {'success': success, 'error': error}

    elif tool_name == 'expand_entity':
        eid = tool_input.get('entity_id', '')
        ename = tool_input.get('entity_name', '')
        mode = tool_input.get('search_mode', 'web')
        feeds = tool_input.get('enabled_feeds', None)
        success, added, added_entities, feed_data, error = await loop.run_in_executor(
            None, investigation.do_expand, eid, ename, mode, feeds)
        # Note: do_expand currently auto-adds. In future, stage entities for approval.
        # For now, return what was added so the AI can report it.
        return {
            'success': success, 'added': added, 'error': error,
            'added_entities': added_entities or [],
            'feed_data': feed_data or {},
        }

    elif tool_name == 'approve_entities':
        from server.routes.approval import approve_entities
        batch_id = tool_input.get('batch_id', '')
        indices = tool_input.get('approved_indices', None)
        added, skipped, error = await loop.run_in_executor(
            None, approve_entities, batch_id, indices)
        return {'success': error is None, 'added': added, 'skipped': skipped, 'error': error}

    elif tool_name == 'reject_batch':
        from server.routes.approval import reject_batch
        batch_id = tool_input.get('batch_id', '')
        success = await loop.run_in_executor(None, reject_batch, batch_id)
        return {'success': success}

    elif tool_name == 'generate_report':
        eid = tool_input.get('entity_id', '')
        ename = tool_input.get('entity_name', '')
        success, path, error = await loop.run_in_executor(
            None, investigation.do_generate_report, eid, ename)
        return {'success': success, 'path': path, 'error': error}

    elif tool_name == 'pin_node':
        from node_actions import pin_node as _pin
        eid = tool_input.get('entity_id', '')
        if state.GRAPH:
            success, pinned = _pin(state.GRAPH, eid)
            return {'success': success, 'pinned': pinned}
        return {'success': False, 'error': 'No investigation loaded'}

    elif tool_name == 'add_note':
        from node_actions import add_note as _note
        eid = tool_input.get('entity_id', '')
        note = tool_input.get('note', '')
        if state.GRAPH:
            success, count = _note(state.GRAPH, eid, note)
            return {'success': success, 'note_count': count}
        return {'success': False, 'error': 'No investigation loaded'}

    elif tool_name == 'prune_node':
        from node_actions import prune_node as _prune
        eid = tool_input.get('entity_id', '')
        if state.GRAPH:
            success, error = _prune(state.GRAPH, eid)
            if success:
                state.GRAPH.save(state.INV_PATH)
                investigation._rebuild_board()
            return {'success': success, 'error': error}
        return {'success': False, 'error': 'No investigation loaded'}

    elif tool_name == 'query_feed':
        feed = tool_input.get('feed_name', '')
        entity = tool_input.get('entity', '')
        result = await loop.run_in_executor(None, osint.handle_osint_tool, feed, entity)
        return result

    elif tool_name == 'query_all_feeds':
        entity = tool_input.get('entity', '')
        result = await loop.run_in_executor(None, osint.handle_osint_tool, 'feeds', entity)
        return result

    elif tool_name == 'trace_timeline':
        entity = tool_input.get('entity', '')
        result = await loop.run_in_executor(None, osint.handle_osint_tool, 'timeline', entity)
        return result

    elif tool_name == 'trace_money':
        entity = tool_input.get('entity', '')
        result = await loop.run_in_executor(None, osint.handle_osint_tool, 'money', entity)
        return result

    elif tool_name == 'scan_social_media':
        entity = tool_input.get('entity', '')
        result = await loop.run_in_executor(None, osint.handle_osint_tool, 'social', entity)
        return result

    elif tool_name == 'check_wayback':
        entity = tool_input.get('entity', '')
        result = await loop.run_in_executor(None, osint.handle_osint_tool, 'wayback', entity)
        return result

    elif tool_name == 'list_gaps':
        if state.GRAPH:
            gaps = state.GRAPH.detect_gaps()
            return {'gaps': gaps[:20]}
        return {'gaps': []}

    elif tool_name == 'research_gaps':
        max_gaps = tool_input.get('max_gaps', 5)
        success, researched, found, error = await loop.run_in_executor(
            None, investigation.do_research_gaps, max_gaps)
        return {'success': success, 'gaps_researched': researched, 'connections_found': found, 'error': error}

    elif tool_name == 'show_view':
        view = tool_input.get('view', 'graph')
        view_urls = {
            'graph': '/board',
            'timeline': '/timeline',
            'money_flow': '/money-flow',
            'report': '/report-view',
            'settings': '/settings',
        }
        return {'action': 'navigate', 'url': view_urls.get(view, '/board')}

    elif tool_name == 'count_documents':
        from server.routes.file_ingest import count_documents
        folder = tool_input.get('folder_path', '')
        count, error = await loop.run_in_executor(None, count_documents, folder)
        return {'count': count, 'error': error}

    elif tool_name == 'process_document_batch':
        from server.routes.file_ingest import count_documents, process_batch
        from file_memory import register_folder
        folder = tool_input.get('folder_path', '')
        batch_idx = tool_input.get('batch_index', 0)
        result = await loop.run_in_executor(None, process_batch, folder, batch_idx)
        # Register in file memory on first batch
        if batch_idx == 0 and result.get('success'):
            inv_name = state.GRAPH.name if state.GRAPH else ''
            register_folder(folder, doc_count=result.get('total_docs', 0), investigation=inv_name)
        return result

    elif tool_name == 'scan_dataset':
        from file_memory import register_folder
        folder = tool_input.get('folder_path', '')
        success, files, added, error = await loop.run_in_executor(
            None, investigation.do_scan_dataset, folder)
        if success:
            inv_name = state.GRAPH.name if state.GRAPH else ''
            register_folder(folder, doc_count=files, investigation=inv_name)
        return {'success': success, 'files_indexed': files, 'entities_added': added, 'error': error}

    elif tool_name == 'read_file':
        file_path = tool_input.get('file_path', '')
        if not os.path.isfile(file_path):
            return {'success': False, 'error': f'File not found: {file_path}'}
        try:
            with open(file_path, 'r', errors='ignore') as f:
                content = f.read(15000)
            fname = os.path.basename(file_path)
            prompt = f"""Analyze this file: {fname}

FILE CONTENTS:
{content}

Investigation context: {state.GRAPH.name if state.GRAPH else 'none'}

Extract ALL people, companies, locations, events, and money connections.
Output each as: ENTITY_NAME | ENTITY_TYPE | RELATIONSHIP | CONFIDENCE (high/medium/low)"""
            inv_name = state.GRAPH.name if state.GRAPH else 'unknown'
            response, _ = await loop.run_in_executor(
                None, state.BRIDGE.research, inv_name, 'file_analysis', prompt)
            from extractors import extract_entities
            extracted = extract_entities(response or '')
            # Register in file memory
            from file_memory import register_file
            register_file(file_path, investigation=inv_name)
            return {
                'success': True,
                'file': fname,
                'entities_found': len(extracted),
                'entities': [{'name': n, 'type': t, 'relationship': r, 'confidence': c}
                             for n, t, r, c in extracted],
                'raw_response': response,
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}

    elif tool_name == 'list_file_memory':
        from file_memory import get_all
        data = get_all()
        return {
            'corpora': data.get('corpora', []),
            'individual_files': data.get('individual_files', []),
            'total_corpora': len(data.get('corpora', [])),
            'total_files': len(data.get('individual_files', [])),
        }

    elif tool_name == 'forget_corpus':
        from file_memory import remove_corpus
        folder = tool_input.get('folder_path', '')
        remove_corpus(folder)
        return {'success': True, 'message': f'Removed {folder} from memory'}

    elif tool_name == 'check_past_investigations':
        entity_name = tool_input.get('entity_name', '')
        entity_type = tool_input.get('entity_type', 'unknown')
        inv_dir = state.get_investigations_dir()
        current = state.GRAPH.name if state.GRAPH else None
        from cross_linker import find_new_crosslinks_for_entity
        matches = await loop.run_in_executor(
            None, find_new_crosslinks_for_entity,
            entity_name, entity_type, inv_dir, current)
        return {
            'entity': entity_name,
            'matches': matches,
            'found': len(matches),
            'message': f'Found {len(matches)} matches for "{entity_name}" in past investigations' if matches
                       else f'"{entity_name}" has not appeared in any past investigations',
        }

    elif tool_name == 'scan_all_crosslinks':
        inv_dir = state.get_investigations_dir()
        current = state.GRAPH.name if state.GRAPH else None
        from cross_linker import find_cross_links
        result = await loop.run_in_executor(None, find_cross_links, inv_dir, current)
        return result

    elif tool_name == 'export_investigation':
        fmt = tool_input.get('format', 'json')
        if fmt == 'json':
            if state.GRAPH:
                return {
                    'format': 'json',
                    'name': state.GRAPH.name,
                    'entities': len(state.GRAPH.entities),
                    'connections': len(state.GRAPH.connections),
                    'message': 'Export ready — the client will download the JSON file.',
                }
            return {'error': 'No investigation loaded'}
        elif fmt == 'markdown':
            return {'format': 'markdown', 'message': 'Export ready — markdown file will be generated.'}
        elif fmt == 'html_report':
            return {'format': 'html_report', 'message': 'Report will open in a new tab.'}
        return {'error': f'Unknown format: {fmt}'}

    else:
        return {'error': f'Unknown tool: {tool_name}'}
