"""
Approval Workflow — staged entity management.
Entities found during investigation are held in a pending queue.
User reviews and approves/rejects before they're added to the graph.
"""

import json
import server.state as state
from graph import Entity, Connection


# Pending entities waiting for approval — keyed by a batch ID
_pending_batches = {}
_batch_counter = 0


def stage_entities(entities, connections, source_label):
    """Stage a batch of entities for user approval.
    Returns batch_id and the formatted list for display.

    Args:
        entities: list of (name, type, relationship, confidence) tuples
        connections: list of (source_id, target_id) pairs for each entity
        source_label: where these came from (e.g., "Expansion of Elon Musk")

    Returns:
        (batch_id, entity_list) where entity_list is formatted for display
    """
    global _batch_counter
    _batch_counter += 1
    batch_id = f"batch_{_batch_counter}"

    items = []
    for i, (name, etype, rel, conf) in enumerate(entities):
        entity_id = name.lower().replace(' ', '_')
        is_duplicate = entity_id in state.GRAPH.entities if state.GRAPH else False
        src_id, tgt_id = connections[i] if i < len(connections) else ('', '')

        items.append({
            'index': i,
            'name': name,
            'type': etype,
            'relationship': rel,
            'confidence': conf,
            'entity_id': entity_id,
            'source_id': src_id,
            'target_id': tgt_id,
            'is_duplicate': is_duplicate,
        })

    _pending_batches[batch_id] = {
        'items': items,
        'source': source_label,
    }

    # Keep only last 20 batches
    if len(_pending_batches) > 20:
        oldest = sorted(_pending_batches.keys())[0]
        del _pending_batches[oldest]

    return batch_id, items


def approve_entities(batch_id, approved_indices=None):
    """Approve entities from a staged batch and add them to the graph.

    Args:
        batch_id: the batch to approve from
        approved_indices: list of indices to approve, or None for all

    Returns:
        (added_count, skipped_count, error)
    """
    if not state.GRAPH:
        return 0, 0, "No investigation loaded"

    batch = _pending_batches.get(batch_id)
    if not batch:
        return 0, 0, f"Batch {batch_id} not found or expired"

    items = batch['items']
    if approved_indices is None:
        # Approve all
        to_add = items
    else:
        to_add = [items[i] for i in approved_indices if 0 <= i < len(items)]

    added = 0
    skipped = 0
    for item in to_add:
        new_entity = Entity(item['name'], item['type'])
        new_entity.depth = 2
        is_new = state.GRAPH.add_entity(new_entity)
        if is_new:
            added += 1
        else:
            skipped += 1
        # Add connection
        if item['source_id']:
            state.GRAPH.add_connection(
                Connection(item['source_id'], new_entity.id,
                           item['relationship'], item['confidence']))

    if added:
        state.GRAPH.save(state.INV_PATH)
        from server.routes.investigation import _rebuild_board
        _rebuild_board()

    # Clean up the batch
    del _pending_batches[batch_id]

    return added, len(items) - len(to_add), None


def reject_batch(batch_id):
    """Reject/discard a pending batch entirely."""
    if batch_id in _pending_batches:
        del _pending_batches[batch_id]
        return True
    return False


def get_pending_batch(batch_id):
    """Get a pending batch for display."""
    return _pending_batches.get(batch_id)
