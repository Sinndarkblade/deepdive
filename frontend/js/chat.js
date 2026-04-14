/**
 * DeepDive Chat Panel
 * Floating, draggable, resizable chat interface for the AI investigator.
 * Handles message display, input, typing indicators, and drag behavior.
 */

// ── State ──
let chatOpen = false;
let chatMessages = [];
let investigatorName = 'Investigator';
let userName = 'User';
let chatDragging = false;
let chatDragOffsetX = 0;
let chatDragOffsetY = 0;

// ── Init ──

function initChat() {
  const panel = document.getElementById('chatPanel');
  if (!panel) return;

  // Load names from settings
  const savedSettings = localStorage.getItem('dd_chat_settings');
  if (savedSettings) {
    try {
      const s = JSON.parse(savedSettings);
      investigatorName = s.investigatorName || 'Investigator';
      userName = s.userName || 'User';
    } catch (e) {}
  }

  // Update title
  document.getElementById('chatAgentName').textContent = investigatorName;

  // Setup drag
  _setupDrag(panel);

  // Setup input
  const input = document.getElementById('chatInput');
  input.addEventListener('keydown', function(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendChatMessage();
    }
  });

  // Auto-resize textarea
  input.addEventListener('input', function() {
    this.style.height = 'auto';
    this.style.height = Math.min(this.scrollHeight, 120) + 'px';
  });
}

// ── Toggle ──

function toggleChat() {
  chatOpen = !chatOpen;
  const panel = document.getElementById('chatPanel');
  const toggle = document.getElementById('chatToggle');

  if (chatOpen) {
    panel.classList.add('open');
    toggle.classList.add('active');
    toggle.textContent = '✕';
    document.getElementById('chatInput').focus();
    scrollChatToBottom();
  } else {
    panel.classList.remove('open');
    toggle.classList.remove('active');
    toggle.textContent = '💬';
  }
}

// ── Messages ──

function addChatMessage(role, text, name) {
  const msg = {
    role: role,  // 'agent', 'user', 'system'
    text: text,
    name: name || (role === 'agent' ? investigatorName : userName),
    time: Date.now(),
  };
  chatMessages.push(msg);
  _renderMessage(msg);
  scrollChatToBottom();
  saveChatToSession();
}

function _renderMessage(msg) {
  const container = document.getElementById('chatMessages');
  const div = document.createElement('div');
  div.className = 'chat-msg ' + msg.role;

  if (msg.role === 'system') {
    div.textContent = msg.text;
  } else {
    let html = '<div class="msg-name">' + msg.name + '</div>';
    if (msg.role === 'agent') {
      html += _renderMarkdown(msg.text);
    } else {
      html += _escapeHtml(msg.text);
    }
    div.innerHTML = html;
  }

  container.appendChild(div);
}

function clearChatMessages() {
  chatMessages = [];
  const container = document.getElementById('chatMessages');
  if (container) container.innerHTML = '';
  sessionStorage.removeItem('dd_chat_history');
}

function saveChatToSession() {
  // Save text-only messages to sessionStorage (not interactive elements)
  var saveable = chatMessages.map(function(m) {
    return { role: m.role, text: m.text, name: m.name };
  });
  sessionStorage.setItem('dd_chat_history', JSON.stringify(saveable));
}

function restoreChatFromSession() {
  var saved = sessionStorage.getItem('dd_chat_history');
  if (!saved) return false;
  try {
    var msgs = JSON.parse(saved);
    if (!msgs.length) return false;
    msgs.forEach(function(m) {
      addChatMessage(m.role, m.text, m.name);
    });
    return true;
  } catch (e) {
    return false;
  }
}

function scrollChatToBottom() {
  const container = document.getElementById('chatMessages');
  if (container) {
    setTimeout(() => { container.scrollTop = container.scrollHeight; }, 50);
  }
}

// ── Typing Indicator ──

var _typingTimer = null;
var _typingStartTime = 0;

function showTyping() {
  const el = document.getElementById('chatTyping');
  if (el) {
    el.classList.add('visible');
    el.innerHTML = '<span class="chat-typing-dot"></span><span class="chat-typing-dot"></span><span class="chat-typing-dot"></span>';
  }
  _typingStartTime = Date.now();
  // Update with elapsed time every 5 seconds
  if (_typingTimer) clearInterval(_typingTimer);
  _typingTimer = setInterval(function() {
    var elapsed = Math.round((Date.now() - _typingStartTime) / 1000);
    if (el && el.classList.contains('visible')) {
      var statusText = el.querySelector('span:not(.chat-typing-dot)');
      var baseText = statusText ? statusText.textContent.split('(')[0].trim() : investigatorName + ' is working';
      el.innerHTML = '<span style="font-size:11px;color:var(--text-muted)">' + baseText + ' (' + elapsed + 's)</span>';
    }
  }, 5000);
  scrollChatToBottom();
}

function hideTyping() {
  const el = document.getElementById('chatTyping');
  if (el) el.classList.remove('visible');
  if (_typingTimer) { clearInterval(_typingTimer); _typingTimer = null; }
}

// ── Send ──

function sendChatMessage() {
  const input = document.getElementById('chatInput');
  const text = input.value.trim();
  if (!text) return;

  addChatMessage('user', text);
  input.value = '';
  input.style.height = 'auto';

  // Disable input while processing (GAP 13 — prevent rapid messages)
  const btn = document.getElementById('chatSendBtn');
  const inputEl = document.getElementById('chatInput');
  if (btn) btn.disabled = true;
  if (inputEl) inputEl.disabled = true;

  showTyping();

  _handleUserMessage(text).finally(() => {
    hideTyping();
    if (btn) btn.disabled = false;
    if (inputEl) { inputEl.disabled = false; inputEl.focus(); }
  });
}

async function _handleUserMessage(text) {
  return new Promise(function(resolve, reject) {
    // Send via WebSocket
    const sent = sendWsMessage({ action: 'chat', message: text });
    if (!sent) {
      addChatMessage('system', 'Not connected to server. Make sure the server is running.');
      resolve();
      return;
    }

    // Listen for responses
    const chatHandler = function(data) {
      if (data.type === 'agent_message') {
        hideTyping();
        addChatMessage('agent', data.text);
      } else if (data.type === 'status') {
        // Update typing indicator with status
        const typingEl = document.getElementById('chatTyping');
        if (typingEl) {
          typingEl.innerHTML = '<span style="font-size:11px;color:var(--text-muted)">' + data.message + '</span>';
          typingEl.classList.add('visible');
        }
      } else if (data.type === 'choices') {
        hideTyping();
        // Render choice buttons from the server
        var container = document.getElementById('chatMessages');
        var div = document.createElement('div');
        div.className = 'chat-msg agent';
        var html = '<div class="chat-choices">';
        data.choices.forEach(function(c) {
          html += '<button class="chat-choice-btn" onclick="handleChoiceClick(this, \'' +
            c.action.replace(/'/g, "\\'") + '\')">' + c.label + '</button>';
        });
        html += '</div>';
        div.innerHTML = html;
        container.appendChild(div);
        scrollChatToBottom();
      } else if (data.type === 'approval_list') {
        hideTyping();
        addApprovalMessage(data.text, data.items, data.batch_id);
      } else if (data.type === 'task_status') {
        // Update the typing indicator with task info
        var typingEl = document.getElementById('chatTyping');
        if (typingEl && data.task) {
          typingEl.innerHTML = '<span style="font-size:11px;color:var(--blue)">' +
            data.task.description + ' (' + data.task.elapsed + 's)</span>';
          typingEl.classList.add('visible');
        }
      } else if (data.type === 'tool_status') {
        // Show which tool is being used + switch mode
        setChatMode(detectModeFromTool(data.tool));
        const typingEl = document.getElementById('chatTyping');
        if (typingEl) {
          typingEl.innerHTML = '<span style="font-size:11px;color:var(--blue)">Using: ' + data.tool + '</span>';
          typingEl.classList.add('visible');
        }
      } else if (data.type === 'chat_done') {
        // Remove this handler, reset mode
        _wsListeners = _wsListeners.filter(fn => fn !== chatHandler);
        hideTyping();
        setChatMode('chat');
        resolve();
      } else if (data.action === 'navigate') {
        // AI requested a view change
        window.location.href = data.url || '/board';
      }
    };

    onWsMessage(chatHandler);
  });
}

// ── Drag ──

function _setupDrag(panel) {
  const titlebar = panel.querySelector('.chat-titlebar');
  if (!titlebar) return;

  titlebar.addEventListener('mousedown', function(e) {
    if (e.target.closest('.chat-titlebar-btn')) return; // Don't drag from buttons
    chatDragging = true;
    const rect = panel.getBoundingClientRect();
    chatDragOffsetX = e.clientX - rect.left;
    chatDragOffsetY = e.clientY - rect.top;
    panel.style.transition = 'none';
    e.preventDefault();
  });

  document.addEventListener('mousemove', function(e) {
    if (!chatDragging) return;
    const x = e.clientX - chatDragOffsetX;
    const y = e.clientY - chatDragOffsetY;
    // Constrain to viewport
    const maxX = window.innerWidth - 100;
    const maxY = window.innerHeight - 100;
    panel.style.left = Math.max(0, Math.min(x, maxX)) + 'px';
    panel.style.top = Math.max(0, Math.min(y, maxY)) + 'px';
    panel.style.right = 'auto';
    panel.style.bottom = 'auto';
  });

  document.addEventListener('mouseup', function() {
    if (chatDragging) {
      chatDragging = false;
      panel.style.transition = '';
    }
  });
}

// ── Settings ──

function setChatNames(agentName, userNameVal) {
  investigatorName = agentName || 'Investigator';
  userName = userNameVal || 'User';
  document.getElementById('chatAgentName').textContent = investigatorName;
  localStorage.setItem('dd_chat_settings', JSON.stringify({
    investigatorName, userName
  }));
}

// ── Helpers ──

function _escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

function _renderMarkdown(text) {
  // Markdown rendering + interactive elements for investigator responses
  let html = _escapeHtml(text);

  // Code blocks
  html = html.replace(/```(\w*)\n([\s\S]*?)```/g, '<pre><code>$2</code></pre>');
  // Inline code
  html = html.replace(/`([^`]+)`/g, '<code>$1</code>');
  // Bold
  html = html.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
  // Italic
  html = html.replace(/\*([^*]+)\*/g, '<em>$1</em>');
  // Headers
  html = html.replace(/^### (.+)$/gm, '<h3>$1</h3>');
  html = html.replace(/^## (.+)$/gm, '<h2>$1</h2>');
  html = html.replace(/^# (.+)$/gm, '<h1>$1</h1>');
  // Unordered lists
  html = html.replace(/^- (.+)$/gm, '<li>$1</li>');
  html = html.replace(/(<li>.*<\/li>\n?)+/g, '<ul>$&</ul>');
  // Links
  html = html.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank">$1</a>');
  // Line breaks
  html = html.replace(/\n/g, '<br>');
  // Clean up double breaks after block elements
  html = html.replace(/(<\/h[123]>)<br>/g, '$1');
  html = html.replace(/(<\/ul>)<br>/g, '$1');
  html = html.replace(/(<\/pre>)<br>/g, '$1');

  return html;
}

/**
 * Add a message with clickable action buttons.
 * choices: array of {label: string, action: string}
 * The action string is sent as a chat message when clicked.
 */
function addChoiceMessage(agentText, choices) {
  const container = document.getElementById('chatMessages');
  const div = document.createElement('div');
  div.className = 'chat-msg agent';

  let html = '<div class="msg-name">' + investigatorName + '</div>';
  html += _renderMarkdown(agentText);
  html += '<div class="chat-choices">';
  choices.forEach(function(c) {
    html += '<button class="chat-choice-btn" onclick="handleChoiceClick(this, ' +
      "'" + _escapeAttr(c.action) + "'" + ')">' + _escapeHtml(c.label) + '</button>';
  });
  html += '</div>';

  div.innerHTML = html;
  container.appendChild(div);
  scrollChatToBottom();
}

/**
 * Add a message with a checkbox list for entity approval.
 * items: array of {name, type, relationship}
 * batchId: identifier for this batch
 */
function addApprovalMessage(agentText, items, batchId) {
  const container = document.getElementById('chatMessages');
  const div = document.createElement('div');
  div.className = 'chat-msg agent';
  div.id = 'approval-' + batchId;

  let html = '<div class="msg-name">' + investigatorName + '</div>';
  html += _renderMarkdown(agentText);
  html += '<div class="chat-approval-list">';
  items.forEach(function(item, i) {
    var color = (graphState.colors && graphState.colors[item.type]) || '#6B7280';
    html += '<label class="chat-approval-item">' +
      '<input type="checkbox" checked data-index="' + i + '">' +
      '<span style="color:' + color + ';font-weight:600">' + _escapeHtml(item.name) + '</span>' +
      '<span class="chat-approval-meta">' + item.type + ' — ' + (item.relationship || '').replace(/_/g, ' ') + '</span>' +
      '</label>';
  });
  html += '</div>';
  html += '<div class="chat-approval-actions">';
  html += '<button class="chat-choice-btn primary" onclick="handleApproveSelected(' + "'" + batchId + "'" + ')">Add Selected</button>';
  html += '<button class="chat-choice-btn" onclick="handleApproveAll(' + "'" + batchId + "'" + ')">Add All</button>';
  html += '<button class="chat-choice-btn danger" onclick="handleRejectAll(' + "'" + batchId + "'" + ')">Skip All</button>';
  html += '</div>';

  div.innerHTML = html;
  container.appendChild(div);
  scrollChatToBottom();
}

function handleChoiceClick(btn, action) {
  // Disable all choice buttons in this message
  var parent = btn.closest('.chat-choices');
  if (parent) {
    parent.querySelectorAll('.chat-choice-btn').forEach(function(b) {
      b.disabled = true;
      b.style.opacity = '0.5';
    });
    btn.style.opacity = '1';
    btn.style.borderColor = 'var(--blue)';
  }
  // Send the action as a user message
  addChatMessage('user', action);
  showTyping();
  var sendBtn = document.getElementById('chatSendBtn');
  if (sendBtn) sendBtn.disabled = true;
  _handleUserMessage(action).finally(function() {
    hideTyping();
    if (sendBtn) sendBtn.disabled = false;
  });
}

function handleApproveSelected(batchId) {
  var el = document.getElementById('approval-' + batchId);
  if (!el) return;
  var indices = [];
  el.querySelectorAll('input[type="checkbox"]:checked').forEach(function(cb) {
    indices.push(parseInt(cb.dataset.index));
  });
  _disableApproval(el);
  addChatMessage('user', 'Add ' + indices.length + ' selected entities to graph');
  // Call approve endpoint
  apiPost('/approve', { batch_id: batchId, approved_indices: indices }).then(function(d) {
    if (d.success) {
      addChatMessage('agent', 'Added **' + d.added + '** entities to the graph.', investigatorName);
      if (d.added > 0) setTimeout(function() { location.reload(); }, 2000);
    } else {
      addChatMessage('system', 'Error: ' + (d.error || 'Failed'));
    }
  });
}

function handleApproveAll(batchId) {
  var el = document.getElementById('approval-' + batchId);
  if (el) _disableApproval(el);
  addChatMessage('user', 'Add all to graph');
  apiPost('/approve', { batch_id: batchId }).then(function(d) {
    if (d.success) {
      addChatMessage('agent', 'Added **' + d.added + '** entities to the graph. The graph will update shortly.\n\nWhat would you like to do next? I can dive deeper into any of the new entities, trace money flows, or check for gaps.', investigatorName);
      // Reload to update graph but with a longer delay so user can read
      if (d.added > 0) setTimeout(function() { location.reload(); }, 5000);
    }
  });
}

function handleRejectAll(batchId) {
  var el = document.getElementById('approval-' + batchId);
  if (el) _disableApproval(el);
  addChatMessage('user', 'Skip all');
  apiPost('/reject', { batch_id: batchId }).then(function() {
    addChatMessage('agent', 'Skipped. What would you like to investigate next?', investigatorName);
  });
}

function _disableApproval(el) {
  el.querySelectorAll('.chat-choice-btn').forEach(function(b) { b.disabled = true; b.style.opacity = '0.4'; });
  el.querySelectorAll('input[type="checkbox"]').forEach(function(cb) { cb.disabled = true; });
}

function _escapeAttr(s) {
  return s.replace(/'/g, "\\'").replace(/"/g, '&quot;');
}

// ── Mode Transitions ──

function setChatMode(mode) {
  // mode: 'chat', 'search', 'analysis', 'report', 'update'
  const panel = document.getElementById('chatPanel');
  const modeBar = document.getElementById('chatModeBar');
  if (!panel) return;

  panel.setAttribute('data-mode', mode || 'chat');

  const modeLabels = {
    'chat': '',
    'search': 'Searching OSINT sources...',
    'analysis': 'Analyzing data...',
    'report': 'Generating report...',
    'update': 'Preparing graph update...',
  };

  if (modeBar) {
    modeBar.textContent = modeLabels[mode] || '';
  }
}

// Detect mode from tool usage
function detectModeFromTool(toolName) {
  const searchTools = ['query_feed', 'query_all_feeds', 'scan_social_media', 'check_wayback', 'expand_entity'];
  const analysisTools = ['trace_money', 'trace_timeline', 'list_gaps', 'research_gaps'];
  const reportTools = ['generate_report', 'export_investigation'];
  const updateTools = ['approve_entities', 'new_investigation', 'prune_node'];

  if (searchTools.includes(toolName)) return 'search';
  if (analysisTools.includes(toolName)) return 'analysis';
  if (reportTools.includes(toolName)) return 'report';
  if (updateTools.includes(toolName)) return 'update';
  return 'chat';
}

// ── Node Selection Notification ──

var _lastNotifiedNode = null;

function notifyChatNodeSelected(node) {
  // Don't spam if same node clicked again
  if (_lastNotifiedNode === node.id) return;
  _lastNotifiedNode = node.id;

  // Tell the server which node is selected
  sendWsMessage({ action: 'select_node', node_id: node.id, node_name: node.label, node_type: node.type });

  // Open chat if not open
  if (!chatOpen) toggleChat();

  var conns = getEdgesFor(node.id);
  var color = (graphState.colors && graphState.colors[node.type]) || '#6B7280';

  var text = 'You selected **' + node.label + '** (' + node.type + ') — ' + conns.length + ' connections.';
  text += '\n\nWhat do you want to do?';

  // Use direct function calls instead of sending through chat pipeline
  var nodeId = node.id;
  var nodeLabel = node.label;

  var container = document.getElementById('chatMessages');
  var div = document.createElement('div');
  div.className = 'chat-msg agent';
  var html = '<div class="msg-name">' + investigatorName + '</div>';
  html += _renderMarkdown(text);
  html += '<div class="chat-choices">';
  html += '<button class="chat-choice-btn primary" onclick="directInvestigate(\'' + nodeId + '\',\'' + nodeLabel.replace(/'/g, '') + '\')">Investigate</button>';
  html += '<button class="chat-choice-btn" onclick="directInvestigate(\'' + nodeId + '\',\'' + nodeLabel.replace(/'/g, '') + '\')">Dive Deeper</button>';
  html += '<button class="chat-choice-btn" onclick="handleChoiceClick(this, \'report on ' + nodeLabel.replace(/'/g, '') + '\')">Report</button>';
  html += '<button class="chat-choice-btn" onclick="handleChoiceClick(this, \'trace money for ' + nodeLabel.replace(/'/g, '') + '\')">Trace Money</button>';
  html += '</div>';
  div.innerHTML = html;
  container.appendChild(div);
  scrollChatToBottom();
}

// ── Direct Investigation (bypasses chat model, calls expand API directly) ──

function directInvestigate(nodeId, nodeLabel) {
  addChatMessage('user', 'Investigate ' + nodeLabel);
  showTyping();

  var btn = document.getElementById('chatSendBtn');
  var inputEl = document.getElementById('chatInput');
  if (btn) btn.disabled = true;
  if (inputEl) inputEl.disabled = true;

  // Call expand endpoint directly — preview only
  apiPost('/expand', {
    id: nodeId,
    label: nodeLabel,
    search_mode: 'web',
    preview_only: true,
  }).then(function(d) {
    hideTyping();
    if (btn) btn.disabled = false;
    if (inputEl) { inputEl.disabled = false; inputEl.focus(); }

    if (d.success && d.added_entities && d.added_entities.length > 0) {
      // Stage on server first to get the real batch ID
      apiPost('/stage_entities', {
        entities: d.added_entities,
        source_id: nodeId,
        source_label: nodeLabel,
      }).then(function(stageResult) {
        var batchId = stageResult.batch_id || ('expand_' + nodeId);
        // Show approval list with the server's batch ID
        addApprovalMessage(
          'Found **' + d.added_entities.length + '** connections for **' + nodeLabel + '**:',
          d.added_entities,
          batchId
        );
      });
    } else if (d.success) {
      addChatMessage('agent', 'No new connections found for **' + nodeLabel + '**. Try a different angle — trace money, check the timeline, or ask me a specific question about this entity.', investigatorName);
    } else {
      addChatMessage('agent', 'Investigation hit a snag: ' + (d.error || 'Unknown error') + '. Want me to try again?', investigatorName);
    }
  }).catch(function(e) {
    hideTyping();
    if (btn) btn.disabled = false;
    if (inputEl) { inputEl.disabled = false; inputEl.focus(); }
    addChatMessage('system', 'Server error: ' + e.message);
  });
}

// ── File Attachment ──

function handleChatAttach() {
  // Open the file browser modal, then send path to investigator
  openFileBrowser();
  // Override the confirm action to send to chat instead
  window._chatAttachMode = true;
}

// Hook into confirmFileBrowser to detect chat attach mode
var _originalConfirmFileBrowser = typeof confirmFileBrowser === 'function' ? confirmFileBrowser : null;
document.addEventListener('DOMContentLoaded', function() {
  if (typeof confirmFileBrowser === 'function') {
    var orig = confirmFileBrowser;
    confirmFileBrowser = function() {
      if (window._chatAttachMode) {
        var path = fileBrowserSelected || fileBrowserPath;
        window._chatAttachMode = false;
        closeFileBrowser();
        if (path) {
          var msg = 'Process these files: ' + path;
          addChatMessage('user', msg);
          showTyping();
          var btn = document.getElementById('chatSendBtn');
          if (btn) btn.disabled = true;
          _handleUserMessage(msg).finally(function() {
            hideTyping();
            if (btn) btn.disabled = false;
          });
        }
      } else {
        orig();
      }
    };
  }
});

// ── Heartbeat — check for stalled tasks ──

var _heartbeatInterval = null;

function startHeartbeat() {
  if (_heartbeatInterval) return;
  _heartbeatInterval = setInterval(function() {
    apiPost('/heartbeat').then(function(status) {
      if (status.stalled && status.task && !status.task.stall_notified) {
        // A task was promised but never executed — notify user
        addChatMessage('system',
          'Task stalled: ' + status.task.description +
          ' — was promised ' + Math.round(status.task.age) + 's ago. ' +
          'Type "where are the results?" to remind ' + investigatorName + '.');
      }
    }).catch(function() {});
  }, 10000); // Check every 10 seconds
}

function stopHeartbeat() {
  if (_heartbeatInterval) {
    clearInterval(_heartbeatInterval);
    _heartbeatInterval = null;
  }
}

// ── Auto-init ──
document.addEventListener('DOMContentLoaded', function() {
  initChat();
  startHeartbeat();
});
