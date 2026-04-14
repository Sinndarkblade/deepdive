"""
Entity Extractor — Parses AI model responses into entities and connections.
Works with ANY model's output — looks for patterns, not specific formats.
"""

import re
from typing import List, Tuple

# Entity type keywords
TYPE_KEYWORDS = {
    'person': ['ceo', 'founder', 'president', 'director', 'chairman', 'officer', 'scientist',
               'researcher', 'engineer', 'manager', 'professor', 'dr.', 'mr.', 'mrs.', 'ms.'],
    'company': ['inc', 'llc', 'corp', 'ltd', 'company', 'startup', 'firm', 'group',
                'ventures', 'capital', 'fund', 'labs', 'technologies', 'institute'],
    'location': ['city', 'state', 'country', 'based in', 'headquartered', 'located',
                 'office in', 'san francisco', 'new york', 'london', 'paris', 'tokyo', 'seattle'],
    'money': ['$', 'billion', 'million', 'invested', 'funding', 'raised', 'revenue', 'valued'],
    'event': ['founded', 'launched', 'acquired', 'merged', 'ipo', 'announced', 'crisis', 'sued'],
    'government': ['fbi', 'cia', 'sec', 'ftc', 'congress', 'senate', 'department', 'agency', 'federal'],
}

# Relationship keywords
REL_KEYWORDS = {
    'works_for': ['works for', 'employed by', 'employee of', 'works at', 'joined'],
    'leads': ['ceo of', 'president of', 'leads', 'runs', 'heads', 'directs', 'chief'],
    'founded': ['founded', 'co-founded', 'started', 'created', 'established'],
    'invested_in': ['invested in', 'backed', 'funded', 'financial support', 'put money'],
    'owns': ['owns', 'acquired', 'purchased', 'subsidiary', 'parent company'],
    'partnered_with': ['partnered', 'partnership', 'collaboration', 'alliance', 'deal with'],
    'located_at': ['based in', 'headquartered in', 'located in', 'offices in'],
    'met_with': ['met with', 'meeting', 'spoke with', 'conversation with'],
    'related_to': ['connected to', 'associated with', 'linked to', 'related to', 'tied to'],
    'formerly_at': ['former', 'previously', 'left', 'departed', 'ex-'],
    'rival_of': ['competitor', 'rival', 'competes with', 'competing'],
    'board_member': ['board member', 'board of directors', 'sits on board'],
    'married_to': ['married', 'spouse', 'wife', 'husband', 'partner of'],
    'sued_by': ['lawsuit', 'sued', 'legal action', 'litigation'],
}


JUNK_NAMES = {
    'now', 'connection', 'each', 'make', 'for', 'just', 'also', 'very', 'but',
    'the', 'this', 'that', 'with', 'from', 'into', 'about', 'after', 'before',
    'here', 'there', 'then', 'than', 'both', 'well', 'only', 'over', 'such',
    'some', 'more', 'most', 'many', 'much', 'other', 'these', 'those', 'they',
    'their', 'what', 'when', 'where', 'which', 'who', 'how', 'not', 'all',
    'been', 'have', 'has', 'had', 'will', 'would', 'could', 'should', 'may',
    'can', 'did', 'does', 'was', 'were', 'are', 'its', 'yes', 'and', 'yet',
    'none', 'note', 'see', 'etc', 'per', 'via', 'any', 'new', 'old', 'key',
    'high', 'low', 'medium', 'unknown', 'n/a', 'na', 'tbd', 'confidential',
    'entity', 'type', 'relationship', 'confidence', 'name', 'description',
    'summary', 'details', 'information', 'data', 'source', 'result', 'results',
    'list', 'table', 'section', 'part', 'item', 'number', 'total',
    'president', 'vice president', 'human resources', 'business operations',
    'cfo', 'ceo', 'cto', 'coo',  # titles without names
}


def is_junk_name(name: str) -> bool:
    """Filter out common English words and generic terms extracted as entity names."""
    cleaned = name.strip().strip('*').strip('#').strip('-').strip()
    if not cleaned:
        return True
    if cleaned.lower() in JUNK_NAMES:
        return True
    # Single common word
    if len(cleaned.split()) == 1 and len(cleaned) < 4:
        return True
    # Starts with ** (markdown bold artifacts)
    if cleaned.startswith('**') or cleaned.endswith('**'):
        cleaned = cleaned.strip('*')
        if cleaned.lower() in JUNK_NAMES or not cleaned:
            return True
    return False


def extract_structured(response: str) -> List[Tuple[str, str, str, float]]:
    """
    Extract structured entities from the pipe-delimited format.
    Returns: [(entity_name, entity_type, relationship, confidence)]
    """
    results = []
    for line in response.split('\n'):
        # Look for ENTITY_NAME | ENTITY_TYPE | RELATIONSHIP | CONFIDENCE
        parts = [p.strip() for p in line.split('|')]
        if len(parts) >= 3:
            name = parts[0].strip().strip('*').strip('-').strip()
            # Strip markdown artifacts, leading numbers, bullets
            name = re.sub(r'^\*+\s*', '', name).strip()
            name = re.sub(r'\*+$', '', name).strip()
            name = re.sub(r'^\d+\.\s*', '', name).strip()
            name = re.sub(r'^[-•]\s*', '', name).strip()
            etype = parts[1].lower().strip() if len(parts) > 1 else 'unknown'
            rel = parts[2].lower().replace(' ', '_').strip() if len(parts) > 2 else 'related_to'
            conf_str = parts[3].lower() if len(parts) > 3 else 'medium'

            # Skip header-like lines and example lines
            if any(skip in name.lower() for skip in ['entity_name', 'entity name', '---', '===', 'format', 'example']):
                continue

            # Skip URLs and domain names masquerading as entities
            if re.search(r'https?://|www\.|\.com|\.org|\.net|\.io|\.gov', name, re.I):
                continue

            # Skip pure year strings and numeric timestamps (e.g. "2026", "20041212212717")
            if re.match(r'^\d{4,}$', name):
                continue

            # Skip names that are mostly digits or garbled (>40% digits)
            digit_ratio = sum(c.isdigit() for c in name) / max(len(name), 1)
            if digit_ratio > 0.4 and len(name) > 4:
                continue

            # Skip junk names
            if is_junk_name(name):
                continue

            # Parse confidence
            if 'high' in conf_str:
                conf = 0.9
            elif 'low' in conf_str:
                conf = 0.4
            else:
                conf = 0.7

            # Validate entity type
            valid_types = ['person', 'company', 'location', 'event', 'money', 'document', 'government', 'concept']
            if etype not in valid_types:
                etype = guess_type(name)

            if name and len(name) > 1 and len(name) < 100:
                results.append((name, etype, rel, conf))

    return results


def extract_freeform(response: str) -> List[Tuple[str, str, str, float]]:
    """
    Extract entities from freeform text when the model doesn't follow the format.
    Uses pattern matching and NER-like heuristics.
    """
    results = []

    # Find capitalized multi-word phrases (likely proper nouns = entities)
    # Pattern: 2-5 consecutive capitalized words
    proper_nouns = re.findall(r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,4})\b', response)

    seen = set()
    for name in proper_nouns:
        name_lower = name.lower()
        if name_lower in seen or len(name) < 3:
            continue
        seen.add(name_lower)

        # Skip junk names (same filter as structured)
        if is_junk_name(name):
            continue

        # Skip common words that get capitalized at sentence starts
        skip_words = {'the', 'this', 'that', 'these', 'those', 'they', 'their', 'there',
                      'what', 'when', 'where', 'which', 'who', 'how', 'also', 'however',
                      'additionally', 'furthermore', 'moreover', 'key', 'major', 'main',
                      'first', 'then', 'next', 'okay', 'wait', 'maybe', 'let', 'other',
                      'events', 'money', 'falcon', 'i', 'so', 'sure', 'still'}
        if name_lower.split()[0] in skip_words:
            continue

        etype = guess_type(name)
        rel = guess_relationship(name, response)
        results.append((name, etype, rel, 0.5))

    return results


def guess_type(name: str) -> str:
    """Guess entity type from its name."""
    name_lower = name.lower()
    for etype, keywords in TYPE_KEYWORDS.items():
        if any(kw in name_lower for kw in keywords):
            return etype
    # If it looks like a person name (2-3 words, no corp keywords)
    words = name.split()
    if 2 <= len(words) <= 3 and all(w[0].isupper() for w in words):
        return 'person'
    return 'unknown'


def guess_relationship(name: str, context: str) -> str:
    """Guess relationship type from surrounding context."""
    # Find the sentence containing this name
    sentences = context.split('.')
    relevant = [s for s in sentences if name in s]
    if not relevant:
        return 'related_to'

    text = relevant[0].lower()
    for rel, keywords in REL_KEYWORDS.items():
        if any(kw in text for kw in keywords):
            return rel

    return 'related_to'


def extract_entities(response: str) -> List[Tuple[str, str, str, float]]:
    """
    Main extraction function. Tries structured first, falls back to freeform.
    Returns: [(entity_name, entity_type, relationship, confidence)]
    """
    # Try structured extraction first
    structured = extract_structured(response)
    if len(structured) >= 3:
        return structured

    # Fall back to freeform
    freeform = extract_freeform(response)

    # Combine, preferring structured when available
    all_entities = structured + freeform

    # Deduplicate by name
    seen = {}
    for name, etype, rel, conf in all_entities:
        key = name.lower().strip()
        if key not in seen or conf > seen[key][3]:
            seen[key] = (name, etype, rel, conf)

    return list(seen.values())
