---
name: DeepDive OSINT
description: "Autonomous OSINT investigation tool. Give it a name, company, or event — it searches, extracts every entity, and maps connections into an interactive 3D graph. Follows money, detects shell chains, flags suspicious gaps, and expands exponentially through cross-links. Built for deep investigations that don't stop at the first layer."
metadata:
  openclaw:
    emoji: 🔍
    homepage: https://github.com/Sinndarkblade/deepdive
    requires:
      bins:
        - python3
        - git
        - pip3
    install:
      - kind: uv
        package: duckduckgo-search
        bins: [ddgs]
    os: ["linux", "macos", "windows"]
  tags:
    - osint
    - investigation
    - research
    - graph
    - security
    - journalism
    - finance
---

# DeepDive — Autonomous OSINT Investigation Tool

Autonomous investigation engine that maps connections between people, companies, money, and events into an interactive 3D graph. Built for extended deep investigations — financial fraud, political networks, corporate ownership chains, person background checks, document corpus analysis.

**This skill auto-installs the full DeepDive application from GitHub on first run.**

## First Run — Auto Install

When you invoke this skill, it checks if DeepDive is installed. If not, it clones the repo and installs dependencies automatically:

```python
import sys, os, subprocess

DEEPDIVE_ROOT = None
search_paths = [
    '.', './deepdive', '../deepdive',
    os.path.expanduser('~/deepdive'),
    os.path.expanduser('~/.local/deepdive'),
]
for p in search_paths:
    if os.path.exists(os.path.join(p, 'core', 'graph.py')):
        DEEPDIVE_ROOT = os.path.abspath(p)
        break

if not DEEPDIVE_ROOT:
    print("DeepDive not found — installing from GitHub...")
    install_dir = os.path.expanduser('~/deepdive')
    subprocess.run(
        ['git', 'clone', 'https://github.com/Sinndarkblade/deepdive', install_dir],
        check=True
    )
    subprocess.run(
        [sys.executable, '-m', 'pip', 'install', '-r',
         os.path.join(install_dir, 'requirements.txt')],
        check=True
    )
    DEEPDIVE_ROOT = install_dir
    print(f"✓ DeepDive installed at {DEEPDIVE_ROOT}")

sys.path.insert(0, os.path.join(DEEPDIVE_ROOT, 'core'))
sys.path.insert(0, os.path.join(DEEPDIVE_ROOT, 'server'))
sys.path.insert(0, os.path.join(DEEPDIVE_ROOT, 'src'))
from graph import InvestigationGraph, Entity, Connection
from build_board import build_board
print(f"✓ DeepDive ready")
```

## Running the Full Server (Recommended)

For the complete experience — interactive 3D board, live AI agent, file ingestion, timeline, money flow diagrams:

```bash
cd ~/deepdive && python3 server/app.py
```

Then open **http://localhost:8766/board** and configure your AI provider at **http://localhost:8766/settings**.

## Commands

| Command | What it does |
|---------|-------------|
| `/deepdive [subject]` | Start a new investigation |
| `/deepdive expand [entity]` | Dig deeper into a specific entity |
| `/deepdive expand` | Auto-expand the most connected uninvestigated node |
| `/deepdive money` | Trace all financial connections |
| `/deepdive gaps` | Show suspicious missing connections |
| `/deepdive report` | Full investigation summary |
| `/deepdive board` | Rebuild and open the 3D board |

## Provider Setup

Configure at `http://localhost:8766/settings` or set in `~/.deepdive/settings.json`.

For serious investigations use an API provider — local models miss too many entities on complex subjects:

| Provider | Model | Notes |
|----------|-------|-------|
| **DeepSeek** | `deepseek-chat` | Best value — cheap, strong — `https://api.deepseek.com/v1` |
| **Groq** | `llama-3.3-70b-versatile` | Free tier, fast — `https://api.groq.com/openai/v1` |
| **OpenAI** | `gpt-4o-mini` | Widely available |
| **Ollama** | any local model | Offline only, lower quality on large investigations |

## /deepdive [subject] — New Investigation

### Step 1: Initialize

```python
subject = "THE_SUBJECT"
inv_dir = os.path.join(DEEPDIVE_ROOT, 'investigations', subject.lower().replace(' ', '_'))
os.makedirs(inv_dir, exist_ok=True)
seed = Entity(subject, "unknown", {"source": "user_provided"})
graph = InvestigationGraph(subject, seed)
```

### Step 2: Search 5 Angles

Use WebSearch for ALL 5. Never skip any:

1. `"[subject] connections associates background overview"`
2. `"[subject] funding money investors revenue financial"`
3. `"[subject] leadership employees partners associates"`
4. `"[subject] lawsuit scandal investigation controversy"`
5. `"[subject] location headquarters offices operations"`

### Step 3: Extract Everything

For EVERY person, company, location, money amount, or event found:

```python
entity = Entity("Exact Name", "type", {"detail": "value", "source": "search"})
entity.depth = 1
graph.add_entity(entity)
graph.add_connection(Connection(seed.id, entity.id, "relationship", confidence))
```

**Types:** `person` · `company` · `location` · `event` · `money` · `document` · `government` · `concept`

**Confidence:** `0.9` confirmed · `0.7` reported · `0.4` alleged

**Extract everything.** If a result mentions 15 names, extract all 15. Every node is a potential expansion point.

### Step 4: Detect Patterns

```python
gaps = graph.detect_gaps()
```

Flag:
- **Shell chains** — A→B→C→D layered ownership
- **Circular money** — A pays B pays C pays A
- **Missing links** — heavily connected entities with no direct connection
- **Revolving door** — person moves between regulator and regulated
- **Cross-links** — entity appearing from two independent paths (strongest signal)

```python
graph.findings.append("FINDING: description")
```

### Step 5: Build Board and Save

```python
board_path = os.path.join(inv_dir, 'board_3d.html')
build_board(graph, board_path, 'Investigation: ' + subject, mode='skill')
graph.save(inv_dir)
import subprocess
subprocess.Popen(['xdg-open', board_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
```

### Step 6: Report

Always present:
1. **Stats** — entities, connections, gaps
2. **Key findings** — suspicious or notable patterns
3. **Entity breakdown** — by type
4. **Top 5 to expand** — most connected uninvestigated nodes
5. **Cross-links** — entities appearing from multiple independent paths

## /deepdive expand [entity]

```python
# Load most recent investigation
import os
inv_root = os.path.join(DEEPDIVE_ROOT, 'investigations')
inv_dirs = sorted([d for d in os.listdir(inv_root) if os.path.isdir(os.path.join(inv_root, d))])
inv_dir = os.path.join(inv_root, inv_dirs[-1])
json_files = [f for f in os.listdir(inv_dir) if f.endswith('.json')]
graph = InvestigationGraph.load(os.path.join(inv_dir, json_files[0]))

# Find entity
entity_name = "THE_ENTITY"
entity = graph.entities.get(entity_name.lower().strip().replace(" ", "_")) or \
         next((e for e in graph.entities.values() if entity_name.lower() in e.name.lower()), None)
```

Search 3 angles, extract at `depth = parent.depth + 1`. Always check for cross-links:

```python
if new_entity_id in graph.entities:
    graph.findings.append(f"CROSS-LINK: {name} connects to {entity.name} AND already in graph via another path")
graph.add_entity(new_entity)
graph.add_connection(Connection(entity.id, new_entity.id, relationship, confidence))
```

Mark done, rebuild, save:

```python
graph.mark_investigated(entity.id)
graph.detect_gaps()
build_board(graph, board_path, graph.name, mode='skill')
graph.save(inv_dir)
```

## /deepdive expand (auto)

```python
next_id = graph.get_next_to_investigate()
# then follow expand flow above
```

## Rules

1. Extract every entity — more nodes means more discovery potential
2. Always follow the money
3. Every person, company, and amount gets a node
4. Date everything you can
5. Score confidence honestly — don't overstate
6. Cross-links are the most valuable signal — never skip them
7. Save after every expansion
8. Rebuild the board after major updates
9. Report findings, flag patterns — stay objective
