"""
DeepDive Graph Engine
The core data structure that holds all entities and connections.
"""

import json
import os
from datetime import datetime
from collections import defaultdict

class Entity:
    """A node in the investigation graph."""
    def __init__(self, name, entity_type="unknown", metadata=None):
        self.id = name.lower().strip().replace(" ", "_")
        self.name = name
        self.type = entity_type  # person, company, location, event, concept, money, document
        self.metadata = metadata or {}
        self.discovered_at = datetime.now().isoformat()
        self.sources = []
        self.depth = 0  # how many hops from the seed
        self.investigated = False  # has this entity been expanded?

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'type': self.type,
            'metadata': self.metadata,
            'discovered_at': self.discovered_at,
            'sources': self.sources,
            'depth': self.depth,
            'investigated': self.investigated,
        }


class Connection:
    """An edge in the investigation graph."""
    def __init__(self, source_id, target_id, relationship, confidence=0.5, metadata=None):
        self.source_id = source_id
        self.target_id = target_id
        self.relationship = relationship  # "works_for", "met_with", "funded_by", etc.
        self.confidence = confidence  # 0.0 to 1.0
        self.metadata = metadata or {}
        self.discovered_at = datetime.now().isoformat()
        self.sources = []
        self.time_period = None  # when this connection was active

    def to_dict(self):
        return {
            'source': self.source_id,
            'target': self.target_id,
            'relationship': self.relationship,
            'confidence': self.confidence,
            'metadata': self.metadata,
            'discovered_at': self.discovered_at,
            'sources': self.sources,
            'time_period': self.time_period,
        }


class InvestigationGraph:
    """The full investigation graph with entities and connections."""

    def __init__(self, name, seed_entity=None):
        self.name = name
        self.created_at = datetime.now().isoformat()
        self.entities = {}  # id -> Entity
        self.connections = []  # list of Connection
        self.search_queue = []  # entities to investigate next
        self.search_history = []  # what we've already searched
        self.findings = []  # notable discoveries
        self.gaps = []  # suspicious missing connections

        if seed_entity:
            self.add_entity(seed_entity)
            self.search_queue.append(seed_entity.id)

    def add_entity(self, entity):
        """Add an entity to the graph. Returns True if new."""
        if entity.id not in self.entities:
            self.entities[entity.id] = entity
            return True
        else:
            # Merge metadata
            existing = self.entities[entity.id]
            existing.metadata.update(entity.metadata)
            existing.sources.extend(entity.sources)
            return False

    def add_connection(self, connection):
        """Add a connection. Blocks self-loops and deduplicates same source→target pairs."""
        # Block self-loops
        if connection.source_id == connection.target_id:
            return False

        # Deduplicate: same source→target, keep best relationship
        for existing in self.connections:
            if (existing.source_id == connection.source_id and
                existing.target_id == connection.target_id and
                existing.relationship == connection.relationship):
                # Update confidence if higher
                if connection.confidence > existing.confidence:
                    existing.confidence = connection.confidence
                existing.sources.extend(connection.sources)
                return False
        self.connections.append(connection)
        return True

    def get_connections_for(self, entity_id):
        """Get all connections involving an entity."""
        results = []
        for c in self.connections:
            if c.source_id == entity_id or c.target_id == entity_id:
                results.append(c)
        return results

    def get_neighbors(self, entity_id):
        """Get all entities directly connected to this one."""
        neighbors = set()
        for c in self.connections:
            if c.source_id == entity_id:
                neighbors.add(c.target_id)
            elif c.target_id == entity_id:
                neighbors.add(c.source_id)
        return neighbors

    def get_next_to_investigate(self):
        """Get the next entity to investigate (breadth-first by depth)."""
        # Sort queue by depth (shallowest first)
        uninvestigated = [
            eid for eid in self.search_queue
            if eid in self.entities and not self.entities[eid].investigated
        ]
        if not uninvestigated:
            return None
        # Prioritize by depth (breadth-first)
        uninvestigated.sort(key=lambda eid: self.entities[eid].depth)
        return uninvestigated[0]

    def mark_investigated(self, entity_id):
        """Mark an entity as fully investigated."""
        if entity_id in self.entities:
            self.entities[entity_id].investigated = True
            self.search_history.append({
                'entity_id': entity_id,
                'timestamp': datetime.now().isoformat()
            })

    def detect_gaps(self):
        """Find suspicious missing connections with suspicion scoring.
        Higher score = more suspicious gap."""
        self.gaps = []
        entity_ids = list(self.entities.keys())
        seen_keys = set()

        for a_id in entity_ids:
            a_neighbors = self.get_neighbors(a_id)
            for b_id in a_neighbors:
                b_neighbors = self.get_neighbors(b_id)
                for c_id in b_neighbors:
                    if c_id != a_id and c_id not in a_neighbors:
                        key = tuple(sorted([a_id, c_id]))
                        if key in seen_keys:
                            continue
                        seen_keys.add(key)

                        a = self.entities.get(a_id)
                        b = self.entities.get(b_id)
                        c = self.entities.get(c_id)
                        if not a or not c or not b:
                            continue

                        # Score suspicion
                        score = 0
                        reasons = []

                        # Same type = more suspicious
                        if a.type == c.type:
                            score += 2
                            reasons.append(f"both are {a.type}s")

                        # Both are people or companies = most suspicious
                        if a.type in ('person', 'company') and c.type in ('person', 'company'):
                            score += 3
                            reasons.append("people/companies should know each other")

                        # Multiple shared bridges = very suspicious
                        shared_bridges = a_neighbors & self.get_neighbors(c_id)
                        if len(shared_bridges) > 1:
                            score += len(shared_bridges) * 2
                            bridge_names = [self.entities[bid].name for bid in shared_bridges if bid in self.entities]
                            reasons.append(f"{len(shared_bridges)} shared connections: {', '.join(bridge_names[:3])}")

                        # Money involved = suspicious
                        a_has_money = any(
                            self.entities.get(nid, None) and self.entities[nid].type == 'money'
                            for nid in a_neighbors
                        )
                        c_has_money = any(
                            self.entities.get(nid, None) and self.entities[nid].type == 'money'
                            for nid in self.get_neighbors(c_id)
                        )
                        if a_has_money and c_has_money:
                            score += 3
                            reasons.append("both have financial connections")

                        # High connection count on both sides = suspicious
                        a_conns = len(self.get_connections_for(a_id))
                        c_conns = len(self.get_connections_for(c_id))
                        if a_conns > 5 and c_conns > 5:
                            score += 2
                            reasons.append(f"both heavily connected ({a_conns} + {c_conns})")

                        if score >= 2:  # Only keep meaningful gaps
                            gap = {
                                'entity_a': a_id,
                                'entity_b': b_id,
                                'entity_c': c_id,
                                'a_name': a.name,
                                'b_name': b.name,
                                'c_name': c.name,
                                'reason': f'{a.name} and {c.name} both connect to {b.name} but not to each other',
                                'details': '; '.join(reasons),
                                'score': score,
                                'types': f"{a.type}/{c.type}",
                                'researched': False,
                            }
                            self.gaps.append(gap)

        # Sort by suspicion score
        self.gaps.sort(key=lambda g: -g.get('score', 0))
        return self.gaps

    def get_stats(self):
        """Get investigation statistics."""
        type_counts = defaultdict(int)
        for e in self.entities.values():
            type_counts[e.type] += 1

        rel_counts = defaultdict(int)
        for c in self.connections:
            rel_counts[c.relationship] += 1

        investigated = sum(1 for e in self.entities.values() if e.investigated)
        pending = sum(1 for e in self.entities.values() if not e.investigated)

        return {
            'total_entities': len(self.entities),
            'total_connections': len(self.connections),
            'entity_types': dict(type_counts),
            'relationship_types': dict(rel_counts),
            'investigated': investigated,
            'pending': pending,
            'depth_max': max((e.depth for e in self.entities.values()), default=0),
            'gaps_found': len(self.gaps),
        }

    def search(self, query):
        """Search the graph for entities matching a query."""
        query_lower = query.lower()
        results = []
        for entity in self.entities.values():
            score = 0
            if query_lower in entity.name.lower():
                score += 10
            if query_lower in entity.type.lower():
                score += 5
            for key, val in entity.metadata.items():
                if query_lower in str(val).lower():
                    score += 3
            if score > 0:
                results.append((entity, score))

        results.sort(key=lambda x: -x[1])
        return results

    def save(self, directory):
        """Save the investigation to JSON files."""
        os.makedirs(directory, exist_ok=True)

        data = {
            'name': self.name,
            'created_at': self.created_at,
            'saved_at': datetime.now().isoformat(),
            'entities': {eid: e.to_dict() for eid, e in self.entities.items()},
            'connections': [c.to_dict() for c in self.connections],
            'findings': self.findings,
            'gaps': self.gaps,
            'search_history': self.search_history,
            'stats': self.get_stats(),
        }

        filepath = os.path.join(directory, f"{self.name.replace(' ', '_')}.json")
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2, default=str)
        return filepath

    @classmethod
    def load(cls, filepath):
        """Load an investigation from JSON."""
        with open(filepath) as f:
            data = json.load(f)

        graph = cls(data['name'])
        graph.created_at = data['created_at']

        for eid, edata in data['entities'].items():
            entity = Entity(edata['name'], edata['type'], edata.get('metadata', {}))
            entity.id = eid
            entity.discovered_at = edata.get('discovered_at', '')
            entity.sources = edata.get('sources', [])
            entity.depth = edata.get('depth', 0)
            entity.investigated = edata.get('investigated', False)
            graph.entities[eid] = entity

        for cdata in data['connections']:
            conn = Connection(
                cdata['source'], cdata['target'],
                cdata['relationship'], cdata.get('confidence', 0.5),
                cdata.get('metadata', {})
            )
            conn.discovered_at = cdata.get('discovered_at', '')
            conn.sources = cdata.get('sources', [])
            conn.time_period = cdata.get('time_period')
            graph.connections.append(conn)

        graph.findings = data.get('findings', [])
        graph.gaps = data.get('gaps', [])
        graph.search_history = data.get('search_history', [])

        return graph
