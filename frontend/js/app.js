/**
 * DeepDive App — Main entry point
 * Initializes the graph, wires up event handlers, loads data.
 * Depends on: api.js, graph.js, views.js (loaded before this file)
 */

// ── App Init ──

document.addEventListener('DOMContentLoaded', function() {
  // Check onboarding state first
  getOnboardingState().then(state => {
    if (state.is_first_run) {
      _runOnboarding(state);
    } else {
      // Set chat names from saved settings
      setChatNames(state.agent_name, state.user_name);
      _loadBoard(state);
    }
  }).catch(() => {
    // Onboarding endpoint might not exist yet, just load the board
    _loadBoard();
  });
});

function _loadBoard(onboardingState) {
  fetchBoardData().then(data => {
    if (!data || data.error) {
      showBanner('Error loading board data: ' + (data ? data.error : 'Server not responding'));
      return;
    }
    startApp(data);

    // Try to restore chat from session first (persists across reloads)
    var restored = restoreChatFromSession();

    if (restored) {
      // Chat restored — open panel, no re-greeting
      if (!chatOpen) toggleChat();
    } else if (onboardingState && !onboardingState.is_first_run) {
      // Fresh session, show greeting once
      getGreeting().then(g => {
        if (g.greeting) {
          if (!chatOpen) toggleChat();
          addChatMessage('agent', g.greeting, g.agent_name);
        }
      }).catch(() => {});
    }
  }).catch(() => {
    showBanner('Cannot connect to server. Is the server running?');
  });
}

function _runOnboarding(state) {
  // Open chat panel for onboarding
  setTimeout(function() {
    if (!chatOpen) toggleChat();

    // Run through onboarding steps
    var currentStep = 0;
    var steps = state.steps || [];
    var userData = {};

    function showStep(idx) {
      if (idx >= steps.length) {
        // Onboarding complete, reload
        _loadBoard();
        return;
      }
      var step = steps[idx];
      var text = step.agent_text
        .replace('{user_name}', userData.user_name || '')
        .replace('{agent_name}', userData.agent_name || '');
      addChatMessage('agent', text, 'DeepDive');

      if (!step.wait_for) {
        // Auto-advance after a short delay
        setTimeout(function() { showStep(idx + 1); }, 1500);
      }
      // If wait_for is set, the normal chat send handler will process it
      currentStep = idx;
    }

    // Override chat handler for onboarding
    var originalHandler = _handleUserMessage;
    _handleUserMessage = async function(text) {
      var step = steps[currentStep];
      if (!step || !step.wait_for) return;

      // Submit to server
      var result = await submitOnboardingStep(step.wait_for === 'user_name' ? 'ask_user_name' : 'ask_agent_name', text);

      if (result.error) {
        addChatMessage('system', result.error);
        return;
      }

      if (result.user_name) userData.user_name = result.user_name;
      if (result.agent_name) {
        userData.agent_name = result.agent_name;
        setChatNames(result.agent_name, userData.user_name);
      }

      if (result.complete) {
        // Show final step then load board
        if (result.step) {
          addChatMessage('agent', result.step.agent_text, userData.agent_name);
        }
        // Restore normal handler
        _handleUserMessage = originalHandler;
        setTimeout(function() { _loadBoard({ is_first_run: false, agent_name: userData.agent_name, user_name: userData.user_name }); }, 3000);
      } else if (result.step) {
        showStep(currentStep + 1);
      }
    };

    // Start onboarding
    showStep(0);
  }, 500);
}

function startApp(data) {
  boardTitle = data.title || 'DeepDive';

  // Set page title
  document.title = boardTitle;
  const titleEl = document.querySelector('.sidebar-title');
  if (titleEl) titleEl.textContent = boardTitle;

  // Set stats
  const stats = data.stats || {};
  updateStats(stats);

  // Load recent history
  recentHistory = JSON.parse(localStorage.getItem('dd_recent_' + boardTitle) || '[]');

  // Build entity list in sidebar
  buildEntityList(data.nodes || []);

  // Build findings
  buildFindings(data.findings || []);

  // Build legend
  buildLegend(data.stats ? data.stats.entity_types : {});

  // Init graph
  initGraph('graphCanvas', data.nodes || [], data.edges || [], data.colors || {});

  // Wire graph callbacks
  onNodeClick = function(node) {
    if (graphState.selectedNodeId === node.id) {
      deselectNode();
      closeDetailPanel();
    } else {
      selectNode(node.id);
      showDetailPanel(node);
      addToRecent(node.id, node.label, node.type);
      // Notify the chat about the selected node
      notifyChatNodeSelected(node);
    }
  };

  onNodeDoubleClick = function(node) {
    toggleCollapse(node.id);
    selectNode(node.id);
    showDetailPanel(node);
  };

  onNodeHover = showTooltip;
  onNodeHoverEnd = hideTooltip;

  // Wire WebSocket
  onWsMessage(function(d) {
    if (d.action === 'expand_done') {
      showBanner(d.message);
      renderExpandResults(d);
      setTimeout(function() {
        location.hash = 'focus=' + (graphState.selectedNodeId || '');
        location.reload();
      }, 3000);
    } else if (d.action === 'reload') {
      showBanner('Done! Reloading...');
      setTimeout(function() {
        location.hash = 'focus=' + (graphState.selectedNodeId || '');
        location.reload();
      }, 1000);
    } else if (d.action === 'status') {
      showBanner(d.message);
    } else if (d.action === 'error') {
      showBanner('Error: ' + d.message);
    } else if (d.action === 'scan_status') {
      showBanner(d.message);
    } else if (d.action === 'scan_done') {
      showBanner(d.message);
      setTimeout(function() { location.reload(); }, 2000);
    }
  });

  // Load sidebar data
  setTimeout(loadSidebarData, 300);

  // Handle URL hash focus
  setTimeout(function() {
    const hash = location.hash.replace('#', '');
    const params = new URLSearchParams(hash);
    const fid = params.get('focus');
    if (fid && graphState.nodeMap[fid]) {
      focusOnNode(fid);
      showDetailPanel(graphState.nodeMap[fid]);
    }
  }, 100);
}

// ── Sidebar builders ──

function updateStats(stats) {
  const meta = document.querySelector('.sidebar-meta');
  if (meta) {
    meta.innerHTML =
      '<span><b>' + (stats.total_entities || 0) + '</b> entities</span>' +
      '<span><b>' + (stats.total_connections || 0) + '</b> conn</span>' +
      '<span><b>' + (stats.gaps_found || 0) + '</b> gaps</span>';
  }
  // Status bar
  const statusbar = document.querySelector('.statusbar');
  if (statusbar) {
    statusbar.innerHTML =
      '<span class="status-dot"></span>' +
      '<span style="color:var(--text-secondary)">ACTIVE</span>' +
      '<span class="status-sep">&middot;</span>' +
      '<span>' + (stats.total_entities || 0) + ' entities</span>' +
      '<span class="status-sep">&middot;</span>' +
      '<span>' + (stats.total_connections || 0) + ' connections</span>' +
      '<span class="status-sep">&middot;</span>' +
      '<span>' + (stats.gaps_found || 0) + ' gaps</span>';
  }
}

function buildEntityList(nodes) {
  const container = document.getElementById('entityList');
  if (!container) return;
  const sorted = [...nodes].sort((a, b) => b.connections - a.connections);
  container.innerHTML = sorted.map(n =>
    '<div class="entity-card" data-entity onclick="handleFocusNode(\'' + n.id + '\')" style="border-left-color:' + n.color + '">' +
    '<div class="entity-name" style="color:' + n.color + '">' + n.label + '</div>' +
    '<div class="entity-type">' + n.type + ' &middot; ' + n.connections + ' conn</div></div>'
  ).join('');
}

function buildFindings(findings) {
  const container = document.getElementById('findingsContainer');
  if (!container || !findings.length) return;
  container.innerHTML = findings.map(f => '<div class="finding-card">' + f + '</div>').join('');
  // Show the section
  const section = container.closest('.section');
  if (section) section.style.display = '';
}

function buildLegend(entityTypes) {
  const container = document.getElementById('legendContainer');
  if (!container) return;
  const colors = graphState.colors || {};
  container.innerHTML = Object.entries(colors)
    .filter(([t]) => (entityTypes || {})[t] > 0)
    .map(([t, c]) =>
      '<div class="legend-item"><div class="legend-dot" style="background:' + c + '"></div>' + t + ' (' + (entityTypes[t] || 0) + ')</div>'
    ).join('');
}

// ── Action Handlers (called from HTML onclick) ──

function handleFocusNode(id) {
  focusOnNode(id);
  const node = getNode(id);
  if (node) {
    showDetailPanel(node);
    addToRecent(id, node.label, node.type);
  }
}

function handleToggleCollapse(id) {
  toggleCollapse(id);
  const node = getNode(id);
  if (node) showDetailPanel(node);
}

function handleDiveDeeper(id, label) {
  // Route through the chat so the investigator handles it with approval
  if (!chatOpen) toggleChat();
  var ef = getEnabledFeeds();
  var feedList = ef.length ? ' using ' + ef.join(', ') : '';
  var msg = 'Dive deeper into "' + label + '"' + feedList;
  addChatMessage('user', msg);
  showTyping();

  var btn = document.getElementById('chatSendBtn');
  if (btn) btn.disabled = true;

  _handleUserMessage(msg).finally(function() {
    hideTyping();
    if (btn) btn.disabled = false;
  });
}

function handleInvestigateNode(id, label, type, connCount) {
  document.getElementById('searchInput').value = label;
  const p = document.getElementById('interviewPanel');
  p.classList.add('open');
  loadFocusOptions();
  setTimeout(function() {
    const ctx = document.getElementById('userContext');
    if (ctx) {
      const edges = getEdgesFor(id);
      const names = edges.map(c => {
        const oid = c.from === id ? c.to : c.from;
        const o = getNode(oid);
        return o ? (o.label + ' (' + c.label + ')') : '';
      }).filter(x => x).slice(0, 20).join(', ');
      ctx.value = 'Known: ' + names;
    }
    let cd = document.getElementById('investChoice');
    if (!cd) {
      cd = document.createElement('div');
      cd.id = 'investChoice';
      cd.style.cssText = 'margin-top:10px';
      cd.innerHTML = '<div class="interview-label">Mode</div>' +
        '<label style="display:block;font-size:12px;color:var(--text-secondary);padding:3px 0"><input type="radio" name="investMode" value="expand" checked> Expand current graph</label>' +
        '<label style="display:block;font-size:12px;color:var(--text-secondary);padding:3px 0"><input type="radio" name="investMode" value="new"> New investigation</label>';
      const btn = p.querySelector('.btn-primary');
      if (btn) p.insertBefore(cd, btn);
    }
  }, 300);
}

function handleGenerateReport(id, label) {
  showBanner('Generating report for <b>' + label + '</b>...');

  if (sendWsMessage({ action: 'report', id, label })) return;

  generateReport(id, label).then(d => {
    if (d.success) {
      showBanner('Report saved');
      loadReportList();
      if (graphState.selectedNodeId && graphState.nodeMap[graphState.selectedNodeId]) {
        showDetailPanel(graphState.nodeMap[graphState.selectedNodeId]);
      }
    } else {
      showBanner('Error: ' + d.error);
    }
  }).catch(() => showBanner('Error: Server not running'));
}

function handleRunOsint(tool, entity) {
  showFeedPanel(tool.toUpperCase() + ' — ' + entity,
    '<div class="feed-loading">AI is running ' + tool + ' trace on ' + entity + '... this may take a minute</div>');
  showBanner('AI running <b>' + tool + '</b> on <b>' + entity + '</b>...');

  runOsintTool(tool, entity).then(d => {
    if (!d.success) {
      showFeedPanel(tool.toUpperCase(), '<div class="feed-loading">Error: ' + (d.error || 'Failed') + '</div>');
      showBanner('Error: ' + (d.error || 'Failed'));
      return;
    }
    renderFeedResults(tool, entity, d);
    showBanner(tool + ' complete: ' + d.message);
    if (d.reload) setTimeout(function() { location.reload(); }, 3000);
  }).catch(() => {
    showFeedPanel(tool.toUpperCase(), '<div class="feed-loading">Server not running</div>');
    showBanner('Error: Server not running');
  });
}

function handlePreviewFeed(feedName) {
  const entity = graphState.selectedNodeId && graphState.nodeMap[graphState.selectedNodeId] ?
    graphState.nodeMap[graphState.selectedNodeId].label :
    document.getElementById('searchInput').value.trim();

  if (!entity) {
    showBanner('Select a node or enter a search term first');
    return;
  }

  showFeedLoading(feedName);

  runOsintTool(feedName, entity).then(d => {
    if (!d.success) {
      showFeedPanel(feedName.toUpperCase(), '<div class="feed-loading">Error: ' + (d.error || 'Failed') + '</div>');
      return;
    }
    renderFeedResults(feedName, entity, d);
  }).catch(() => {
    showFeedPanel(feedName.toUpperCase(), '<div class="feed-loading">Server not running</div>');
  });
}

function handlePinNode(id) {
  pinNode(id).then(d => {
    if (d.success && graphState.nodeMap[id]) {
      if (!graphState.nodeMap[id].metadata) graphState.nodeMap[id].metadata = {};
      graphState.nodeMap[id].metadata.pinned = d.pinned;
      showDetailPanel(graphState.nodeMap[id]);
    }
  });
}

function handleAddNote(id) {
  const note = prompt('Add note:');
  if (!note || !note.trim()) return;
  addNodeNote(id, note.trim()).then(d => {
    if (d.success && graphState.nodeMap[id]) {
      if (!graphState.nodeMap[id].metadata) graphState.nodeMap[id].metadata = {};
      if (!graphState.nodeMap[id].metadata.notes) graphState.nodeMap[id].metadata.notes = [];
      graphState.nodeMap[id].metadata.notes.push(note.trim());
      showDetailPanel(graphState.nodeMap[id]);
    }
  });
}

function handlePruneNode(id, label) {
  if (!confirm('Remove ' + label + '?')) return;
  pruneNode(id).then(d => {
    if (d.success) location.reload();
  });
}

function handleAnalyzeFeedData() {
  const { results, feed, entity } = _feedPanelData;
  if (!results || !results.length) return;

  const dataText = results.map(r => {
    let line = (r.title || r.name || '') + ' | ' + (r.source || feed) + ' | ' + (r.date || '');
    if (r.extra) Object.entries(r.extra).forEach(([k, v]) => line += ' | ' + k + ': ' + v);
    if (r.url) line += ' | ' + r.url;
    return line;
  }).join('\n');

  showBanner('AI analyzing ' + results.length + ' ' + feed + ' results...');
  analyzeOsintData(entity, dataText, feed).then(d => {
    if (d.success) {
      showBanner('AI extracted ' + d.added + ' entities from ' + feed);
      if (d.reload) setTimeout(function() { location.reload(); }, 1500);
    } else {
      showBanner('Error: ' + (d.error || 'Failed'));
    }
  }).catch(() => showBanner('Server error'));
}

function handleLaunchInvestigation() {
  const subj = document.getElementById('searchInput').value.trim();
  if (!subj) return;

  const fa = [];
  document.querySelectorAll('.focus-cb:checked').forEach(cb => fa.push(cb.value));
  if (!fa.length) fa.push('all');

  const mr = document.querySelector('input[name="investMode"]:checked');
  const ef = getEnabledFeeds();

  const config = {
    subject: subj,
    raw_intent: subj,
    focus_areas: fa,
    depth: document.getElementById('depthSelect').value,
    time_period: document.getElementById('timePeriod').value,
    user_context: document.getElementById('userContext').value,
    multi_agent: document.getElementById('multiAgent').checked,
    mode: mr ? mr.value : 'new',
    enabled_feeds: ef,
  };

  showBanner('Investigating <b>' + subj + '</b>...');
  document.getElementById('interviewPanel').classList.remove('open');

  investigateWithConfig(config).then(d => {
    if (d.success) {
      showBanner('Found ' + d.entities + ' entities');
      location.reload();
    } else {
      showBanner('Error: ' + (d.error || 'Failed'));
    }
  }).catch(() => showBanner('Error: Server not running'));
}

function handleSwitchInvestigation(dir) {
  if (!dir) return;
  // Clear chat so stale greeting doesn't persist
  clearChatMessages();
  sessionStorage.removeItem('dd_chat_history');
  switchInvestigation(dir).then(d => {
    if (d.success) location.reload();
  });
}

function handleGoHome() {
  goHome().then(() => location.reload());
}

function handleResearchGaps() {
  showBanner('Researching gaps...');
  researchGaps(5).then(d => {
    if (d.success) {
      showBanner(d.gaps_researched + ' gaps researched');
      setTimeout(function() { location.reload(); }, 2000);
    } else {
      showBanner('Error: ' + (d.error || 'Failed'));
    }
  }).catch(() => showBanner('Error: Server not running'));
}

function handleScanDataset() {
  const path = document.getElementById('dsPath').value.trim();
  if (!path) return;
  showBanner('Scanning...');

  if (sendWsMessage({ action: 'scan_dataset', path })) return;

  scanDataset(path).then(d => {
    if (d.success) {
      showBanner(d.files_indexed + ' files, ' + d.entities_added + ' entities');
      setTimeout(function() { location.reload(); }, 2000);
    } else {
      showBanner('Error: ' + d.error);
    }
  }).catch(() => showBanner('Error: Server not running'));
}

// ── Theme System ──

function setTheme(name) {
  document.documentElement.setAttribute('data-theme', name);
  localStorage.setItem('deepdive-theme', name);
  document.querySelectorAll('.topbar-swatch').forEach(s => {
    s.classList.toggle('active', s.getAttribute('data-theme') === name);
  });
  if (typeof drawGraph === 'function') drawGraph();
}

// Init swatch active state on load
(function() {
  var t = localStorage.getItem('deepdive-theme') || 'aero';
  document.querySelectorAll('.topbar-swatch').forEach(s => {
    s.classList.toggle('active', s.getAttribute('data-theme') === t);
  });
})();

// ── Top Menu Dropdown ──
function toggleTopMenu() {
  const dd = document.getElementById('topbarDropdown');
  if (dd) dd.classList.toggle('open');
}

function closeTopMenu() {
  const dd = document.getElementById('topbarDropdown');
  if (dd) dd.classList.remove('open');
}

document.addEventListener('click', function(e) {
  const wrap = document.getElementById('topbarMenuWrap');
  if (wrap && !wrap.contains(e.target)) closeTopMenu();
});
