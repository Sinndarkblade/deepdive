"""
Tool Definitions — AI function calling interface.
Defines every server function as a tool the AI can call.
Uses Claude tool_use format (adaptable to OpenAI function_calling).
"""


def get_tool_definitions():
    """Return the complete list of tool definitions for the AI.
    Each tool has: name, description, input_schema (JSON Schema).
    """
    return [
        # ── Investigation Management ──
        {
            "name": "new_investigation",
            "description": "Start a new investigation case. Creates a new graph with the given subject as the seed entity.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "The subject to investigate (person, company, event, topic)"}
                },
                "required": ["name"]
            }
        },
        {
            "name": "list_investigations",
            "description": "List all saved investigation cases with entity counts and connection counts. Use this to show the user their previous work.",
            "input_schema": {"type": "object", "properties": {}}
        },
        {
            "name": "switch_investigation",
            "description": "Switch to a different saved investigation. Loads the graph and all associated data.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "dir": {"type": "string", "description": "The directory path of the investigation to load"}
                },
                "required": ["dir"]
            }
        },

        # ── Entity Operations ──
        {
            "name": "expand_entity",
            "description": "Dive deeper on an entity — search the web, query enabled OSINT feeds, extract connections. IMPORTANT: Present results to the user for approval before adding to the graph.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "entity_id": {"type": "string", "description": "The entity ID (lowercase name with underscores)"},
                    "entity_name": {"type": "string", "description": "The display name of the entity"},
                    "search_mode": {"type": "string", "enum": ["web", "local", "both"], "description": "Where to search. Default: web"},
                    "enabled_feeds": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of OSINT feed names to query (e.g., ['news', 'sec', 'sanctions']). Omit for defaults only."
                    }
                },
                "required": ["entity_id", "entity_name"]
            }
        },
        {
            "name": "generate_report",
            "description": "Generate a detailed intelligence report on an entity. Includes all connections, patterns, and recommendations.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "entity_id": {"type": "string", "description": "Entity ID"},
                    "entity_name": {"type": "string", "description": "Entity display name"}
                },
                "required": ["entity_id", "entity_name"]
            }
        },
        {
            "name": "pin_node",
            "description": "Bookmark an entity as important for the investigation.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "entity_id": {"type": "string", "description": "Entity ID to pin/unpin"}
                },
                "required": ["entity_id"]
            }
        },
        {
            "name": "add_note",
            "description": "Add a text annotation to an entity in the graph.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "entity_id": {"type": "string", "description": "Entity ID"},
                    "note": {"type": "string", "description": "The note text to attach"}
                },
                "required": ["entity_id", "note"]
            }
        },
        {
            "name": "prune_node",
            "description": "Remove an entity and its exclusive connections from the graph. Ask the user for confirmation first.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "entity_id": {"type": "string", "description": "Entity ID to remove"}
                },
                "required": ["entity_id"]
            }
        },

        # ── OSINT Data Feeds ──
        {
            "name": "query_feed",
            "description": "Query a specific OSINT data feed for information about an entity. Returns raw data for review. Available feeds: news, gdelt, reddit, bluesky, conflicts, darkweb, gov, patents, sec, sanctions, cisa, humanitarian, flights, ships, earthquakes, fires, satellites, weather, launches, stock.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "feed_name": {
                        "type": "string",
                        "enum": ["news", "gdelt", "reddit", "bluesky", "conflicts", "darkweb",
                                 "gov", "patents", "sec", "sanctions", "cisa", "humanitarian",
                                 "flights", "ships", "earthquakes", "fires", "satellites",
                                 "weather", "launches", "stock"],
                        "description": "Which feed to query"
                    },
                    "entity": {"type": "string", "description": "What to search for"}
                },
                "required": ["feed_name", "entity"]
            }
        },
        {
            "name": "query_all_feeds",
            "description": "Query all available OSINT feeds at once for an entity. Returns aggregated results from all sources.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "entity": {"type": "string", "description": "What to search for"}
                },
                "required": ["entity"]
            }
        },

        # ── AI-Powered Traces ──
        {
            "name": "trace_timeline",
            "description": "Use AI to trace the complete chronological timeline of events for an entity. Searches the web and builds a dated event list.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "entity": {"type": "string", "description": "Entity to trace"}
                },
                "required": ["entity"]
            }
        },
        {
            "name": "trace_money",
            "description": "Use AI to trace all financial connections for an entity. Follows payments, investments, acquisitions, shell companies.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "entity": {"type": "string", "description": "Entity to trace"}
                },
                "required": ["entity"]
            }
        },
        {
            "name": "scan_social_media",
            "description": "Use AI to search social media platforms for posts by or about an entity.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "entity": {"type": "string", "description": "Entity to search"}
                },
                "required": ["entity"]
            }
        },
        {
            "name": "check_wayback",
            "description": "Use AI to check the Wayback Machine for archived and deleted web content related to an entity.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "entity": {"type": "string", "description": "Entity to check"}
                },
                "required": ["entity"]
            }
        },

        # ── Gap Analysis ──
        {
            "name": "list_gaps",
            "description": "Show suspicious gaps in the investigation graph — entities that should be connected but aren't.",
            "input_schema": {"type": "object", "properties": {}}
        },
        {
            "name": "research_gaps",
            "description": "Actively investigate the top suspicious gaps by searching for hidden connections.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "max_gaps": {"type": "integer", "description": "How many gaps to research (default 5)", "default": 5}
                }
            }
        },

        # ── Views / Navigation ──
        {
            "name": "show_view",
            "description": "Switch the main display to a different view.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "view": {
                        "type": "string",
                        "enum": ["graph", "timeline", "money_flow", "report", "settings"],
                        "description": "Which view to display"
                    }
                },
                "required": ["view"]
            }
        },

        # ── Data Sources ──
        {
            "name": "scan_dataset",
            "description": "Process a folder of local documents — extract entities and add to the investigation. Processes 5-10 documents at a time for large collections. Ask the user before processing massive collections.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "folder_path": {"type": "string", "description": "Absolute path to the document folder"}
                },
                "required": ["folder_path"]
            }
        },

        # ── Approval ──
        {
            "name": "approve_entities",
            "description": "Approve entities from a staged batch and add them to the investigation graph. Call this after presenting found entities to the user. Pass approved_indices to add specific items, or omit to add all.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "batch_id": {"type": "string", "description": "The batch ID returned from expansion/trace"},
                    "approved_indices": {
                        "type": "array",
                        "items": {"type": "integer"},
                        "description": "Indices of items to approve (0-based). Omit to approve all."
                    }
                },
                "required": ["batch_id"]
            }
        },
        {
            "name": "reject_batch",
            "description": "Reject/discard all pending entities from a batch. Use when the user doesn't want any of the found entities.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "batch_id": {"type": "string", "description": "The batch ID to reject"}
                },
                "required": ["batch_id"]
            }
        },

        # ── File Ingestion (batched) ──
        {
            "name": "count_documents",
            "description": "Count how many processable documents are in a folder. Use this before starting ingestion to know the scope.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "folder_path": {"type": "string", "description": "Absolute path to the document folder"}
                },
                "required": ["folder_path"]
            }
        },
        {
            "name": "process_document_batch",
            "description": "Process a batch of 10 documents from a folder. Call repeatedly with incrementing batch_index. Returns found entities for user review — do NOT auto-add. If collection is 50+ docs, offer the user parallel processing but warn about API costs.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "folder_path": {"type": "string", "description": "Absolute path to documents"},
                    "batch_index": {"type": "integer", "description": "Which batch to process (0-based)", "default": 0}
                },
                "required": ["folder_path"]
            }
        },

        # ── File Reading ──
        {
            "name": "read_file",
            "description": "Read a specific file and extract entities from it. Works with any text file, PDF, CSV, JSON, HTML, or document. Use this when the user points you at a single file to analyze.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "description": "Absolute path to the file to read and analyze"}
                },
                "required": ["file_path"]
            }
        },
        {
            "name": "list_file_memory",
            "description": "Show all document folders and files that have been previously loaded into DeepDive. Use this when the user asks about available documents, wants to re-use a previous corpus, or asks 'what files do I have?'",
            "input_schema": {"type": "object", "properties": {}}
        },
        {
            "name": "forget_corpus",
            "description": "Remove a document folder from the file memory. Use when the user says they no longer want a folder remembered.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "folder_path": {"type": "string", "description": "Path of the folder to remove from memory"}
                },
                "required": ["folder_path"]
            }
        },

        # ── Cross-Investigation Memory ──
        {
            "name": "check_past_investigations",
            "description": "Search all past investigations for an entity name — find if this person, company, or entity appeared before in any other investigation. Returns exact matches and fuzzy matches with similarity scores. Use this proactively when you encounter a new entity that might be significant.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "entity_name": {"type": "string", "description": "The entity name to search for across all investigations"},
                    "entity_type": {"type": "string", "description": "Entity type hint (person, company, etc.) to narrow matches", "default": "unknown"}
                },
                "required": ["entity_name"]
            }
        },
        {
            "name": "scan_all_crosslinks",
            "description": "Run a full cross-investigation scan — find all entities shared across multiple investigations. Returns exact and fuzzy matches grouped by frequency. Use when the user asks 'what keeps coming up?' or 'what do these investigations have in common?'",
            "input_schema": {"type": "object", "properties": {}}
        },

        # ── Export ──
        {
            "name": "export_investigation",
            "description": "Export the current investigation data.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "format": {
                        "type": "string",
                        "enum": ["json", "markdown", "html_report"],
                        "description": "Export format"
                    }
                },
                "required": ["format"]
            }
        },
    ]


def get_tools_for_claude():
    """Return tools in Claude API format (tool_use)."""
    return get_tool_definitions()


def get_tools_for_openai():
    """Return tools in OpenAI function_calling format. For future use."""
    return [
        {
            "type": "function",
            "function": {
                "name": tool["name"],
                "description": tool["description"],
                "parameters": tool["input_schema"],
            }
        }
        for tool in get_tool_definitions()
    ]
