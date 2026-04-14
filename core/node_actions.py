#!/usr/bin/env python3
"""
Node Actions — prune, pin, note for individual graph nodes.
"""


def prune_node(graph, entity_id):
    """Remove a node and its exclusive connections from the graph."""
    if entity_id not in graph.entities:
        return False, "Entity not found"

    # Remove connections involving this entity
    graph.connections = [
        c for c in graph.connections
        if c.source_id != entity_id and c.target_id != entity_id
    ]

    # Remove the entity
    del graph.entities[entity_id]

    # Remove from search queue
    graph.search_queue = [eid for eid in graph.search_queue if eid != entity_id]

    return True, None


def pin_node(graph, entity_id):
    """Toggle pin/bookmark on a node."""
    entity = graph.entities.get(entity_id)
    if not entity:
        return False, "Entity not found"

    pinned = entity.metadata.get('pinned', False)
    entity.metadata['pinned'] = not pinned
    return True, not pinned


def add_note(graph, entity_id, note):
    """Add user annotation to a node."""
    entity = graph.entities.get(entity_id)
    if not entity:
        return False, "Entity not found"

    notes = entity.metadata.get('notes', [])
    notes.append(note)
    entity.metadata['notes'] = notes
    return True, len(notes)


def get_pinned(graph):
    """Get all pinned nodes."""
    return [
        {'id': eid, 'name': e.name, 'type': e.type}
        for eid, e in graph.entities.items()
        if e.metadata.get('pinned', False)
    ]
