/**
 * DeepDive API Client
 * All server communication — fetch and WebSocket.
 * Every function returns promises. No direct DOM manipulation here.
 */

const SERVER = 'http://localhost:8766';
const WS_URL = 'ws://localhost:8765/ws';

// ── Core HTTP helpers ──

function apiPost(path, body = {}) {
  return fetch(SERVER + path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  }).then(r => r.json());
}

function apiGet(path) {
  return fetch(SERVER + path).then(r => {
    if (r.headers.get('content-type')?.includes('json')) return r.json();
    return r.text();
  });
}

// ── Board Data ──

function fetchBoardData() {
  return apiPost('/api/board-data');
}

// ── Investigation Management ──

function listInvestigations() {
  return apiPost('/list_investigations');
}

function switchInvestigation(dir) {
  return apiPost('/switch', { dir });
}

function createNewInvestigation(name) {
  return apiPost('/new_investigation', { name });
}

function goHome() {
  return apiPost('/home');
}

// ── Entity Operations ──

function expandEntity(id, label, searchMode, enabledFeeds) {
  return apiPost('/expand', {
    id, label,
    search_mode: searchMode,
    enabled_feeds: enabledFeeds && enabledFeeds.length ? enabledFeeds : null,
  });
}

function investigateWithConfig(config) {
  return apiPost('/interview/start', config);
}

function getInterviewOptions() {
  return apiPost('/interview/options');
}

function generateReport(id, label) {
  return apiPost('/report', { id, label });
}

function getReport(id) {
  return apiPost('/report/get', { id });
}

function listReports() {
  return apiPost('/list_reports');
}

// ── Node Actions ──

function pinNode(id) {
  return apiPost('/node/pin', { id });
}

function addNodeNote(id, note) {
  return apiPost('/node/note', { id, note });
}

function pruneNode(id) {
  return apiPost('/node/prune', { id });
}

function getPinnedNodes() {
  return apiPost('/node/pinned');
}

// ── OSINT Tools ──

function runOsintTool(tool, entity) {
  return apiPost('/osint/' + tool, { entity });
}

function analyzeOsintData(entity, data, source) {
  return apiPost('/osint/analyze', { entity, data, source });
}

// ── Gap Analysis ──

function listGaps() {
  return apiPost('/list_gaps');
}

function researchGaps(maxGaps = 5) {
  return apiPost('/research_gaps', { max_gaps: maxGaps });
}

// ── Data Sources ──

function scanDataset(path) {
  return apiPost('/scan', { path });
}

function browseDirectory(path) {
  return apiPost('/browse_dir', { path });
}

function pickFolder() {
  return apiPost('/pick_folder');
}

// ── Settings ──

function loadSettings() {
  return apiPost('/settings/load');
}

function saveSettings(settings) {
  return apiPost('/settings/save', settings);
}

// ── Onboarding ──

function getOnboardingState() {
  return apiPost('/onboarding/state');
}

function submitOnboardingStep(stepId, input) {
  return apiPost('/onboarding/step', { step_id: stepId, input: input });
}

function getGreeting() {
  return apiPost('/onboarding/greeting');
}

// ── Auth ──

function checkAuthStatus() {
  return apiPost('/auth/status');
}

// ── Usage ──

function getUsageStats() {
  return apiPost('/usage');
}

function killInvestigation() {
  return apiPost('/kill');
}

function resetKill() {
  return apiPost('/kill/reset');
}

// ── Plugins ──

function listPlugins() {
  return apiPost('/plugins/list');
}

function togglePlugin(name) {
  return apiPost('/plugins/toggle', { name });
}

function installPlugin(source) {
  return apiPost('/plugins/install', { source });
}

// ── Export ──

function exportJson() {
  return apiPost('/export/json');
}

function exportMarkdown() {
  return apiPost('/export/markdown');
}

function exportObsidianVault(vaultPath) {
  return apiPost('/export/obsidian', { vault_path: vaultPath || '' });
}

function scanCrossLinks() {
  return apiPost('/crosslinks/scan');
}

// ── File Browser ──

function browseDir(path) {
  return apiPost('/browse_dir', { path });
}

// ── WebSocket ──

let _ws = null;
let _wsListeners = [];

function connectWebSocket() {
  try {
    _ws = new WebSocket(WS_URL);
    _ws.onmessage = function(e) {
      const data = JSON.parse(e.data);
      _wsListeners.forEach(fn => fn(data));
    };
    _ws.onerror = function() {};
    _ws.onclose = function() {
      // Reconnect after 3 seconds
      setTimeout(connectWebSocket, 3000);
    };
  } catch (e) {
    // WebSocket not available
  }
}

function onWsMessage(callback) {
  _wsListeners.push(callback);
}

function sendWsMessage(data) {
  if (_ws && _ws.readyState === 1) {
    _ws.send(JSON.stringify(data));
    return true;
  }
  return false;
}

// Auto-connect on load
connectWebSocket();
