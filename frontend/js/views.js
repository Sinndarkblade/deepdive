/**
 * DeepDive Views Manager
 * Handles sidebar, detail panel, feed panel, tooltips, banners,
 * modals, and all UI state that isn't the graph or chat.
 */

// ── State ──
let boardTitle = 'DeepDive';
let nodeReports = {};
let recentHistory = [];
let searchMode = localStorage.getItem('dd_search_mode') || 'web';

// ── Banner ──

function showBanner(html) {
  const b = document.getElementById('banner');
  b.innerHTML = html + ' <span style="cursor:pointer;margin-left:14px;opacity:.4;font-size:16px" onclick="hideBanner()">&times;</span>';
  b.classList.add('visible');
}

function hideBanner() {
  document.getElementById('banner').classList.remove('visible');
}

// ── Tooltip ──

function showTooltip(node, mx, my) {
  const tt = document.getElementById('tooltip');
  tt.style.display = 'block';
  tt.style.left = (mx + 16) + 'px';
  tt.style.top = (my + 16) + 'px';
  let h = '<div class="tooltip-name" style="color:' + graphState.colors[node.type] + '">' + node.label + '</div>';
  h += '<div class="tooltip-meta">' + node.type + ' &middot; ' + node.connections + ' connections</div>';
  if (node.metadata) {
    Object.entries(node.metadata).slice(0, 3).forEach(([k, v]) => {
      if (k !== 'notes' && k !== 'pinned') {
        h += '<div class="tooltip-meta">' + k + ': ' + String(v).substring(0, 60) + '</div>';
      }
    });
  }
  tt.innerHTML = h;
}

function hideTooltip() {
  document.getElementById('tooltip').style.display = 'none';
}

// ── Sidebar ──

function toggleSidebar() {
  document.querySelector('.sidebar').classList.toggle('collapsed');
}

function toggleSection(el) {
  el.classList.toggle('open');
  el.nextElementSibling.classList.toggle('open');
}

function filterEntities(q) {
  q = q.toLowerCase();
  document.querySelectorAll('.entity-card[data-entity]').forEach(c => {
    c.style.display = c.textContent.toLowerCase().includes(q) || !q ? '' : 'none';
  });
}

// ── Detail Panel ──

function showDetailPanel(node) {
  const panel = document.querySelector('.detail-panel');
  const body = document.querySelector('.detail-body');
  const edges = graphState.edges;
  const colors = graphState.colors;
  const nodeMap = graphState.nodeMap;
  const conns = edges.filter(e => e.from === node.id || e.to === node.id);

  let h = '<div style="margin-bottom:16px">';
  h += '<div style="font-family:var(--font-display);font-size:22px;font-weight:800;color:' + colors[node.type] + '">' + node.label + '</div>';
  h += '<div style="font-size:11px;font-family:var(--font-mono);color:var(--text-muted);margin-top:3px;letter-spacing:1px">' + node.type.toUpperCase() + '</div></div>';

  h += '<div class="detail-row"><span class="detail-key">Connections</span><span class="detail-value">' + conns.length + '</span></div>';
  h += '<div class="detail-row"><span class="detail-key">Depth</span><span class="detail-value">' + (node.depth || 0) + '</span></div>';

  if (node.metadata) {
    Object.entries(node.metadata).forEach(([k, v]) => {
      if (k !== 'notes' && k !== 'pinned') {
        h += '<div class="detail-row"><span class="detail-key">' + k + '</span><span class="detail-value">' + v + '</span></div>';
      }
    });
  }

  const cc = edges.filter(e => e.from === node.id).length;
  if (cc > 0) {
    h += '<button class="btn btn-secondary btn-sm" style="margin:12px 0 0" onclick="handleToggleCollapse(\'' + node.id + '\')">';
    h += (isCollapsed(node.id) ? 'Expand' : 'Collapse') + ' ' + cc + ' nodes</button>';
  }

  const ri = nodeReports[node.id];
  if (ri) {
    const stale = conns.length > ri.conn_count;
    h += '<div class="report-badge ' + (stale ? 'stale' : 'current') + '">';
    h += (stale ? 'Report outdated' : 'Up to date');
    h += ' <a href="file://' + ri.path + '" target="_blank" style="color:var(--blue);margin-left:8px">Open</a></div>';
  }

  // Action buttons
  const nl = node.label.replace(/'/g, '');
  h += '<div class="detail-actions">';
  h += '<button class="btn btn-primary" onclick="handleDiveDeeper(\'' + node.id + '\',\'' + nl + '\')">Dive Deeper</button>';
  h += '<button class="btn btn-secondary" onclick="handleInvestigateNode(\'' + node.id + '\',\'' + nl + '\',\'' + node.type + '\',' + conns.length + ')">Full Investigation</button>';
  h += '<button class="btn btn-secondary" onclick="handleGenerateReport(\'' + node.id + '\',\'' + nl + '\')">' + (ri ? 'Update' : 'Generate') + ' Report</button>';

  // OSINT tools
  h += '<div style="margin-top:4px;font-size:10px;font-weight:700;color:var(--text-muted);text-transform:uppercase;letter-spacing:1px">OSINT Tools</div>';
  h += '<div class="detail-action-row"><button class="btn btn-sm btn-secondary" style="flex:1" onclick="handleRunOsint(\'timeline\',\'' + nl + '\')">Timeline</button>';
  h += '<button class="btn btn-sm btn-secondary" style="flex:1" onclick="handleRunOsint(\'money\',\'' + nl + '\')">Money Flow</button></div>';
  h += '<div class="detail-action-row"><button class="btn btn-sm btn-secondary" style="flex:1" onclick="handleRunOsint(\'social\',\'' + nl + '\')">Social Media</button>';
  h += '<button class="btn btn-sm btn-secondary" style="flex:1" onclick="handleRunOsint(\'wayback\',\'' + nl + '\')">Wayback</button></div>';
  h += '<div class="detail-action-row"><button class="btn btn-sm btn-secondary" style="flex:1" onclick="handlePreviewFeed(\'darkweb\')">Dark Web</button>';
  h += '<button class="btn btn-sm btn-secondary" style="flex:1" onclick="handlePreviewFeed(\'feeds\')">All Feeds</button></div>';

  // Node actions
  h += '<div class="detail-action-row">';
  const pin = node.metadata && node.metadata.pinned;
  h += '<button class="btn btn-sm btn-secondary" style="flex:1" onclick="handlePinNode(\'' + node.id + '\')">' + (pin ? 'Unpin' : 'Pin') + '</button>';
  h += '<button class="btn btn-sm btn-secondary" style="flex:1" onclick="handleAddNote(\'' + node.id + '\')">Note</button>';
  h += '<button class="btn btn-sm btn-danger" style="flex:1" onclick="handlePruneNode(\'' + node.id + '\',\'' + nl + '\')">Remove</button></div></div>';

  // Notes
  if (node.metadata && node.metadata.notes && node.metadata.notes.length) {
    node.metadata.notes.forEach(note => {
      h += '<div class="note-card">' + note + '</div>';
    });
  }

  // Connections list
  h += '<div class="detail-section-title">Connections (' + conns.length + ')</div>';
  conns.sort((a, b) => b.confidence - a.confidence).forEach(c => {
    const oid = c.from === node.id ? c.to : c.from;
    const o = nodeMap[oid];
    if (!o) return;
    h += '<div class="entity-card" onclick="handleFocusNode(\'' + oid + '\')">';
    h += '<div class="entity-name" style="color:' + colors[o.type] + '">' + o.label + '</div>';
    h += '<div class="entity-type">' + c.label + ' &middot; ' + Math.round(c.confidence * 100) + '%</div></div>';
  });

  body.innerHTML = h;
  panel.classList.add('open');
}

function closeDetailPanel() {
  document.querySelector('.detail-panel').classList.remove('open');
}

// ── Feed Panel ──

let _feedPanelData = { results: null, feed: '', entity: '' };

function showFeedPanel(title, contentHtml) {
  document.getElementById('feedPanelTitle').textContent = title;
  document.getElementById('feedPanelBody').innerHTML = contentHtml;
  document.getElementById('feedPanel').classList.add('open');
}

function closeFeedPanel() {
  document.getElementById('feedPanel').classList.remove('open');
}

function showFeedLoading(feedName) {
  showFeedPanel(feedName.toUpperCase(), '<div class="feed-loading">Querying ' + feedName + '...</div>');
}

function renderFeedResults(feedName, entity, data) {
  const results = data.results || [];
  _feedPanelData = { results, feed: feedName, entity };

  if (!results.length) {
    showFeedPanel(feedName.toUpperCase() + ' — ' + entity,
      '<div class="feed-loading">No results from ' + feedName + '</div>' +
      (data.message ? '<div style="text-align:center;color:var(--text-muted);font-size:11px;margin-top:8px">' + data.message + '</div>' : ''));
    return;
  }

  let html = '<div style="font-size:11px;color:var(--text-muted);margin-bottom:8px">' + data.message + '</div>';
  html += '<button class="btn btn-sm btn-primary" style="width:100%;margin-bottom:10px;padding:6px" onclick="handleAnalyzeFeedData()">AI Analyze &amp; Add to Graph</button>';
  html += _renderFeedItems(results, feedName);

  showFeedPanel(feedName.toUpperCase() + ' — ' + entity, html);
}

function renderExpandResults(data) {
  const feedData = data.feed_data || {};
  const addedEntities = data.added_entities || [];
  const feedCount = Object.keys(feedData).length;
  const totalItems = Object.values(feedData).reduce((s, arr) => s + (arr || []).length, 0);

  let html = '';

  if (addedEntities.length) {
    html += '<div style="font-size:11px;font-weight:700;color:var(--green);text-transform:uppercase;letter-spacing:1px;margin-bottom:6px">Added to Graph (' + addedEntities.length + ')</div>';
    html += addedEntities.map(function(e) {
      var eid = e.name.toLowerCase().replace(/ /g, '_');
      return '<div class="feed-item" style="border-left:3px solid ' + (graphState.colors[e.type] || '#6B7280') + '" onclick="handleFocusNode(' + String.fromCharCode(39) + eid + String.fromCharCode(39) + ')">' +
        '<div class="feed-item-title" style="color:' + (graphState.colors[e.type] || '#6B7280') + '">' + e.name + '</div>' +
        '<div class="feed-item-meta">' + e.type + ' &middot; ' + e.relationship.replace(/_/g, ' ') + '</div></div>';
    }).join('');
  }

  if (feedCount) {
    html += '<div style="font-size:11px;font-weight:700;color:var(--blue);text-transform:uppercase;letter-spacing:1px;margin:14px 0 6px">OSINT Feed Data Used (' + totalItems + ' items from ' + feedCount + ' feeds)</div>';
    Object.entries(feedData).forEach(([feed, items]) => {
      if (!items || !items.length) return;
      html += '<div style="font-size:10px;font-weight:700;color:var(--text-muted);text-transform:uppercase;margin:8px 0 4px">' + feed + ' (' + items.length + ')</div>';
      html += _renderFeedItems(items, feed);
    });
  }

  if (!html) html = '<div class="feed-loading">No feed data or entities to show</div>';
  showFeedPanel('Expansion Results — +' + data.added + ' entities', html);
}

function _renderFeedItems(items, feedName) {
  return items.map(r => {
    let extra = '';
    if (r.extra) {
      Object.entries(r.extra).slice(0, 4).forEach(([k, v]) => {
        extra += '<div class="feed-item-extra">' + k + ': ' + v + '</div>';
      });
    }
    let link = r.url ? '<div class="feed-item-link"><a href="' + r.url + '" target="_blank">' + r.url.substring(0, 80) + '</a></div>' : '';
    return '<div class="feed-item"><div class="feed-item-title">' + (r.title || r.name || r.event || '—') + '</div>' +
      '<div class="feed-item-meta">' + (r.source || feedName) + ' &middot; ' + (r.date || '') + '</div>' +
      extra + link + '</div>';
  }).join('');
}

// ── Search Mode ──

function setSearchMode(m) {
  searchMode = m;
  localStorage.setItem('dd_search_mode', m);
  document.querySelectorAll('.mode-btn').forEach(b => b.classList.remove('active'));
  const btn = document.getElementById('mode-' + m);
  if (btn) btn.classList.add('active');
}

// ── OSINT Feed Checkboxes ──

function getEnabledFeeds() {
  const feeds = [];
  document.querySelectorAll('.feed-cb:checked').forEach(cb => feeds.push(cb.value));
  return feeds;
}

function toggleAllFeeds(on) {
  document.querySelectorAll('.feed-cb').forEach(cb => cb.checked = on);
}

// ── Recent History ──

function addToRecent(id, label, type) {
  recentHistory = recentHistory.filter(r => r.id !== id);
  recentHistory.unshift({ id, label, type, time: Date.now() });
  if (recentHistory.length > 20) recentHistory = recentHistory.slice(0, 20);
  localStorage.setItem('dd_recent_' + boardTitle, JSON.stringify(recentHistory));
  renderRecent();
}

function renderRecent() {
  const el = document.getElementById('recentTargets');
  if (!el) return;
  if (!recentHistory.length) {
    el.innerHTML = '<div style="color:var(--text-muted);padding:6px;font-size:12px">Click nodes to track</div>';
    return;
  }
  el.innerHTML = recentHistory.map(r =>
    '<div class="entity-card" onclick="handleFocusNode(\'' + r.id + '\')" style="border-left-color:' + graphState.colors[r.type] + '">' +
    '<div class="entity-name" style="color:' + graphState.colors[r.type] + '">' + r.label + '</div>' +
    '<div class="entity-type">' + r.type + '</div></div>'
  ).join('');
}

// ── File Browser Modal ──

let fileBrowserPath = '/home';
let fileBrowserSelected = '';

function openFileBrowser() {
  fileBrowserPath = (document.getElementById('dsPath') && document.getElementById('dsPath').value) || '/home';
  fileBrowserSelected = '';
  document.getElementById('fileBrowserModal').classList.add('open');
  loadDirectory(fileBrowserPath);
}

function closeFileBrowser() {
  document.getElementById('fileBrowserModal').classList.remove('open');
}

function loadDirectory(path) {
  fileBrowserPath = path;
  browseDir(path).then(d => {
    if (!d.success) return;
    const parts = path.split('/').filter(x => x);
    let bc = '<span class="path-segment" onclick="loadDirectory(\'/\')">/ </span>';
    let acc = '/';
    parts.forEach(p => {
      acc += p + '/';
      bc += '<span class="path-segment" onclick="loadDirectory(\'' + acc + '\')">' + p + ' / </span>';
    });
    document.getElementById('pathBreadcrumb').innerHTML = bc;
    let html = '';
    if (path !== '/') {
      html += '<div class="file-item" ondblclick="loadDirectory(\'' + d.parent + '\')"><span class="file-icon">&#128193;</span><span class="file-name">..</span></div>';
    }
    (d.dirs || []).forEach(dir => {
      html += '<div class="file-item" onclick="selectBrowserItem(this,\'' + dir.path + '\')" ondblclick="loadDirectory(\'' + dir.path + '\')">';
      html += '<span class="file-icon">&#128193;</span><span class="file-name">' + dir.name + '</span></div>';
    });
    document.getElementById('fileBrowserList').innerHTML = html;
  }).catch(() => {
    document.getElementById('fileBrowserList').innerHTML = '<div style="color:var(--text-muted);padding:16px">Could not load</div>';
  });
}

function selectBrowserItem(el, path) {
  document.querySelectorAll('.file-item.selected').forEach(e => e.classList.remove('selected'));
  el.classList.add('selected');
  fileBrowserSelected = path;
}

function confirmFileBrowser() {
  if (document.getElementById('dsPath')) document.getElementById('dsPath').value = fileBrowserSelected || fileBrowserPath;
  closeFileBrowser();
}

// ── Interview Panel ──

function toggleInterviewPanel() {
  const inp = document.getElementById('searchInput');
  if (!inp.value.trim()) return;
  const p = document.getElementById('interviewPanel');
  if (!p.classList.contains('open')) {
    p.classList.add('open');
    loadFocusOptions();
  } else {
    p.classList.remove('open');
  }
}

function loadFocusOptions() {
  getInterviewOptions().then(d => {
    const el = document.getElementById('focusChecks');
    let h = '<label><input type="checkbox" value="all" onchange="toggleAllFocus(this.checked)"> <b>Select All</b></label>';
    Object.entries(d.focus_categories || {}).forEach(([k, cat]) => {
      h += '<div class="interview-cat">' + cat.label + '</div>';
      (cat.options || []).forEach(([v, l]) => {
        h += '<label><input type="checkbox" class="focus-cb" value="' + v + '"> ' + l + '</label>';
      });
    });
    el.innerHTML = h;
  }).catch(() => {});
}

function toggleAllFocus(checked) {
  document.querySelectorAll('.focus-cb').forEach(cb => cb.checked = checked);
}

// ── Export ──

function exportInvestigation() {
  const fmt = prompt('Export format:\n1. HTML Report\n2. JSON Graph Data\n3. Print to PDF\n\nEnter 1, 2, or 3:');
  if (fmt === '1' || fmt === null) window.open(SERVER + '/report-view', '_blank');
  else if (fmt === '2') {
    exportJson().then(data => {
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
      const a = document.createElement('a');
      a.href = URL.createObjectURL(blob);
      a.download = 'deepdive_export.json';
      a.click();
    });
  } else if (fmt === '3') window.print();
}

// ── Obsidian Export ──

function exportObsidian() {
  const vaultPath = prompt(
    'Export to Obsidian vault\n\nEnter vault path, or leave blank to save alongside investigation files:',
    ''
  );
  if (vaultPath === null) return; // cancelled

  showBanner('Exporting to Obsidian vault...', 'info');
  exportObsidianVault(vaultPath).then(d => {
    if (d.success) {
      showBanner(`✓ Exported ${d.written} entity notes → ${d.vault_path}`, 'success');
      if (confirm(`Vault exported!\n\n${d.written} notes written to:\n${d.vault_path}\n\nOpen Obsidian and use "Open folder as vault" to load it.\n\nCopy path to clipboard?`)) {
        navigator.clipboard.writeText(d.vault_path).catch(() => {});
      }
    } else {
      showBanner('Export failed: ' + (d.error || 'unknown error'), 'error');
    }
  }).catch(e => showBanner('Export error: ' + e, 'error'));
}

// ── Cross-Link Scanner ──

function scanCrossLinks() {
  showBanner('Scanning all investigations for cross-links...', 'info');
  apiPost('/crosslinks/scan').then(d => {
    if (!d.success) {
      showBanner(d.error || 'Scan failed', 'error');
      return;
    }

    const section = document.getElementById('crossLinksSection');
    const list = document.getElementById('crossLinksList');
    if (!section || !list) return;

    section.style.display = '';

    const exact = d.exact_matches || [];
    const fuzzy = d.fuzzy_matches || [];
    const total = exact.length + fuzzy.length;

    if (total === 0) {
      list.innerHTML = `<div style="color:#64748b;font-size:11px;padding:6px">${d.message || 'No cross-links found yet. Run more investigations.'}</div>`;
      showBanner(`Scanned ${d.investigations_scanned} investigations — no cross-links yet`, 'info');
      return;
    }

    let html = '';

    if (exact.length) {
      html += `<div style="color:#00ccaa;font-size:10px;font-weight:700;padding:4px 0 2px">CONFIRMED (${exact.length})</div>`;
      for (const m of exact.slice(0, 15)) {
        const invs = m.investigations.join(', ');
        html += `<div style="padding:4px 0;border-bottom:1px solid #1e293b">
          <div style="color:#e2e8f0;font-size:12px;font-weight:600">${m.entity_name}</div>
          <div style="color:#64748b;font-size:10px">${m.entity_type} · appears in ${m.appearances} investigations</div>
          <div style="color:#475569;font-size:10px">${invs}</div>
        </div>`;
      }
    }

    if (fuzzy.length) {
      html += `<div style="color:#f59e0b;font-size:10px;font-weight:700;padding:6px 0 2px">POSSIBLE MATCHES (${fuzzy.length})</div>`;
      for (const m of fuzzy.slice(0, 15)) {
        const sim = Math.round(m.similarity * 100);
        const invs = m.investigations.join(' ↔ ');
        html += `<div style="padding:4px 0;border-bottom:1px solid #1e293b">
          <div style="color:#e2e8f0;font-size:12px;font-weight:600">${m.best_name}</div>
          <div style="color:#64748b;font-size:10px">${m.entity_type} · ${sim}% match · ${m.match_type}</div>
          <div style="color:#475569;font-size:10px">${invs}</div>
          <div style="color:#334155;font-size:10px;font-style:italic">${m.names.join(' / ')}</div>
        </div>`;
      }
    }

    list.innerHTML = html;

    // Open the section header
    const header = section.querySelector('.section-header');
    const body = section.querySelector('.section-body');
    if (header && body) { header.classList.add('open'); body.classList.add('open'); }

    showBanner(`Found ${exact.length} confirmed + ${fuzzy.length} possible cross-links across ${d.investigations_scanned} investigations`, 'success');
  }).catch(e => showBanner('Cross-link scan error: ' + e, 'error'));
}

// ── Load sidebar data ──

function loadSidebarData() {
  loadInvestigationList();
  loadGapList();
  loadReportList();
  renderRecent();
  setSearchMode(searchMode);
  loadFileCorpusList();
}

function loadInvestigationList() {
  listInvestigations().then(d => {
    const sel = document.getElementById('navSelect');
    sel.innerHTML = '<option value="" disabled selected>Switch Investigation</option>';
    (d.investigations || []).forEach(inv => {
      const o = document.createElement('option');
      o.value = inv.dir;
      o.textContent = inv.name + ' (' + inv.entities + ')';
      if (inv.active) o.selected = true;
      sel.appendChild(o);
    });
  }).catch(() => {});
}

function loadGapList() {
  listGaps().then(d => {
    const el = document.getElementById('gapList');
    const gaps = (d.gaps || []).slice(0, 10);
    if (!gaps.length) {
      el.innerHTML = '<div style="color:var(--text-muted);padding:6px;font-size:12px">No gaps detected</div>';
      return;
    }
    el.innerHTML = gaps.map(g =>
      '<div class="gap-card' + (g.researched ? ' researched' : '') + '">' +
      '<span style="color:var(--text)">' + g.a_name + '</span> ' +
      '<span style="color:var(--text-muted)">&harr;</span> ' +
      '<span style="color:var(--text)">' + g.c_name + '</span>' +
      '<div style="color:var(--text-muted);font-size:10px;margin-top:2px">via ' + g.b_name + ' &middot; score ' + g.score + (g.researched ? ' &check;' : '') + '</div></div>'
    ).join('');
  }).catch(() => {});
}

function loadReportList() {
  listReports().then(d => {
    nodeReports = {};
    (d.reports || []).forEach(r => { nodeReports[r.id] = r; });
  }).catch(() => {});
}

// ── File & Document Corpus Panel ──

let _ingestActive = false;
let _ingestFolder = '';

function openFileBrowserForIngest() {
  openFileBrowser();
  window._fileBrowserMode = 'ingest';
}

function fileDragOver(e) {
  e.preventDefault();
  document.getElementById('fileDropZone').classList.add('dragover');
}

function fileDragLeave(e) {
  document.getElementById('fileDropZone').classList.remove('dragover');
}

function fileDrop(e) {
  e.preventDefault();
  document.getElementById('fileDropZone').classList.remove('dragover');
  // Browser security: can't get full path from drag-drop — open browser instead
  openFileBrowserForIngest();
}

function startFolderIngest(folderPath) {
  if (_ingestActive) { showBanner('Already processing a folder', 'error'); return; }
  _ingestFolder = folderPath;

  // Count first
  apiPost('/ingest/count', { path: folderPath }).then(d => {
    const count = d.count || 0;
    if (count === 0) { showBanner('No processable documents found in that folder', 'error'); return; }

    const go = count > 50
      ? confirm(`Found ${count} documents in:\n${folderPath}\n\nThis will process them in batches of 10.\nLarge collections may use significant API credits.\n\nProceed?`)
      : true;
    if (!go) return;

    _ingestActive = true;
    showIngestProgress(0, count, 'Starting...');
    runIngestBatch(folderPath, 0, count);
  });
}

function runIngestBatch(folder, batchIndex, totalDocs) {
  apiPost('/ingest/batch', { path: folder, batch_index: batchIndex }).then(d => {
    if (!d.success) {
      _ingestActive = false;
      hideIngestProgress();
      showBanner('Ingest error: ' + (d.error || 'unknown'), 'error');
      return;
    }

    const pct = d.progress_pct || 0;
    showIngestProgress(pct, totalDocs, `Batch ${batchIndex + 1}: ${d.entities_found || 0} entities found from ${d.docs_in_batch || 0} docs`);

    // If entities found, show them in a banner and let the chat agent know
    if ((d.entities || []).length > 0) {
      showBanner(`Batch ${batchIndex + 1}: found ${d.entities.length} entities — sending to investigator for review`, 'info');
      // Notify chat agent
      const msg = `Document batch ${batchIndex + 1} from folder "${folder}" processed. Found ${d.entities.length} entities:\n` +
        d.entities.slice(0, 10).map(e => `- ${e.name} (${e.type})`).join('\n') +
        (d.entities.length > 10 ? `\n... and ${d.entities.length - 10} more` : '') +
        '\n\nShould I add these to the investigation graph?';
      if (typeof addChatMessage === 'function') {
        addChatMessage('system', msg);
      }
    }

    if (d.has_more) {
      // Small pause between batches to avoid hammering the API
      setTimeout(() => runIngestBatch(folder, batchIndex + 1, totalDocs), 500);
    } else {
      _ingestActive = false;
      hideIngestProgress();
      showBanner(`Done! Processed ${totalDocs} documents from ${folder.split('/').pop()}`, 'success');
      loadFileCorpusList();
      // Tell chat agent
      if (typeof addChatMessage === 'function') {
        addChatMessage('system', `Finished processing all ${totalDocs} documents from folder: ${folder}`);
      }
    }
  }).catch(e => {
    _ingestActive = false;
    hideIngestProgress();
    showBanner('Batch error: ' + e, 'error');
  });
}

function showIngestProgress(pct, total, label) {
  const el = document.getElementById('fileIngestProgress');
  const bar = document.getElementById('fileProgressBar');
  const lbl = document.getElementById('fileProgressLabel');
  if (!el) return;
  el.style.display = '';
  if (bar) bar.style.width = pct + '%';
  if (lbl) lbl.textContent = label + ` (${pct}%)`;
}

function hideIngestProgress() {
  const el = document.getElementById('fileIngestProgress');
  if (el) el.style.display = 'none';
}

function loadFileCorpusList() {
  apiPost('/files/memory').then(d => {
    const el = document.getElementById('fileCorpusList');
    if (!el) return;
    const corpora = d.corpora || [];
    const files = d.individual_files || [];
    if (!corpora.length && !files.length) {
      el.innerHTML = '<div style="color:var(--text-muted);font-size:10px;padding:4px 0">No documents loaded yet</div>';
      return;
    }
    let html = '';
    for (const c of corpora) {
      const name = c.label || c.path.split('/').pop();
      const inv = c.investigation ? ` · ${c.investigation}` : '';
      html += `<div class="corpus-item">
        <span class="corpus-icon">&#128193;</span>
        <div class="corpus-info">
          <div class="corpus-name" title="${c.path}">${name}</div>
          <div class="corpus-meta">${c.doc_count || '?'} docs${inv}</div>
        </div>
        <button class="corpus-btn" onclick="startFolderIngest('${c.path.replace(/'/g, "\\'")}')">Re-scan</button>
      </div>`;
    }
    el.innerHTML = html;
  }).catch(() => {});
}

// Hook confirmFileBrowser for ingest mode
document.addEventListener('DOMContentLoaded', function() {
  // Patch confirmFileBrowser to handle ingest mode
  const _patchFileBrowser = () => {
    if (typeof confirmFileBrowser !== 'function') { setTimeout(_patchFileBrowser, 200); return; }
    const _orig = confirmFileBrowser;
    confirmFileBrowser = function() {
      const mode = window._fileBrowserMode;
      if (mode === 'ingest') {
        window._fileBrowserMode = null;
        const path = typeof fileBrowserSelected !== 'undefined' && fileBrowserSelected
          ? fileBrowserSelected
          : (typeof fileBrowserPath !== 'undefined' ? fileBrowserPath : '');
        closeFileBrowser();
        if (path) startFolderIngest(path);
      } else {
        _orig();
      }
    };
  };
  _patchFileBrowser();
  loadFileCorpusList();
});
