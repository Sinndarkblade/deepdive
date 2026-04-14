#!/usr/bin/env python3
"""
Settings View — API keys, provider selection, defaults.
Settings stored in ~/.deepdive/settings.json
"""

import json
import os
from pathlib import Path

SETTINGS_FILE = Path.home() / ".deepdive" / "settings.json"

DEFAULT_SETTINGS = {
    "provider": "openai",
    "api_keys": {},
    "default_depth": "standard",
    "default_focus": [],
    "theme": "dark",
}


def load_settings() -> dict:
    if SETTINGS_FILE.exists():
        try:
            with open(SETTINGS_FILE) as f:
                saved = json.load(f)
            settings = {**DEFAULT_SETTINGS, **saved}
            settings['_configured'] = True
            return settings
        except:
            pass
    result = dict(DEFAULT_SETTINGS)
    result['_configured'] = False
    return result


def save_settings(settings: dict) -> bool:
    try:
        SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(SETTINGS_FILE, 'w') as f:
            json.dump(settings, f, indent=2)
        os.chmod(SETTINGS_FILE, 0o600)
        return True
    except:
        return False


def build_settings_page():
    """Generate the settings HTML page."""
    settings = load_settings()

    # Mask API keys for display
    def mask_key(key):
        if not key:
            return ""
        if len(key) < 8:
            return "***"
        return key[:4] + "..." + key[-4:]

    cur_provider = settings.get("provider", "openai")
    cur_ollama_model = settings.get("ollama_model", "gemma4:latest")
    cur_ollama_url = settings.get("ollama_url", "http://localhost:11434")
    cur_openai_url = settings.get("openai_base_url", "https://api.openai.com/v1")
    cur_openai_model = settings.get("openai_model", "gpt-4o-mini")

    providers = [
        ("openai", "OpenAI / DeepSeek / Groq (Recommended)", "OpenAI, DeepSeek, Groq, Together, LM Studio, etc. — best results for large investigations"),
        ("claude_api", "Claude (Anthropic API)", "Claude 3.5 Sonnet / Opus — excellent for complex OSINT analysis"),
        ("ollama", "Ollama (Local / Offline)", "Run local models via Ollama — no API key needed, lower quality"),
        ("claude", "Claude CLI", "Uses your Claude Code login — not recommended"),
    ]

    provider_options = ""
    for pid, pname, _ in providers:
        selected = "selected" if cur_provider == pid else ""
        provider_options += f'<option value="{pid}" {selected}>{pname}</option>\n'

    # Try to list available Ollama models for dropdown
    ollama_model_options = f'<option value="{cur_ollama_model}" selected>{cur_ollama_model}</option>'
    try:
        import requests as _req
        _r = _req.get(f"{cur_ollama_url}/api/tags", timeout=2)
        if _r.status_code == 200:
            _models = [m['name'] for m in _r.json().get('models', [])]
            if _models:
                ollama_model_options = ""
                for m in _models:
                    sel = "selected" if m == cur_ollama_model else ""
                    ollama_model_options += f'<option value="{m}" {sel}>{m}</option>'
    except Exception:
        pass

    claude_api_key = mask_key(settings.get("api_keys", {}).get("claude_api", ""))
    openai_api_key = mask_key(settings.get("api_keys", {}).get("openai", ""))

    def show(pid):
        return "" if cur_provider == pid else "display:none"

    depth_options = ""
    for d in ["quick", "standard", "exhaustive"]:
        selected = "selected" if settings["default_depth"] == d else ""
        depth_options += f'<option value="{d}" {selected}>{d.title()}</option>'

    html = f'''<!DOCTYPE html>
<html lang="en" id="settingsHtml">
<head>
<meta charset="UTF-8"><title>DeepDive — Settings</title>
<link rel="stylesheet" href="/static/css/themes.css">
<link rel="stylesheet" href="/static/css/views-shared.css">
<script>
(function(){{
  var t = localStorage.getItem('deepdive-theme') || 'dark';
  document.getElementById('settingsHtml').setAttribute('data-theme', t);
}})();
</script>
</head>
<body>

<div class="back-bar">
  <a href="http://localhost:8766/board" class="back-btn">← Board</a>
  <span class="back-bar-title">Settings</span>
</div>

<div class="page" style="max-width:680px">

  <div class="card">
    <div class="card-header"><span class="card-title">AI Provider</span></div>
    <div class="card-body">
      <div class="field">
        <label>Active Provider</label>
        <select id="provider" onchange="showProviderFields()">
          {provider_options}
        </select>
      </div>

      <div id="fields_openai" style="{show("openai")}">
        <div class="field">
          <label>API Base URL</label>
          <div class="field-note">OpenAI: https://api.openai.com/v1 &nbsp;·&nbsp; DeepSeek: https://api.deepseek.com/v1 &nbsp;·&nbsp; Groq: https://api.groq.com/openai/v1 &nbsp;·&nbsp; LM Studio: http://localhost:1234/v1</div>
          <input type="text" id="openai_base_url" value="{cur_openai_url}">
        </div>
        <div class="field">
          <label>Model Name</label>
          <input type="text" id="openai_model" value="{cur_openai_model}" placeholder="gpt-4o-mini / deepseek-chat / llama-3.3-70b-versatile">
        </div>
        <div class="field">
          <label>API Key</label>
          <input type="password" id="key_openai" placeholder="{openai_api_key or 'Enter API key...'}">
        </div>
      </div>

      <div id="fields_claude_api" style="{show("claude_api")}">
        <div class="field">
          <label>Anthropic API Key</label>
          <div class="field-note">Get one at console.anthropic.com</div>
          <input type="password" id="key_claude_api" placeholder="{claude_api_key or 'sk-ant-...'}">
        </div>
      </div>

      <div id="fields_ollama" style="{show("ollama")}">
        <div class="field">
          <label>Ollama Model <span class="active-badge">ACTIVE</span></label>
          <div class="field-note">Select from installed models or type a model name</div>
          <select id="ollama_model">{ollama_model_options}</select>
        </div>
        <div class="field">
          <label>Ollama Server URL</label>
          <input type="text" id="ollama_url" value="{cur_ollama_url}" placeholder="http://localhost:11434">
        </div>
        <button onclick="refreshModels()" class="btn btn-secondary" style="width:auto;margin-top:4px">↺ Refresh Models</button>
      </div>

      <div id="fields_claude" style="{show("claude")}">
        <div class="warning-box">
          <div class="warning-title">⚠ USE AT YOUR OWN RISK</div>
          <div class="warning-body">
            Anthropic has restricted Claude CLI use inside third-party harnesses.
            Using this mode may violate Anthropic's Terms of Service and could result in
            your Claude account being suspended.<br><br>
            <strong>Consider using OpenAI, DeepSeek, Groq, or Ollama instead.</strong>
          </div>
        </div>
      </div>
    </div>
  </div>

  <div class="card">
    <div class="card-header"><span class="card-title">Defaults</span></div>
    <div class="card-body">
      <div class="field">
        <label>Default Investigation Depth</label>
        <select id="default_depth">{depth_options}</select>
      </div>
    </div>
  </div>

  <div class="card">
    <div class="card-header"><span class="card-title">Plugins</span></div>
    <div class="card-body">
      <div id="pluginList" style="margin-bottom:12px"></div>
      <div style="display:flex;gap:8px">
        <input type="text" id="pluginSource" placeholder="Git URL or local path to install..." style="flex:1">
        <button onclick="installPlugin()" class="btn btn-secondary" style="width:auto">Install</button>
      </div>
    </div>
  </div>

  <div style="display:flex;gap:10px;margin-top:4px">
    <button onclick="saveSettings()" class="btn btn-primary" style="flex:1">Save Settings</button>
    <button onclick="window.location.href='http://localhost:8766/board'" class="btn btn-secondary" style="width:auto">Cancel</button>
  </div>
  <div id="status" class="status-msg"></div>

</div>

<script>
function showProviderFields() {{
    const p = document.getElementById('provider').value;
    ['ollama','openai','claude_api','claude'].forEach(id => {{
        const el = document.getElementById('fields_' + id);
        if (el) el.style.display = id === p ? 'block' : 'none';
    }});
}}
showProviderFields();

function refreshModels() {{
    const url = document.getElementById('ollama_url').value || 'http://localhost:11434';
    fetch(url + '/api/tags').then(r => r.json()).then(d => {{
        const sel = document.getElementById('ollama_model');
        const cur = sel.value;
        sel.innerHTML = '';
        (d.models || []).forEach(m => {{
            const o = document.createElement('option');
            o.value = m.name; o.text = m.name;
            if (m.name === cur) o.selected = true;
            sel.appendChild(o);
        }});
        setStatus('Model list refreshed', true);
    }}).catch(() => setStatus('Could not reach Ollama at ' + url, false));
}}

function setStatus(msg, ok) {{
    const st = document.getElementById('status');
    st.textContent = (ok ? '✓ ' : '✗ ') + msg;
    st.className = 'status-msg ' + (ok ? 'ok' : 'err');
}}

function saveSettings() {{
    const provider = document.getElementById('provider').value;
    const api_keys = {{}};
    const key_ca = document.getElementById('key_claude_api');
    if (key_ca && key_ca.value) api_keys['claude_api'] = key_ca.value;
    const key_oa = document.getElementById('key_openai');
    if (key_oa && key_oa.value) api_keys['openai'] = key_oa.value;

    const settings = {{
        provider: provider,
        api_keys: api_keys,
        default_depth: document.getElementById('default_depth').value,
    }};
    if (provider === 'ollama') {{
        settings.ollama_model = document.getElementById('ollama_model').value;
        settings.ollama_url = document.getElementById('ollama_url').value || 'http://localhost:11434';
    }}
    if (provider === 'openai') {{
        settings.openai_base_url = document.getElementById('openai_base_url').value;
        settings.openai_model = document.getElementById('openai_model').value;
    }}

    fetch('http://localhost:8766/settings/save', {{
        method: 'POST', headers: {{'Content-Type': 'application/json'}},
        body: JSON.stringify(settings)
    }}).then(r => r.json()).then(d => {{
        if (d.success) setStatus('Settings saved — using ' + provider + (provider === 'ollama' ? ' / ' + (settings.ollama_model || '') : ''), true);
        else setStatus(d.error || 'Failed', false);
    }});
}}

function loadPlugins() {{
    fetch('http://localhost:8766/plugins/list', {{method: 'POST'}})
        .then(r => r.json()).then(d => {{
            const el = document.getElementById('pluginList');
            const plugins = d.plugins || [];
            if (!plugins.length) {{
                el.innerHTML = '<div style="color:var(--text-muted);font-size:11px;padding:8px">No plugins installed</div>';
                return;
            }}
            el.innerHTML = plugins.map(p =>
                '<div style="display:flex;justify-content:space-between;align-items:center;padding:10px 0;border-bottom:1px solid var(--glass-border)">' +
                '<div><div style="font-size:13px;font-weight:600;color:var(--text)">' + p.name + ' <span style="color:var(--text-muted);font-size:11px">v' + p.version + '</span></div>' +
                '<div style="font-size:10px;color:var(--text-muted)">' + p.description + '</div></div>' +
                '<button style="padding:4px 12px;border-radius:20px;border:1px solid ' + (p.enabled ? 'var(--accent)' : 'var(--glass-border)') + ';background:' + (p.enabled ? 'var(--accent-light)' : 'var(--white)') + ';color:' + (p.enabled ? 'var(--accent)' : 'var(--text-muted)') + ';font-size:11px;cursor:pointer" onclick="togglePlugin(\'' + p.name + '\')">' + (p.enabled ? 'Enabled' : 'Disabled') + '</button>' +
                '</div>'
            ).join('');
        }});
}}

function togglePlugin(name) {{
    fetch('http://localhost:8766/plugins/toggle', {{
        method: 'POST', headers: {{'Content-Type': 'application/json'}},
        body: JSON.stringify({{name: name}})
    }}).then(() => loadPlugins());
}}

function installPlugin() {{
    const source = document.getElementById('pluginSource').value.trim();
    if (!source) return;
    fetch('http://localhost:8766/plugins/install', {{
        method: 'POST', headers: {{'Content-Type': 'application/json'}},
        body: JSON.stringify({{source: source}})
    }}).then(r => r.json()).then(d => {{
        if (d.success) loadPlugins();
        document.getElementById('pluginSource').value = '';
    }});
}}

loadPlugins();
</script>
</body></html>'''

    return html
