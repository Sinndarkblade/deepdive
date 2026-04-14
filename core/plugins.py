#!/usr/bin/env python3
"""
DeepDive Plugin System — load and manage community plugins.

Plugin structure:
~/.deepdive/plugins/
├── plugin-name/
│   ├── plugin.json          # Manifest
│   ├── search_sources/      # Custom data source connectors
│   ├── views/               # Custom visualization types
│   ├── prompts/             # Custom investigation prompts
│   ├── extractors/          # Custom entity extractors
│   └── reports/             # Custom report templates
"""

import json
import os
import importlib.util
from pathlib import Path
from typing import Dict, List, Optional


PLUGINS_DIR = Path.home() / ".deepdive" / "plugins"


class Plugin:
    """Represents a loaded plugin."""

    def __init__(self, path: str, manifest: Dict):
        self.path = path
        self.name = manifest.get('name', os.path.basename(path))
        self.description = manifest.get('description', '')
        self.version = manifest.get('version', '0.0.0')
        self.author = manifest.get('author', 'Unknown')
        self.enabled = manifest.get('enabled', True)
        self.hooks = manifest.get('hooks', {})
        self.manifest = manifest

    def to_dict(self) -> Dict:
        return {
            'name': self.name,
            'description': self.description,
            'version': self.version,
            'author': self.author,
            'enabled': self.enabled,
            'path': self.path,
            'hooks': list(self.hooks.keys()),
        }


class PluginManager:
    """Discovers, loads, and manages plugins."""

    def __init__(self):
        self.plugins = {}  # name -> Plugin
        self.search_sources = []
        self.extractors = []
        self.views = []
        self.prompts = {}

    def discover(self) -> List[Plugin]:
        """Scan the plugins directory and load manifests."""
        PLUGINS_DIR.mkdir(parents=True, exist_ok=True)

        for entry in PLUGINS_DIR.iterdir():
            if not entry.is_dir():
                continue

            manifest_path = entry / "plugin.json"
            if not manifest_path.exists():
                continue

            try:
                with open(manifest_path) as f:
                    manifest = json.load(f)
                plugin = Plugin(str(entry), manifest)
                self.plugins[plugin.name] = plugin
            except Exception as e:
                print(f"[Plugins] Error loading {entry.name}: {e}")

        return list(self.plugins.values())

    def load_plugin(self, name: str) -> bool:
        """Load a plugin's components."""
        plugin = self.plugins.get(name)
        if not plugin or not plugin.enabled:
            return False

        plugin_path = Path(plugin.path)

        # Load search sources
        sources_dir = plugin_path / "search_sources"
        if sources_dir.exists():
            for py_file in sources_dir.glob("*.py"):
                try:
                    spec = importlib.util.spec_from_file_location(
                        f"plugin_{name}_{py_file.stem}", py_file)
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
                    if hasattr(module, 'SearchSource'):
                        self.search_sources.append(module.SearchSource())
                        print(f"[Plugins] Loaded search source: {name}/{py_file.stem}")
                except Exception as e:
                    print(f"[Plugins] Error loading search source {py_file}: {e}")

        # Load custom prompts
        prompts_dir = plugin_path / "prompts"
        if prompts_dir.exists():
            for txt_file in prompts_dir.glob("*.txt"):
                try:
                    with open(txt_file) as f:
                        self.prompts[f"{name}/{txt_file.stem}"] = f.read()
                    print(f"[Plugins] Loaded prompt: {name}/{txt_file.stem}")
                except Exception as e:
                    print(f"[Plugins] Error loading prompt {txt_file}: {e}")

        # Load custom extractors
        extractors_dir = plugin_path / "extractors"
        if extractors_dir.exists():
            for py_file in extractors_dir.glob("*.py"):
                try:
                    spec = importlib.util.spec_from_file_location(
                        f"plugin_{name}_{py_file.stem}", py_file)
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
                    if hasattr(module, 'EntityExtractor'):
                        self.extractors.append(module.EntityExtractor())
                        print(f"[Plugins] Loaded extractor: {name}/{py_file.stem}")
                except Exception as e:
                    print(f"[Plugins] Error loading extractor {py_file}: {e}")

        return True

    def load_all(self):
        """Discover and load all enabled plugins."""
        self.discover()
        for name, plugin in self.plugins.items():
            if plugin.enabled:
                self.load_plugin(name)
        print(f"[Plugins] {len(self.plugins)} plugins found, {len(self.search_sources)} search sources, {len(self.prompts)} prompts")

    def list_plugins(self) -> List[Dict]:
        """Return all plugins as dicts for the API."""
        return [p.to_dict() for p in self.plugins.values()]

    def toggle_plugin(self, name: str) -> Optional[bool]:
        """Enable/disable a plugin."""
        plugin = self.plugins.get(name)
        if not plugin:
            return None
        plugin.enabled = not plugin.enabled

        # Update manifest on disk
        manifest_path = Path(plugin.path) / "plugin.json"
        try:
            with open(manifest_path) as f:
                manifest = json.load(f)
            manifest['enabled'] = plugin.enabled
            with open(manifest_path, 'w') as f:
                json.dump(manifest, f, indent=2)
        except:
            pass

        return plugin.enabled

    def install_plugin(self, source: str) -> bool:
        """Install a plugin from a git URL or local path."""
        import subprocess

        dest = PLUGINS_DIR / os.path.basename(source).replace('.git', '')

        if source.startswith('http') or source.startswith('git@'):
            # Git clone
            try:
                subprocess.run(['git', 'clone', source, str(dest)],
                    capture_output=True, text=True, timeout=60)
                self.discover()
                return True
            except Exception as e:
                print(f"[Plugins] Install error: {e}")
                return False
        elif os.path.isdir(source):
            # Local copy
            import shutil
            shutil.copytree(source, str(dest))
            self.discover()
            return True

        return False


def create_plugin_template(name: str) -> str:
    """Create a plugin template directory."""
    plugin_dir = PLUGINS_DIR / name
    plugin_dir.mkdir(parents=True, exist_ok=True)

    # Create manifest
    manifest = {
        "name": name,
        "description": f"DeepDive plugin: {name}",
        "version": "0.1.0",
        "author": "",
        "enabled": True,
        "hooks": {},
    }
    with open(plugin_dir / "plugin.json", 'w') as f:
        json.dump(manifest, f, indent=2)

    # Create directories
    for subdir in ['search_sources', 'views', 'prompts', 'extractors', 'reports']:
        (plugin_dir / subdir).mkdir(exist_ok=True)

    # Create example search source
    example = '''"""
Example search source plugin for DeepDive.
Implement the SearchSource class with a search() method.
"""

class SearchSource:
    """Custom data source for DeepDive investigations."""

    @property
    def name(self):
        return "Example Source"

    def search(self, query, max_results=20):
        """Search this data source. Return list of dicts with title, body, url, score."""
        # Your search logic here
        return []

    def multi_angle_search(self, subject):
        """Run multiple search angles. Return dict of {angle: results}."""
        return {"overview": self.search(subject)}

    def deep_search(self, subject, follow_up_queries=None):
        """Deep search with follow-ups. Return (results_dict, combined_text)."""
        results = self.multi_angle_search(subject)
        text = "\\n".join(r.get("body", "") for angle in results.values() for r in angle)
        return results, text
'''
    with open(plugin_dir / "search_sources" / "example.py", 'w') as f:
        f.write(example)

    return str(plugin_dir)
