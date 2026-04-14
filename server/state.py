"""
DeepDive Server — Shared State
All global state lives here. Route modules import from this module.
"""

import os
import sys

# Add core to path
_root = os.path.join(os.path.dirname(__file__), '..')
sys.path.insert(0, os.path.join(_root, 'core'))
sys.path.insert(0, os.path.join(_root, 'cli'))
sys.path.insert(0, os.path.join(_root, 'src'))

from auth import DeepDiveBridge
from plugins import PluginManager

# ── Globals ──

GRAPH = None          # Current InvestigationGraph
INV_PATH = None       # Path to current investigation directory
ENGINES = []          # Search engines (DDG, SearXNG, etc.)
DATASET_PATH = None   # Path to scanned document folder

# ── Singletons ──

BRIDGE = DeepDiveBridge()

PLUGIN_MGR = PluginManager()
PLUGIN_MGR.load_all()

# ── Colors ──

COLORS = {
    'person':     '#E11D48',
    'company':    '#2563EB',
    'location':   '#059669',
    'event':      '#D97706',
    'money':      '#7C3AED',
    'concept':    '#0891B2',
    'government': '#EA580C',
    'document':   '#6366F1',
    'unknown':    '#6B7280',
}


def get_root():
    """Get the project root directory."""
    return _root


def get_investigations_root():
    """Get the investigations directory."""
    return os.path.join(_root, 'investigations')


def get_investigations_dir():
    """Alias for get_investigations_root — used by cross_linker."""
    return get_investigations_root()


def get_frontend_dir():
    """Get the frontend directory."""
    return os.path.join(_root, 'frontend')
