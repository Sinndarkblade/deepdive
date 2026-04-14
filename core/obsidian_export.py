"""
Obsidian Vault Export
Converts a DeepDive investigation graph into an Obsidian-compatible vault.

Each entity becomes a .md note with:
  - YAML frontmatter (type, confidence, sources, depth, investigated)
  - Connections as [[wiki-links]] grouped by relationship
  - Findings and metadata as body text

The vault can be opened directly in Obsidian — graph view, backlinks,
and search all work immediately on import.
"""

import os
import re
from datetime import datetime


# Entity type → emoji for visual scanning in Obsidian
TYPE_EMOJI = {
    'person':     '👤',
    'company':    '🏢',
    'location':   '📍',
    'event':      '📅',
    'money':      '💰',
    'document':   '📄',
    'government': '🏛️',
    'concept':    '💡',
    'unknown':    '❓',
}

# Relationship → human-readable label
REL_LABELS = {
    'works_for':       'Works for',
    'leads':           'Leads',
    'founded':         'Founded',
    'invested_in':     'Invested in',
    'owns':            'Owns',
    'partnered_with':  'Partner of',
    'located_at':      'Located at',
    'met_with':        'Met with',
    'related_to':      'Related to',
    'formerly_at':     'Formerly at',
    'rival_of':        'Rival of',
    'board_member':    'Board member of',
    'married_to':      'Married to',
    'sued_by':         'Sued by',
    'funded_by':       'Funded by',
    'subsidiary_of':   'Subsidiary of',
    'investigated_by': 'Investigated by',
    'employed_by':     'Employed by',
    'paid_by':         'Paid by',
    'received_from':   'Received from',
}


def _safe_filename(name: str) -> str:
    """Convert entity name to a safe filename (Obsidian-compatible)."""
    safe = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '', name)
    safe = safe.strip('. ')
    return safe[:100] or 'unnamed'


def _conf_label(conf: float) -> str:
    if conf >= 0.85:
        return 'high'
    elif conf >= 0.6:
        return 'medium'
    return 'low'


def export_to_vault(graph, vault_path: str, include_index: bool = True) -> dict:
    """
    Export an InvestigationGraph to an Obsidian vault directory.

    Args:
        graph: InvestigationGraph instance
        vault_path: Absolute path to vault root (created if needed)
        include_index: Whether to write an INDEX.md overview note

    Returns:
        dict with 'written', 'skipped', 'vault_path', 'index_path'
    """
    os.makedirs(vault_path, exist_ok=True)

    # Sub-folder per entity type so Obsidian's file explorer is organized
    type_dirs = {}
    for etype in TYPE_EMOJI:
        d = os.path.join(vault_path, etype.title() + 's')
        os.makedirs(d, exist_ok=True)
        type_dirs[etype] = d
    type_dirs['unknown'] = os.path.join(vault_path, 'Other')
    os.makedirs(type_dirs['unknown'], exist_ok=True)

    # Build entity → filename map first (we need it for wiki-links)
    entity_filenames = {}
    for eid, entity in graph.entities.items():
        entity_filenames[eid] = _safe_filename(entity.name)

    written = 0
    skipped = 0

    for eid, entity in graph.entities.items():
        fname = entity_filenames[eid]
        folder = type_dirs.get(entity.type, type_dirs['unknown'])
        filepath = os.path.join(folder, fname + '.md')

        # Build connection lists grouped by relationship
        outgoing = {}  # rel → [(target_name, conf)]
        incoming = {}  # rel → [(source_name, conf)]

        for conn in graph.connections:
            if conn.source_id == eid:
                tgt = graph.entities.get(conn.target_id)
                if tgt:
                    rel = conn.relationship
                    outgoing.setdefault(rel, []).append((tgt.name, conn.confidence))
            elif conn.target_id == eid:
                src = graph.entities.get(conn.source_id)
                if src:
                    rel = conn.relationship
                    incoming.setdefault(rel, []).append((src.name, conn.confidence))

        # YAML frontmatter
        sources_yaml = '\n'.join(f'  - "{s}"' for s in (entity.sources or [])[:10])
        meta_yaml = ''
        if entity.metadata:
            for k, v in list(entity.metadata.items())[:8]:
                clean_v = str(v).replace('"', "'")[:120]
                meta_yaml += f'\n{k}: "{clean_v}"'

        # Confidence from highest outgoing connection
        all_confs = [c for conns in outgoing.values() for _, c in conns] + \
                    [c for conns in incoming.values() for _, c in conns]
        avg_conf = sum(all_confs) / len(all_confs) if all_confs else 0.5

        investigated_str = 'true' if entity.investigated else 'false'
        emoji = TYPE_EMOJI.get(entity.type, '❓')

        frontmatter = f"""---
name: "{entity.name}"
type: {entity.type}
depth: {entity.depth}
investigated: {investigated_str}
confidence: {_conf_label(avg_conf)}
discovered: "{entity.discovered_at[:10] if entity.discovered_at else 'unknown'}"
investigation: "{graph.name}"
tags:
  - deepdive
  - {entity.type}
  - {graph.name.lower().replace(' ', '-')}
{('sources:\n' + sources_yaml) if sources_yaml else 'sources: []'}
{meta_yaml}
---
"""

        # Body
        body = f"# {emoji} {entity.name}\n\n"

        if entity.metadata.get('description'):
            body += f"> {entity.metadata['description']}\n\n"

        # Outgoing connections
        if outgoing:
            body += "## Connections\n\n"
            for rel, targets in sorted(outgoing.items()):
                label = REL_LABELS.get(rel, rel.replace('_', ' ').title())
                for tname, conf in targets:
                    tgt_id = tname.lower().strip().replace(' ', '_')
                    tgt_fname = entity_filenames.get(tgt_id, _safe_filename(tname))
                    tgt_type = graph.entities.get(tgt_id, None)
                    tgt_emoji = TYPE_EMOJI.get(tgt_type.type if tgt_type else 'unknown', '❓')
                    body += f"- **{label}** → {tgt_emoji} [[{tgt_fname}]] _{_conf_label(conf)} confidence_\n"
            body += "\n"

        # Incoming connections
        if incoming:
            body += "## Referenced By\n\n"
            for rel, sources in sorted(incoming.items()):
                label = REL_LABELS.get(rel, rel.replace('_', ' ').title())
                for sname, conf in sources:
                    src_id = sname.lower().strip().replace(' ', '_')
                    src_fname = entity_filenames.get(src_id, _safe_filename(sname))
                    src_type = graph.entities.get(src_id, None)
                    src_emoji = TYPE_EMOJI.get(src_type.type if src_type else 'unknown', '❓')
                    body += f"- {src_emoji} [[{src_fname}]] **{label}** this entity\n"
            body += "\n"

        # Metadata details
        skip_keys = {'description', 'source', 'sources'}
        meta_items = {k: v for k, v in entity.metadata.items() if k not in skip_keys and v}
        if meta_items:
            body += "## Details\n\n"
            for k, v in list(meta_items.items())[:15]:
                body += f"- **{k.replace('_', ' ').title()}**: {str(v)[:200]}\n"
            body += "\n"

        # Investigation status
        body += "## Investigation Status\n\n"
        body += f"- **Depth**: {entity.depth} hops from seed\n"
        body += f"- **Expanded**: {'Yes' if entity.investigated else 'No — pending investigation'}\n"
        body += f"- **Investigation**: [[{_safe_filename(graph.name)}]]\n\n"

        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(frontmatter + "\n" + body)
            written += 1
        except Exception as e:
            print(f"[ObsidianExport] Skipping {fname}: {e}")
            skipped += 1

    # Write index note
    index_path = None
    if include_index:
        index_path = _write_index(graph, vault_path, entity_filenames, type_dirs)

    return {
        'written': written,
        'skipped': skipped,
        'vault_path': vault_path,
        'index_path': index_path,
    }


def _write_index(graph, vault_path, entity_filenames, type_dirs) -> str:
    """Write an INDEX.md overview note for the investigation."""
    stats = graph.get_stats()
    now = datetime.now().strftime('%Y-%m-%d %H:%M')

    lines = [
        f"# 🔍 Investigation: {graph.name}",
        "",
        f"> Exported from DeepDive on {now}",
        "",
        "## Summary",
        "",
        f"| Stat | Value |",
        f"|------|-------|",
        f"| Entities | {stats['total_entities']} |",
        f"| Connections | {stats['total_connections']} |",
        f"| Investigated | {stats['investigated']} / {stats['total_entities']} |",
        f"| Depth | {stats['depth_max']} hops |",
        f"| Gaps found | {stats['gaps_found']} |",
        "",
        "## Entity Breakdown",
        "",
    ]

    for etype, count in sorted(stats.get('entity_types', {}).items(), key=lambda x: -x[1]):
        emoji = TYPE_EMOJI.get(etype, '❓')
        lines.append(f"- {emoji} **{etype.title()}s**: {count}")

    lines += ["", "## Key Findings", ""]
    if graph.findings:
        for f in graph.findings[:20]:
            lines.append(f"- {f}")
    else:
        lines.append("_No findings recorded yet._")

    lines += ["", "## Suspicious Gaps", ""]
    top_gaps = sorted(graph.gaps or [], key=lambda g: -g.get('score', 0))[:10]
    if top_gaps:
        for gap in top_gaps:
            a = entity_filenames.get(gap['entity_a'], gap.get('a_name', '?'))
            c = entity_filenames.get(gap['entity_c'], gap.get('c_name', '?'))
            b = gap.get('b_name', '?')
            score = gap.get('score', 0)
            lines.append(f"- **Score {score}**: [[{a}]] and [[{c}]] both connect to {b} but not each other")
    else:
        lines.append("_No gaps detected yet. Run a gap analysis in DeepDive._")

    # Seed entity
    seed_id = list(graph.entities.keys())[0] if graph.entities else None
    if seed_id:
        seed = graph.entities[seed_id]
        seed_fname = entity_filenames.get(seed_id, _safe_filename(seed.name))
        lines += ["", "## Seed Entity", "", f"[[{seed_fname}]]", ""]

    lines += [
        "## How To Use This Vault",
        "",
        "- Open Graph View (`Ctrl+G`) to see the full connection network",
        "- Click any node to open its note — backlinks show all references",
        "- Use `[[` to manually link new research notes to entities",
        "- Tag search: `#deepdive` shows all investigation notes",
        f"- Tag search: `#{graph.name.lower().replace(' ', '-')}` shows this investigation only",
        "",
        "_Generated by [DeepDive](https://github.com/your-repo/deepdive)_",
    ]

    index_path = os.path.join(vault_path, 'INDEX.md')
    with open(index_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))

    return index_path
