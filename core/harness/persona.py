"""
Persona Management — handles investigator and user identity.
Loads/saves names from settings. Provides identity context for the harness.
"""

import json
import os
from pathlib import Path


SETTINGS_FILE = Path.home() / ".deepdive" / "settings.json"


def load_persona():
    """Load persona settings. Returns dict with investigator_name, user_name."""
    defaults = {
        'investigator_name': '',
        'user_name': '',
        'first_run_complete': False,
    }
    if SETTINGS_FILE.exists():
        try:
            with open(SETTINGS_FILE) as f:
                data = json.load(f)
            return {
                'investigator_name': data.get('investigator_name', ''),
                'user_name': data.get('user_name', ''),
                'first_run_complete': data.get('first_run_complete', False),
            }
        except:
            pass
    return defaults


def save_persona(investigator_name, user_name):
    """Save persona names to settings."""
    SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    settings = {}
    if SETTINGS_FILE.exists():
        try:
            with open(SETTINGS_FILE) as f:
                settings = json.load(f)
        except:
            pass
    settings['investigator_name'] = investigator_name
    settings['user_name'] = user_name
    settings['first_run_complete'] = True
    with open(SETTINGS_FILE, 'w') as f:
        json.dump(settings, f, indent=2)
    os.chmod(SETTINGS_FILE, 0o600)


def is_first_run():
    """Check if this is the user's first time using DeepDive."""
    persona = load_persona()
    return not persona['first_run_complete']
