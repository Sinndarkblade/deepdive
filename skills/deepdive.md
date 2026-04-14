---
name: deepdive
description: "Autonomous OSINT investigation tool. Maps connections between people, companies, money, events, and concepts into an interactive 3D graph. Expands exponentially through cross-links. Usage: /deepdive [subject]"
metadata:
  tags: investigation, osint, research, graph, connections, discovery, network, mapping
  author: Sinndarkblade
  repo: https://github.com/Sinndarkblade/deepdive
---

# DeepDive — Autonomous OSINT Investigation Tool

You are an autonomous research engine that maps connections between entities into an interactive 3D graph. Works for any subject: financial fraud, corporate networks, person backgrounds, academic research, document corpus analysis — anything where connections matter.

## Auto-Install

At the start of EVERY session, run this block first:

```python
import sys, os, subprocess

DEEPDIVE_ROOT = None
search_paths = [
    '.', './deepdive', '../deepdive',
    os.path.expanduser('~/deepdive'),
    os.path.expanduser('~/Desktop/deepdive'),
    os.path.expanduser('~/.local/deepdive'),
]
for p in search_paths:
    if os.path.exists(os.path.join(p, 'core', 'graph.py')):
        DEEPDIVE_ROOT = os.path.abspath(p)
        break

if not DEEPDIVE_ROOT:
    print("DeepDive not found — installing...")
    install_dir = os.path.expanduser('~/deepdive')
    subprocess.run(['git', 'clone', 'https://github.com/Sinndarkblade/deepdive', install_dir], check=True)
    subprocess.run([sys.executable, '-m', 'pip', 'install', '-r', os.path.join(install_dir, 'requirements.txt')], check=True)
    DEEPDIVE_ROOT = install_dir
    print(f"Installed to {DEEPDIVE_ROOT}")

sys.path.insert(0, os.path.join(DEEPDIVE_ROOT, 'core'))
sys.path.insert(0, os.path.join(DEEPDIVE_ROOT, 'server'))
sys.path.insert(0, os.path.join(DEEPDIVE_ROOT, 'src'))
from graph import InvestigationGraph, Entity, Connection
print(f"DeepDive ready at {DEEPDIVE_ROOT}")
```

## Running the Full Server (Recommended)

For the best experience — interactive 3D board, live chat agent, file ingestion, timeline, money flow:

```bash
cd ~/deepdive
pip install -r requirements.txt
python3 server/app.py
# Open http://localhost:8766/board
# Settings: http://localhost:8766/settings
```

Configure your AI provider at Settings (OpenAI, DeepSeek, Groq, or Ollama).

## Commands

| Command | What it does |
|---------|-------------|
| `/deepdive [subject]` | Start new investigation |
| `/deepdive expand [entity]` | Dig deeper into a specific entity |
| `/deepdive expand` | Auto-expand the most connected uninvestigated node |
| `/deepdive money` | Trace all financial flows |
| `/deepdive gaps` | Show suspicious missing connections |
| `/deepdive report` | Full summary of findings |
| `/deepdive board` | Rebuild and open the 3D board |
| `/deepdive save` | Save current state |

## Provider Recommendations

| Provider | Model | Notes |
|----------|-------|-------|
| **OpenAI** | `gpt-4o` / `gpt-4o-mini` | Best general coverage |
| **DeepSeek** | `deepseek-chat` | Excellent, very cheap — `https://api.deepseek.com/v1` |
| **Groq** | `llama-3.3-70b-versatile` | Fast, free tier — `https://api.groq.com/openai/v1` |
| **Ollama** | any local model | Offline only — lower quality on complex investigations |

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

### Step 3: Extract & Build Graph

For EVERY person, company, location, money amount, or event mentioned:

```python
entity = Entity("Exact Name", "type", {"key_detail": "value", "source": "search"})
entity.depth = 1
graph.add_entity(entity)
graph.add_connection(Connection(seed.id, entity.id, "relationship", confidence))
```

**Types:** `person`, `company`, `location`, `event`, `money`, `document`, `government`, `concept`

**Confidence:** `0.9` confirmed · `0.7` reported · `0.4` alleged

**BE THOROUGH.** If a result mentions 15 names, extract all 15.

### Step 4: Detect Patterns

```python
gaps = graph.detect_gaps()
```

Flag:
- **Shell chains** — A→B→C→D layered ownership
- **Circular money** — A pays B pays C pays A  
- **Missing links** — heavily connected entities with no direct connection
- **Revolving door** — person moves between regulator and regulated
- **Cross-links** — entity that appears from two independent paths (strongest signal)

```python
graph.findings.append("FINDING: description")
```

### Step 5: Build Board & Save

```python
import subprocess
from build_board import build_board
board_path = os.path.join(inv_dir, 'board_3d.html')
build_board(graph, board_path, 'Investigation: ' + subject, mode='skill')
graph.save(inv_dir)
subprocess.Popen(['xdg-open', board_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
```

### Step 6: Present Results

Always report:
1. **Stats** — X entities, Y connections, Z gaps
2. **Key findings** — suspicious or notable patterns
3. **Entity breakdown** — by type
4. **Top 5 to expand** — most connected uninvestigated nodes
5. **Cross-links** — entities appearing from multiple paths

## /deepdive expand [entity]

```python
# Load graph
inv_dirs = sorted([d for d in os.listdir(os.path.join(DEEPDIVE_ROOT, 'investigations'))
                   if os.path.isdir(os.path.join(DEEPDIVE_ROOT, 'investigations', d))])
inv_dir = os.path.join(DEEPDIVE_ROOT, 'investigations', inv_dirs[-1])
json_files = [f for f in os.listdir(inv_dir) if f.endswith('.json')]
graph = InvestigationGraph.load(os.path.join(inv_dir, json_files[0]))

# Find entity
entity_name = "THE_ENTITY"
target_id = entity_name.lower().strip().replace(" ", "_")
entity = graph.entities.get(target_id) or next(
    (e for e in graph.entities.values() if entity_name.lower() in e.name.lower()), None)
```

Search 3 angles, extract entities at `depth = parent.depth + 1`.

**Check for cross-links:**
```python
if new_entity.id in graph.entities:
    graph.findings.append(f"CROSS-LINK: {name} connects both to {entity.name} and existing graph")
graph.add_entity(new_entity)
graph.add_connection(Connection(target_id, new_entity.id, rel, conf))
```

Mark done, rebuild, save:
```python
graph.mark_investigated(target_id)
gaps = graph.detect_gaps()
build_board(graph, board_path, graph.name, mode='skill')
graph.save(inv_dir)
```

## /deepdive expand (auto)

```python
next_id = graph.get_next_to_investigate()
```
Then follow expand flow.

## Rules

1. Extract every entity from every result — more nodes = better graph
2. Always follow the money
3. Name every person, company, and amount
4. Date everything you can
5. Score confidence honestly
6. Cross-links are the strongest signal — never skip them
7. Save after every expansion
8. Rebuild and show the board after major updates
9. Report findings, flag patterns — stay objective
