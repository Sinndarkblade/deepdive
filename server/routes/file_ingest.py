"""
File Ingestion — batched document processing.
Processes 5-10 documents at a time for large collections.
Reports progress to the user between batches.
"""

import os
import server.state as state
from graph import Entity, Connection
from extractors import extract_entities


BATCH_SIZE = 10  # Documents per batch
LARGE_THRESHOLD = 50  # Offer subagents above this count


def count_documents(folder_path):
    """Count processable documents in a folder."""
    if not os.path.isdir(folder_path):
        return 0, "Folder not found"
    extensions = {'.txt', '.md', '.pdf', '.doc', '.docx', '.csv', '.json', '.html', '.htm', '.xml', '.log'}
    count = 0
    for root, dirs, files in os.walk(folder_path):
        dirs[:] = [d for d in dirs if not d.startswith('.')]
        for f in files:
            if os.path.splitext(f)[1].lower() in extensions:
                count += 1
    return count, None


def get_document_list(folder_path):
    """Get list of processable documents with paths and sizes."""
    extensions = {'.txt', '.md', '.pdf', '.doc', '.docx', '.csv', '.json', '.html', '.htm', '.xml', '.log'}
    docs = []
    for root, dirs, files in os.walk(folder_path):
        dirs[:] = [d for d in dirs if not d.startswith('.')]
        for f in files:
            if os.path.splitext(f)[1].lower() in extensions:
                full = os.path.join(root, f)
                try:
                    size = os.path.getsize(full)
                    docs.append({'path': full, 'name': f, 'size': size})
                except:
                    pass
    return sorted(docs, key=lambda d: d['name'])


def process_batch(folder_path, batch_index=0, batch_size=BATCH_SIZE):
    """Process a single batch of documents from a folder.

    Returns:
        dict with: batch_index, total_docs, docs_processed, entities_found,
                   entities list for approval, has_more, progress_pct
    """
    if not state.GRAPH:
        return {'success': False, 'error': 'No investigation loaded'}

    docs = get_document_list(folder_path)
    total = len(docs)

    if total == 0:
        return {'success': True, 'total_docs': 0, 'entities_found': 0,
                'has_more': False, 'message': 'No processable documents found'}

    start = batch_index * batch_size
    end = min(start + batch_size, total)
    batch = docs[start:end]

    if not batch:
        return {'success': True, 'total_docs': total, 'entities_found': 0,
                'has_more': False, 'message': 'All documents processed',
                'batch_index': batch_index}

    # Read and combine text from this batch
    combined_text = ""
    files_processed = []
    for doc in batch:
        try:
            with open(doc['path'], 'r', errors='ignore') as f:
                text = f.read(10000)  # Cap per file
            combined_text += f"\n--- {doc['name']} ---\n{text}\n"
            files_processed.append(doc['name'])
        except:
            files_processed.append(f"{doc['name']} (error)")

    if not combined_text.strip():
        return {
            'success': True,
            'batch_index': batch_index,
            'total_docs': total,
            'docs_in_batch': len(batch),
            'files_processed': files_processed,
            'entities_found': 0,
            'has_more': end < total,
            'progress_pct': round(end / total * 100),
            'message': f'Batch {batch_index + 1}: {len(batch)} files read, no extractable text',
        }

    # Send to AI for entity extraction
    prompt = f"""DOCUMENT ANALYSIS for investigation: {state.GRAPH.name}

Processing batch {batch_index + 1} ({len(batch)} documents of {total} total).
Files: {', '.join(files_processed)}

DOCUMENT TEXT:
{combined_text[:12000]}

Extract ALL people, companies, locations, events, and money connections.
Output each as: ENTITY_NAME | ENTITY_TYPE | RELATIONSHIP | CONFIDENCE (high/medium/low)"""

    try:
        response, _ = state.BRIDGE.research(state.GRAPH.name, "document_analysis", prompt)
    except Exception as e:
        return {'success': False, 'error': f'AI error: {e}'}

    if not response or response.startswith("Error"):
        return {'success': False, 'error': f'AI returned: {response}'}

    extracted = extract_entities(response)

    # Stage entities (don't auto-add)
    entity_list = []
    for name, etype, rel, conf in extracted:
        entity_id = name.lower().replace(' ', '_')
        entity_list.append({
            'name': name,
            'type': etype,
            'relationship': rel,
            'confidence': conf,
            'entity_id': entity_id,
            'is_duplicate': entity_id in state.GRAPH.entities,
        })

    return {
        'success': True,
        'batch_index': batch_index,
        'total_docs': total,
        'docs_in_batch': len(batch),
        'files_processed': files_processed,
        'entities_found': len(entity_list),
        'entities': entity_list,
        'has_more': end < total,
        'progress_pct': round(end / total * 100),
        'next_batch_index': batch_index + 1 if end < total else None,
        'message': f'Batch {batch_index + 1}: {len(batch)} files → {len(entity_list)} entities found',
    }


def is_large_collection(folder_path):
    """Check if collection is large enough to warrant subagent offer."""
    count, error = count_documents(folder_path)
    if error:
        return False, 0, error
    return count >= LARGE_THRESHOLD, count, None
