"""
File Memory — Persists loaded document corpora across sessions.

Stores which folders and files have been indexed so:
  1. The AI's system prompt can inform it what corpora are available
  2. Researchers don't have to re-point the tool at files each session
  3. Cross-session queries ("search the Epstein docs") work immediately

Stored in ~/.deepdive/file_memory.json
"""

import json
import os
from datetime import datetime
from pathlib import Path

MEMORY_FILE = Path.home() / '.deepdive' / 'file_memory.json'


def _load() -> dict:
    try:
        if MEMORY_FILE.exists():
            with open(MEMORY_FILE) as f:
                return json.load(f)
    except Exception:
        pass
    return {'corpora': [], 'individual_files': []}


def _save(data: dict):
    try:
        MEMORY_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(MEMORY_FILE, 'w') as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        print(f'[FileMemory] Save error: {e}')


def register_folder(folder_path: str, label: str = '', doc_count: int = 0, investigation: str = ''):
    """Record that a folder was indexed into DeepDive."""
    data = _load()
    folder_path = os.path.abspath(folder_path)

    # Update existing or add new
    for entry in data['corpora']:
        if entry['path'] == folder_path:
            entry['last_used'] = datetime.now().isoformat()
            entry['doc_count'] = doc_count or entry.get('doc_count', 0)
            entry['investigation'] = investigation or entry.get('investigation', '')
            if label:
                entry['label'] = label
            _save(data)
            return

    data['corpora'].append({
        'path': folder_path,
        'label': label or os.path.basename(folder_path),
        'doc_count': doc_count,
        'investigation': investigation,
        'added': datetime.now().isoformat(),
        'last_used': datetime.now().isoformat(),
    })
    _save(data)


def register_file(file_path: str, investigation: str = ''):
    """Record that a single file was processed."""
    data = _load()
    file_path = os.path.abspath(file_path)

    for entry in data['individual_files']:
        if entry['path'] == file_path:
            entry['last_used'] = datetime.now().isoformat()
            _save(data)
            return

    data['individual_files'].append({
        'path': file_path,
        'name': os.path.basename(file_path),
        'investigation': investigation,
        'added': datetime.now().isoformat(),
        'last_used': datetime.now().isoformat(),
    })
    _save(data)


def get_all() -> dict:
    """Get all registered corpora and files."""
    return _load()


def get_corpus_summary() -> str:
    """Return a short string for the system prompt describing available corpora."""
    data = _load()
    corpora = data.get('corpora', [])
    files = data.get('individual_files', [])

    if not corpora and not files:
        return ''

    parts = []
    if corpora:
        parts.append('**Indexed document corpora:**')
        for c in corpora[-10:]:  # Most recent 10
            label = c.get('label', c.get('path', ''))
            count = c.get('doc_count', '?')
            inv = c.get('investigation', '')
            inv_note = f' (used in: {inv})' if inv else ''
            parts.append(f'  - `{label}` — {count} docs{inv_note} — path: {c["path"]}')

    if files:
        parts.append('**Individual files processed:**')
        for f in files[-10:]:
            parts.append(f'  - `{f["name"]}` — {f["path"]}')

    return '\n'.join(parts)


def remove_corpus(folder_path: str):
    """Remove a folder from memory."""
    data = _load()
    folder_path = os.path.abspath(folder_path)
    data['corpora'] = [c for c in data['corpora'] if c['path'] != folder_path]
    _save(data)
