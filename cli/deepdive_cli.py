#!/usr/bin/env python3
"""
DeepDive CLI — Model-Agnostic Investigation Tool
Usage: python deepdive_cli.py "Anthropic" --model ollama:qwen3
       python deepdive_cli.py "Elon Musk" --model openai:gpt-4
       python deepdive_cli.py "Epstein" --model ollama:qwen3 --docs /path/to/epstein_files
       python deepdive_cli.py --load investigations/anthropic/
"""

import sys
import os
import argparse
import json

# Add core to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'core'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from graph import InvestigationGraph, Entity, Connection
from extractors import extract_entities
from build_board import build_board as _build_board

def generate_board_3d(graph, path, title):
    """CLI always uses server mode for the board."""
    return _build_board(graph, path, title, mode="server")


def get_provider(model_str):
    """Parse model string and return provider instance."""
    if ':' in model_str:
        backend, model = model_str.split(':', 1)
    else:
        backend = 'ollama'
        model = model_str

    backend = backend.lower()

    if backend == 'ollama':
        from providers.ollama import OllamaProvider
        return OllamaProvider(model=model)
    elif backend in ('openai', 'lmstudio', 'vllm', 'together', 'groq'):
        from providers.openai_compat import OpenAICompatProvider
        base_urls = {
            'openai': 'https://api.openai.com/v1',
            'lmstudio': 'http://localhost:1234/v1',
            'vllm': 'http://localhost:8000/v1',
            'together': 'https://api.together.xyz/v1',
            'groq': 'https://api.groq.com/openai/v1',
        }
        api_key = os.environ.get('OPENAI_API_KEY', os.environ.get('API_KEY', ''))
        return OpenAICompatProvider(model=model, base_url=base_urls.get(backend, base_urls['openai']), api_key=api_key)
    else:
        print(f"Unknown backend: {backend}")
        print("Supported: ollama, openai, lmstudio, vllm, together, groq")
        sys.exit(1)


def get_search_engines(search_pref=None, docs_dir=None):
    """Initialize search engines. Returns list of available engines."""
    engines = []

    # Online search (DDG or SearXNG)
    try:
        from search.engine import get_search_engine
        engine = get_search_engine(prefer=search_pref)
        if engine:
            engines.append(engine)
            print(f"   🔍 Online search: {engine.name}")
    except Exception as e:
        print(f"   ⚠️  No online search: {e}")

    # Local file search
    if docs_dir:
        from search.local_files import LocalFileSearch
        local = LocalFileSearch(docs_dir)
        if local.index():
            engines.append(local)
            print(f"   📁 Local search: {local.name}")

    return engines


def search_entity(entity_name, entity_type, engines):
    """Run multi-angle search across all engines. Returns combined text."""
    if not engines:
        return "", {}

    all_results = {}
    all_text_parts = []

    for engine in engines:
        print(f"   🔍 Searching {engine.name}...")
        try:
            results, text = engine.deep_search(entity_name)
            all_results[engine.name] = results
            if text:
                all_text_parts.append(text)
        except Exception as e:
            print(f"   ⚠️  {engine.name} error: {e}")

    combined_text = "\n".join(all_text_parts)
    return combined_text, all_results


def expand_node(graph, entity_id, provider, engines=None):
    """Expand a node: search for info, then have the model analyze it."""
    entity = graph.entities.get(entity_id)
    if not entity:
        print(f"Entity '{entity_id}' not found.")
        return 0

    if entity.investigated:
        print(f"'{entity.name}' already investigated.")
        return 0

    # Build context from existing connections
    existing_conns = graph.get_connections_for(entity_id)
    context_parts = []
    for conn in existing_conns:
        other_id = conn.target_id if conn.source_id == entity_id else conn.source_id
        other = graph.entities.get(other_id)
        if other:
            context_parts.append(f"{other.name} ({conn.relationship})")
    known_context = "Already known connections: " + ", ".join(context_parts) if context_parts else ""

    print(f"\n🔍 Researching: {entity.name} ({entity.type})...")

    # STEP 1: Search — gather raw info from all search engines
    search_context = ""
    if engines:
        print(f"   Searching {len(engines)} engine(s)...")
        search_text, search_results = search_entity(entity.name, entity.type, engines)
        if search_text:
            # Truncate to avoid blowing up model context
            search_context = search_text[:8000]
            result_count = sum(
                sum(len(hits) for hits in angle_results.values())
                for angle_results in search_results.values()
            )
            print(f"   📰 Got {result_count} search results across all engines")

    # STEP 2: Model — analyze search results + generate connections
    print(f"   🤖 Analyzing with {provider.name}...")

    # Build enriched context: search results + known connections
    full_context = ""
    if search_context:
        full_context += "SEARCH RESULTS (from web/local files):\n" + search_context + "\n\n"
    if known_context:
        full_context += known_context

    response = provider.research(entity.name, entity.type, full_context)

    if not response or response.startswith("Error"):
        print(f"   ❌ {response}")
        return 0

    # STEP 3: Extract entities from model response
    extracted = extract_entities(response)
    print(f"   📊 Extracted {len(extracted)} entities")

    # STEP 4: Add to graph (skip self-references)
    new_count = 0
    for name, etype, rel, conf in extracted:
        new_entity = Entity(name, etype)
        # Skip if this is the same entity we're expanding
        if new_entity.id == entity_id:
            continue
        new_entity.depth = entity.depth + 1
        new_entity.sources.append(f"Researched from {entity.name}")

        is_new = graph.add_entity(new_entity)
        if is_new:
            new_count += 1
            graph.search_queue.append(new_entity.id)

        graph.add_connection(Connection(entity_id, new_entity.id, rel, conf))

    graph.mark_investigated(entity_id)
    print(f"   ✅ Added {new_count} new entities, {len(extracted)} connections")
    return new_count


def print_graph_status(graph):
    """Print current investigation status."""
    stats = graph.get_stats()
    print(f"\n{'='*50}")
    print(f"📊 {graph.name}")
    print(f"   Entities: {stats['total_entities']}")
    print(f"   Connections: {stats['total_connections']}")
    print(f"   Investigated: {stats['investigated']}")
    print(f"   Pending: {stats['pending']}")
    print(f"   Depth: {stats['depth_max']}")
    print(f"{'='*50}")


def interactive_mode(graph, provider, engines, investigation_dir):
    """Interactive mode — user selects nodes to expand."""
    while True:
        print_graph_status(graph)

        # Show uninvestigated entities
        pending = [(eid, e) for eid, e in graph.entities.items() if not e.investigated]
        pending.sort(key=lambda x: (x[1].depth, -len(graph.get_connections_for(x[0]))))

        if not pending:
            print("\n✅ All entities investigated!")
            break

        print(f"\n📋 Pending entities (select to expand):")
        for i, (eid, e) in enumerate(pending[:20]):
            conns = len(graph.get_connections_for(eid))
            print(f"  {i+1:>3}. [{e.type:>8}] {e.name} ({conns} connections, depth {e.depth})")

        print(f"\n  Commands: [number] expand | [a]uto expand next 5 | [b]oard | [g]aps | [s]ave | [q]uit")

        try:
            choice = input("\n  > ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            break

        if choice == 'q':
            break
        elif choice == 'b':
            board_path = os.path.join(investigation_dir, 'board_3d.html')
            generate_board_3d(graph, board_path, graph.name)
            os.system(f'xdg-open "{board_path}" 2>/dev/null &')
            print(f"   Board opened: {board_path}")
        elif choice == 'g':
            gaps = graph.detect_gaps()
            print(f"\n⚠️  {len(gaps)} gaps found:")
            for gap in gaps[:10]:
                print(f"   {gap['reason']}")
        elif choice == 's':
            save_path = graph.save(investigation_dir)
            print(f"   Saved: {save_path}")
        elif choice == 'a':
            # Auto-expand next 5
            for i, (eid, e) in enumerate(pending[:5]):
                expand_node(graph, eid, provider, engines)
            # Regenerate board
            board_path = os.path.join(investigation_dir, 'board_3d.html')
            generate_board_3d(graph, board_path, graph.name)
        elif choice.isdigit():
            idx = int(choice) - 1
            if 0 <= idx < len(pending):
                eid = pending[idx][0]
                expand_node(graph, eid, provider, engines)
                # Regenerate board
                board_path = os.path.join(investigation_dir, 'board_3d.html')
                generate_board_3d(graph, board_path, graph.name)
            else:
                print("   Invalid number")
        else:
            print("   Unknown command")

    # Final save
    graph.save(investigation_dir)
    print("\n💾 Investigation saved.")


def main():
    parser = argparse.ArgumentParser(description="DeepDive — Autonomous Investigation Tool")
    parser.add_argument("subject", nargs="?", help="Subject to investigate")
    parser.add_argument("--model", "-m", default="ollama:qwen3",
                        help="Model to use (ollama:qwen3, openai:gpt-4, lmstudio:model, etc.)")
    parser.add_argument("--search", "-s", choices=["ddg", "searxng", "none"], default=None,
                        help="Search engine preference (default: auto-detect best available)")
    parser.add_argument("--docs", help="Path to local document corpus to search")
    parser.add_argument("--load", "-l", help="Load existing investigation from directory")
    parser.add_argument("--auto", "-a", type=int, default=0,
                        help="Auto-expand N nodes then stop")
    parser.add_argument("--depth", "-d", type=int, default=3,
                        help="Maximum depth to auto-expand to")
    args = parser.parse_args()

    # Get provider
    provider = get_provider(args.model)
    print(f"🤖 Model: {provider.name}")
    print(f"   Available: {provider.is_available()}")

    # Get search engines
    engines = []
    if args.search != "none":
        engines = get_search_engines(search_pref=args.search, docs_dir=args.docs)
    if not engines:
        print("   ⚠️  No search engines — model will use its own knowledge only")

    if args.load:
        # Load existing investigation
        json_files = [f for f in os.listdir(args.load) if f.endswith('.json')]
        if not json_files:
            print(f"No investigation found in {args.load}")
            sys.exit(1)
        graph = InvestigationGraph.load(os.path.join(args.load, json_files[0]))
        investigation_dir = args.load
        print(f"📂 Loaded: {graph.name}")
    elif args.subject:
        # New investigation
        investigation_dir = os.path.join(os.path.dirname(__file__), '..', 'investigations',
                                         args.subject.lower().replace(' ', '_'))
        os.makedirs(investigation_dir, exist_ok=True)

        seed = Entity(args.subject, "unknown", {"source": "user_provided"})
        graph = InvestigationGraph(args.subject, seed)

        # First expansion: research the seed
        expand_node(graph, seed.id, provider, engines)
    else:
        parser.print_help()
        sys.exit(1)

    if args.auto > 0:
        # Auto mode: expand N nodes
        for i in range(args.auto):
            next_id = graph.get_next_to_investigate()
            if not next_id:
                break
            entity = graph.entities[next_id]
            if entity.depth > args.depth:
                break
            expand_node(graph, next_id, provider, engines)

        # Generate board and save
        board_path = os.path.join(investigation_dir, 'board_3d.html')
        generate_board_3d(graph, board_path, graph.name)
        graph.save(investigation_dir)
        print(f"\n🗺️  Board: {board_path}")
        print_graph_status(graph)
    else:
        # Interactive mode
        interactive_mode(graph, provider, engines, investigation_dir)


if __name__ == "__main__":
    main()
