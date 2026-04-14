#!/usr/bin/env python3
"""
Utility functions for DeepDive.
"""

import re


def extract_subject(prompt: str) -> str:
    """Extract the main subject from a user's investigation prompt.

    Examples:
    'trace the timeline of Amazon Web Services from concept to now' -> 'Amazon Web Services'
    'investigate Bill Gates connections to philanthropy' -> 'Bill Gates'
    'deep dive on Tesla corruption scandals' -> 'Tesla'
    'Apple' -> 'Apple'
    """
    text = prompt.strip()

    # If it's short (3 words or less), it IS the subject
    if len(text.split()) <= 3:
        return text

    # Remove common instruction prefixes
    prefixes = [
        r'^(?:do\s+)?(?:a\s+)?(?:complete|full|deep|exhaustive|thorough)?\s*(?:investigation|dive|search|trace|research|analysis|timeline|report)\s+(?:on|of|into|about|for)\s+',
        r'^investigate\s+',
        r'^trace\s+(?:the\s+)?(?:complete\s+)?(?:timeline\s+)?(?:of\s+)?',
        r'^deep\s*dive\s+(?:on|into)?\s*',
        r'^look\s+(?:into|up|at)\s+',
        r'^find\s+(?:everything|all|connections|info)\s+(?:about|on|for)\s+',
        r'^research\s+',
        r'^search\s+(?:for\s+)?',
        r'^who\s+is\s+',
        r'^what\s+is\s+',
        r'^tell\s+me\s+(?:about|everything)\s+',
    ]

    cleaned = text
    for pattern in prefixes:
        cleaned = re.sub(pattern, '', cleaned, flags=re.I).strip()

    # If cleaning removed too much, use original
    if len(cleaned) < 2:
        cleaned = text

    # Take everything up to common suffix patterns
    suffixes = [
        r'\s+from\s+(?:the\s+)?(?:beginning|start|concept|founding).*$',
        r'\s+(?:and|including)\s+(?:all|every|their)\s+.*$',
        r'\s+(?:trace|follow|find|show|list|map)\s+.*$',
        r'\s+connections?\s+to\s+.*$',
        r'\s+(?:from|between|since|until|through)\s+\d{4}.*$',
    ]

    for pattern in suffixes:
        cleaned = re.sub(pattern, '', cleaned, flags=re.I).strip()

    # Cap at 60 chars for the title
    if len(cleaned) > 60:
        # Try to cut at a word boundary
        cleaned = cleaned[:60].rsplit(' ', 1)[0]

    return cleaned if cleaned else text[:50]
