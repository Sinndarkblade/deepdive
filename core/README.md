# DeepDive Core

Shared engine used by both the CLI and Claude Code skill.

## Components

- `graph.py` — Entity/Connection/InvestigationGraph data structure, gap detection, save/load
- `extractors.py` — Parse AI responses into structured entities (pipe-delimited + freeform NER)
- `providers/` — Model-agnostic AI provider interface
- `search/` — Independent search layer (DuckDuckGo, SearXNG, local files)

## Pipeline

```
Search (DDG/SearXNG/Local) → Raw results
         ↓
Model (Ollama/OpenAI/etc) → Analyze results, output entities
         ↓
Extractor → Parse pipe-delimited + freeform entities
         ↓
Graph → Add entities, connections, detect gaps
         ↓
Board → Rebuild 3D HTML visualization
```
