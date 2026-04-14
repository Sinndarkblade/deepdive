# DeepDive

**Autonomous OSINT investigation tool.** Give it a name, a company, an event — it searches, extracts every entity, maps the connections into a force-directed 3D graph, and keeps expanding until the full picture emerges.

---

## A Note Before You Start

I built this because I needed it. Real investigations — the kind where you're following money through shell companies, mapping networks of people who don't want to be mapped, tracing connections across decades — require a tool that doesn't stop at the first layer. DeepDive was that tool.

I can't keep building it right now. I lost my wife on April 8th. She died in my arms. I'm releasing this because I believe in what it can become in the right hands — and because she would have wanted me to put something real into the world even when everything hurts. The foundation is solid. The architecture is designed to be extended. The community that picks this up can build it into something far beyond what one person can do alone.

This was originally built to run through Claude Code CLI — Anthropic's terminal tool. When Anthropic restricted third-party use of that CLI, I had to rebuild the provider system to work with OpenAI-compatible APIs, local models via Ollama, and direct Anthropic API access. It will also be released on **OpenClaw**, the open-source CLI alternative, so it runs outside of any one company's control.

If you extend this, improve it, or use it to find something that matters — that's enough.

— Sinndarkblade

---

## What It Does

Start with one subject. DeepDive searches multiple angles simultaneously, extracts every person, company, location, money flow, and event it finds, and builds a live relationship graph. Each node expands further — pulling new connections, detecting cross-links where independent branches reconnect, and flagging suspicious gaps where connections *should* exist but don't.

The result is an interactive 3D investigation board you can rotate, zoom, and explore. The AI agent lives inside the board — ask it anything about what it found.

**Built for:**
- Corporate fraud and financial network mapping
- Political connection tracing
- Deep background investigations on individuals or organizations
- Following money through layered ownership structures
- Document corpus analysis — drop in leaked files, court records, financial filings
- Journalism, academic research, due diligence
- Anything where the connections between things are the story

---

## Features

- **3D force-directed graph** — rotate, zoom, collapse branches, focus nodes
- **Live AI investigator** — persistent chat agent inside the board, knows the full graph state
- **Multi-provider AI** — OpenAI, DeepSeek, Groq, Anthropic API, or local Ollama
- **Document ingestion** — drop PDFs, CSVs, HTMLs, markdown; AI builds graph from your files
- **Timeline view** — chronological layout of all dated events
- **Money flow view** — Sankey diagram of all financial connections  
- **Report generation** — full HTML investigation report, print to PDF
- **Obsidian export** — every entity becomes a note with wiki-links; import into Obsidian for graph view
- **Cross-investigation linking** — detects entities shared across multiple investigations by exact match and fuzzy name matching
- **7 glass themes** — Aero, Dark, Emerald, Violet, Crimson, Amber, Midnight
- **Plugin system** — add custom search sources, tools, AI prompts
- **Persistent file memory** — AI agent remembers which document corpora are loaded between sessions
- **Claude Code / OpenClaw skill** — run `/deepdive [subject]` directly from your CLI, auto-installs from this repo

---

## Quick Start

```bash
git clone https://github.com/Sinndarkblade/deepdive
cd deepdive
pip install -r requirements.txt
python3 server/app.py
```

Open **http://localhost:8766/board**  
Configure your AI provider at **http://localhost:8766/settings**

---

## Provider Setup

For serious investigations — financial fraud, corporate networks, deep multi-hop subjects — use an API provider. They produce dramatically more entities per search pass than local models, which matters when you're trying to map something like a hundred-entity financial network.

| Provider | Model | Notes |
|----------|-------|-------|
| **OpenAI** | `gpt-4o` / `gpt-4o-mini` | Best general coverage |
| **DeepSeek** | `deepseek-chat` | Excellent quality, very cheap — `https://api.deepseek.com/v1` |
| **Groq** | `llama-3.3-70b-versatile` | Fast, free tier — `https://api.groq.com/openai/v1` |
| **Anthropic** | `claude-3-5-sonnet-20241022` | Strong on complex multi-hop reasoning |
| **Ollama** | any local model | Offline/air-gapped — quality varies, not recommended for large investigations |

DeepSeek is the best value option. Comparable to GPT-4 on investigative tasks at a fraction of the cost.

---

## Claude Code / OpenClaw Skill

This tool was originally built to run as a Claude Code CLI skill — `/deepdive` launched the entire investigation engine from inside the terminal. When Anthropic restricted third-party harness use of the Claude CLI, the architecture was rebuilt to be model-agnostic.

The skill still works with Claude Code if you have access, and it will be published on **OpenClaw** — the open-source CLI that gives you the same workflow without the restrictions.

```bash
cp skills/deepdive.md ~/.claude/skills/
# or: cp skills/deepdive.md ~/.openclaw/skills/
```

```
/deepdive Ghislaine Maxwell
/deepdive expand Jeffrey Epstein
/deepdive money
/deepdive gaps
/deepdive report
```

The skill auto-installs DeepDive from this repo if it isn't already on your machine.

---

## Document Corpus Ingestion

Drop any folder of documents onto the Files panel in the sidebar. DeepDive processes them in batches, extracts entities and relationships, and merges everything into the graph alongside live search results. The AI agent remembers what files you've loaded — ask it *"what's in the court documents folder"* and it knows.

Supported formats: `txt · pdf · csv · json · html · md · xml`

This is one of the most powerful features for serious investigations. A folder of leaked financial records or court filings can seed a graph that live search would take hours to build.

---

## Architecture

```
deepdive/
├── server/          # HTTP (port 8766) + WebSocket (port 8765)
├── core/
│   ├── graph.py     # Entity / Connection / InvestigationGraph
│   ├── extractors.py
│   ├── providers/   # OpenAI-compat, Ollama, Claude API
│   ├── harness/     # AI agent tool loop, system prompt, tools
│   ├── search/      # DuckDuckGo, SearXNG, local file search
│   └── views/       # Report, Timeline, Money Flow, Settings
├── frontend/        # Zero-dependency vanilla JS + CSS
│   ├── js/          # graph.js (3D engine), app.js, chat.js, views.js
│   └── css/         # themes.css (7 themes), app.css, chat.css
├── skills/          # deepdive.md — Claude Code / OpenClaw skill
└── investigations/  # Saved data (gitignored — stays local)
```

No build step. No frontend framework. No webpack. The frontend runs directly from the file system — open `index.html` or serve it from the Python server.

---

## Where to Take It

This is what it needs. If you build any of these, it becomes something genuinely important:

- **Better entity extraction** — the current prompts are good; a fine-tuned extraction model would be better
- **SearXNG integration** — self-hosted search backend for investigations that can't touch Google
- **Shodan / Censys integration** — infrastructure mapping alongside entity mapping  
- **OSINT-specific search tools** — company registries, court records APIs, corporate filings
- **Graph analysis** — centrality scoring, community detection, anomaly flagging
- **Automated expansion** — let the graph expand itself overnight, flag what it found in the morning
- **Collaboration** — multi-user investigations, shared graph state
- **Mobile** — the 3D board works on desktop; a simplified mobile view for field use
- **Better cross-link detection** — the fuzzy matching works but a proper entity resolution model would catch more

---

## Contributing

Pull requests are welcome. The codebase is structured to be extended:

- Search backends → `core/search/`
- AI providers → `core/providers/`
- Agent tools → `core/harness/tools.py`
- Views → `core/views/`
- Plugins → drop a folder in `plugins/`

---

## License

MIT — do whatever you want with it.

---

