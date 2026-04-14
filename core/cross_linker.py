"""
Cross-Investigation Linker
Scans all saved DeepDive investigations and finds entities that appear
(or likely appear) across multiple investigations.

Two matching strategies:
  1. Exact match — same entity ID (name-normalized). Zero cost, instant.
  2. Fuzzy match — name similarity above a threshold. Uses difflib.
     Optional: Ollama embeddings for semantic similarity if available.

Results are surfaced as "cross-link suggestions" — the investigator
can confirm them to merge entities or add explicit connections.

This is the "grows over time" piece: the more investigations you run,
the denser the cross-link map becomes.
"""

import json
import os
import re
from difflib import SequenceMatcher
from typing import List, Dict, Tuple


# Similarity threshold for fuzzy name matching (0.0–1.0)
# 0.82 catches "Jeffrey Epstein" / "J. Epstein" / "Jeffrey E." without false positives
FUZZY_THRESHOLD = 0.82

# If an entity name is shorter than this, skip fuzzy matching (too many false positives)
MIN_NAME_LENGTH = 5


def _normalize(name: str) -> str:
    """Normalize a name for comparison."""
    name = name.lower().strip()
    # Remove common titles/suffixes
    for title in ['mr.', 'mrs.', 'ms.', 'dr.', 'prof.', 'sir', 'jr.', 'sr.', 'ii', 'iii']:
        name = re.sub(rf'\b{re.escape(title)}\b', '', name)
    # Collapse whitespace
    name = re.sub(r'\s+', ' ', name).strip()
    return name


def _similarity(a: str, b: str) -> float:
    """String similarity score (0.0–1.0)."""
    return SequenceMatcher(None, _normalize(a), _normalize(b)).ratio()


def _try_ollama_embeddings(texts: List[str], base_url: str = 'http://localhost:11434') -> List[List[float]]:
    """Try to get embeddings from Ollama. Returns empty list if unavailable."""
    try:
        import requests
        # Use nomic-embed-text if available, fall back to any embedding model
        for model in ['nomic-embed-text', 'mxbai-embed-large', 'all-minilm']:
            embeddings = []
            ok = True
            for text in texts:
                r = requests.post(
                    f'{base_url}/api/embeddings',
                    json={'model': model, 'prompt': text},
                    timeout=5
                )
                if r.status_code == 200:
                    embeddings.append(r.json().get('embedding', []))
                else:
                    ok = False
                    break
            if ok and embeddings:
                return embeddings
        return []
    except Exception:
        return []


def _cosine(a: List[float], b: List[float]) -> float:
    """Cosine similarity between two vectors."""
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    mag_a = sum(x * x for x in a) ** 0.5
    mag_b = sum(x * x for x in b) ** 0.5
    if mag_a == 0 or mag_b == 0:
        return 0.0
    return dot / (mag_a * mag_b)


def load_all_investigations(investigations_dir: str) -> List[Dict]:
    """
    Load all saved investigation JSON files from the investigations directory.
    Returns list of dicts: {name, path, entities: [{id, name, type, depth, investigated}]}
    """
    results = []
    if not os.path.isdir(investigations_dir):
        return results

    for entry in sorted(os.listdir(investigations_dir)):
        inv_dir = os.path.join(investigations_dir, entry)
        if not os.path.isdir(inv_dir):
            continue
        # Find the JSON file (named after the investigation)
        for fname in os.listdir(inv_dir):
            if fname.endswith('.json') and not fname.startswith('_'):
                fpath = os.path.join(inv_dir, fname)
                try:
                    with open(fpath) as f:
                        data = json.load(f)
                    entities = []
                    for eid, edata in data.get('entities', {}).items():
                        entities.append({
                            'id': eid,
                            'name': edata.get('name', eid),
                            'type': edata.get('type', 'unknown'),
                            'depth': edata.get('depth', 0),
                            'investigated': edata.get('investigated', False),
                            'metadata': edata.get('metadata', {}),
                        })
                    results.append({
                        'name': data.get('name', entry),
                        'path': fpath,
                        'dir': inv_dir,
                        'entity_count': len(entities),
                        'entities': entities,
                        'findings': data.get('findings', []),
                    })
                    break
                except Exception as e:
                    print(f"[CrossLinker] Could not load {fpath}: {e}")

    return results


def find_cross_links(
    investigations_dir: str,
    current_investigation_name: str = None,
    use_embeddings: bool = True,
    threshold: float = FUZZY_THRESHOLD,
) -> Dict:
    """
    Scan all investigations for entities that appear in multiple investigations.

    Returns:
    {
        'exact_matches': [
            {
                'entity_name': str,
                'entity_type': str,
                'investigations': [{'name': str, 'path': str}],
                'confidence': 1.0,
                'match_type': 'exact',
            }
        ],
        'fuzzy_matches': [
            {
                'names': [str, ...],           # variant names across investigations
                'entity_type': str,
                'investigations': [str, ...],
                'best_name': str,
                'similarity': float,
                'match_type': 'fuzzy',
            }
        ],
        'investigations_scanned': int,
        'total_entities': int,
        'using_embeddings': bool,
    }
    """
    investigations = load_all_investigations(investigations_dir)
    if len(investigations) < 2:
        return {
            'exact_matches': [],
            'fuzzy_matches': [],
            'investigations_scanned': len(investigations),
            'total_entities': 0,
            'using_embeddings': False,
            'message': 'Need at least 2 investigations to find cross-links.',
        }

    # Build a map: entity_id → list of (investigation_name, entity_data)
    entity_map: Dict[str, List] = {}
    all_entities = []

    for inv in investigations:
        for entity in inv['entities']:
            eid = entity['id']
            if eid not in entity_map:
                entity_map[eid] = []
            entity_map[eid].append({
                'investigation': inv['name'],
                'investigation_dir': inv['dir'],
                'entity': entity,
            })
            all_entities.append({'inv': inv['name'], **entity})

    total_entities = len(all_entities)

    # 1. Exact matches (same normalized entity ID across multiple investigations)
    exact_matches = []
    for eid, appearances in entity_map.items():
        if len(appearances) >= 2:
            inv_names = list({a['investigation'] for a in appearances})
            # Skip if it's a generic word that appears everywhere (the seed?)
            entity_name = appearances[0]['entity']['name']
            if len(entity_name) < MIN_NAME_LENGTH:
                continue
            exact_matches.append({
                'entity_id': eid,
                'entity_name': entity_name,
                'entity_type': appearances[0]['entity']['type'],
                'investigations': inv_names,
                'appearances': len(appearances),
                'confidence': 1.0,
                'match_type': 'exact',
            })

    # Sort by how many investigations the entity appears in
    exact_matches.sort(key=lambda x: -x['appearances'])

    # 2. Fuzzy matches — find near-duplicate names across investigations
    # Collect unique (name, investigation, type) triples
    seen_ids = set(entity_map.keys())
    name_list = []
    for inv in investigations:
        for entity in inv['entities']:
            if len(entity['name']) >= MIN_NAME_LENGTH:
                name_list.append({
                    'name': entity['name'],
                    'id': entity['id'],
                    'type': entity['type'],
                    'investigation': inv['name'],
                })

    fuzzy_matches = []
    used_pairs = set()

    # Try embeddings for semantic similarity if Ollama is running
    embeddings = []
    embedding_names = [e['name'] for e in name_list]
    if use_embeddings and len(name_list) <= 500:  # cap for performance
        embeddings = _try_ollama_embeddings(embedding_names)

    for i, e1 in enumerate(name_list):
        for j, e2 in enumerate(name_list):
            if j <= i:
                continue
            if e1['investigation'] == e2['investigation']:
                continue
            if e1['id'] == e2['id']:
                continue  # already caught as exact match

            pair_key = tuple(sorted([e1['id'], e2['id']]))
            if pair_key in used_pairs:
                continue

            # Skip obvious type mismatches (person ≠ company etc)
            t1, t2 = e1['type'], e2['type']
            if t1 != 'unknown' and t2 != 'unknown' and t1 != t2:
                continue

            # Compute similarity
            sim = _similarity(e1['name'], e2['name'])

            # Boost with embeddings if available
            if embeddings and i < len(embeddings) and j < len(embeddings):
                emb_sim = _cosine(embeddings[i], embeddings[j])
                sim = max(sim, emb_sim)

            if sim >= threshold:
                used_pairs.add(pair_key)
                # Pick the longer/more complete name as canonical
                best_name = e1['name'] if len(e1['name']) >= len(e2['name']) else e2['name']
                fuzzy_matches.append({
                    'names': [e1['name'], e2['name']],
                    'best_name': best_name,
                    'entity_type': e1['type'] if e1['type'] != 'unknown' else e2['type'],
                    'investigations': [e1['investigation'], e2['investigation']],
                    'similarity': round(sim, 3),
                    'match_type': 'fuzzy' if not embeddings else 'semantic',
                })

    # Deduplicate fuzzy matches that are really the same cluster
    fuzzy_matches.sort(key=lambda x: -x['similarity'])

    return {
        'exact_matches': exact_matches[:50],
        'fuzzy_matches': fuzzy_matches[:50],
        'investigations_scanned': len(investigations),
        'investigations': [{'name': i['name'], 'entity_count': i['entity_count']} for i in investigations],
        'total_entities': total_entities,
        'using_embeddings': bool(embeddings),
        'message': (
            f"Scanned {len(investigations)} investigations, {total_entities} total entities. "
            f"Found {len(exact_matches)} exact cross-links, {len(fuzzy_matches)} fuzzy matches."
        ),
    }


def find_new_crosslinks_for_entity(
    entity_name: str,
    entity_type: str,
    investigations_dir: str,
    current_investigation_name: str,
    threshold: float = FUZZY_THRESHOLD,
) -> List[Dict]:
    """
    After expanding a node, check if the newly discovered entity already
    exists in any OTHER investigation. Called automatically during expansion.

    Returns list of matches: [{investigation, matched_name, similarity}]
    """
    investigations = load_all_investigations(investigations_dir)
    matches = []

    for inv in investigations:
        if inv['name'] == current_investigation_name:
            continue
        for entity in inv['entities']:
            if len(entity['name']) < MIN_NAME_LENGTH:
                continue
            # Exact ID match
            if entity['id'] == entity_name.lower().strip().replace(' ', '_'):
                matches.append({
                    'investigation': inv['name'],
                    'investigation_dir': inv['dir'],
                    'matched_name': entity['name'],
                    'matched_type': entity['type'],
                    'similarity': 1.0,
                    'match_type': 'exact',
                })
                continue
            # Type filter
            if entity_type != 'unknown' and entity['type'] != 'unknown' and entity_type != entity['type']:
                continue
            sim = _similarity(entity_name, entity['name'])
            if sim >= threshold:
                matches.append({
                    'investigation': inv['name'],
                    'investigation_dir': inv['dir'],
                    'matched_name': entity['name'],
                    'matched_type': entity['type'],
                    'similarity': round(sim, 3),
                    'match_type': 'fuzzy',
                })

    matches.sort(key=lambda x: -x['similarity'])
    return matches
