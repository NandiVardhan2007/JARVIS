/**
 * VISION AI — Tools Module
 * Searchable tool grid, categories, execution panel, Lucide icons
 */

const VisionTools = (() => {
  let allTools = [];
  let filteredTools = [];
  let searchInput = null;
  let selectedTool = null;

  // Tool name → Lucide icon + category mapping
  const toolMeta = {
    // Browser
    open_browser:        { icon: 'globe',         cat: 'Browser' },
    browser_navigate:    { icon: 'compass',        cat: 'Browser' },
    browser_click:       { icon: 'mouse-pointer-click', cat: 'Browser' },
    browser_type_text:   { icon: 'keyboard',       cat: 'Browser' },
    browser_scroll:      { icon: 'move-vertical',  cat: 'Browser' },
    browser_screenshot:  { icon: 'camera',         cat: 'Browser' },
    close_browser:       { icon: 'x-circle',       cat: 'Browser' },
    // File
    read_file:           { icon: 'file-text',      cat: 'Files' },
    write_file:          { icon: 'edit-3',         cat: 'Files' },
    list_directory:      { icon: 'folder-open',    cat: 'Files' },
    move_file:           { icon: 'move',           cat: 'Files' },
    delete_file:         { icon: 'trash-2',        cat: 'Files' },
    search_files:        { icon: 'search',         cat: 'Files' },
    organize_folder:     { icon: 'folder-tree',    cat: 'Files' },
    // System
    run_terminal:        { icon: 'terminal',       cat: 'System' },
    get_system_stats:    { icon: 'bar-chart-3',    cat: 'System' },
    execute_python:      { icon: 'code',           cat: 'System' },
    // Media
    play_youtube_video:  { icon: 'play-circle',    cat: 'Media' },
    control_volume:      { icon: 'volume-2',       cat: 'Media' },
    control_brightness:  { icon: 'sun',            cat: 'Media' },
    // Communication
    send_whatsapp:       { icon: 'message-square', cat: 'Communication' },
    send_email:          { icon: 'mail',           cat: 'Communication' },
    // Memory
    remember:            { icon: 'brain',          cat: 'Memory' },
    forget:              { icon: 'eraser',         cat: 'Memory' },
    recall_memories:     { icon: 'lightbulb',      cat: 'Memory' },
    // Input
    type_text_into_application: { icon: 'type',    cat: 'Input' },
    press_hotkey:        { icon: 'command',         cat: 'Input' },
    // Mobile
    unlock_phone:        { icon: 'smartphone',     cat: 'Mobile' },
    // Reminder
    set_reminder:        { icon: 'alarm-clock',    cat: 'Reminders' },
    // Server
    ssh_run:             { icon: 'server',         cat: 'Server' },
    // Web
    web_search:          { icon: 'search',         cat: 'Web' },
    // Printer
    print_document:      { icon: 'printer',        cat: 'Hardware' },
  };

  function init() {
    searchInput = document.getElementById('tools-search');
    if (searchInput) {
      searchInput.addEventListener('input', debounce(filterTools, 150));
    }
  }

  function refresh() {
    fetchTools();
  }

  async function fetchTools() {
    try {
      const res = await fetch('/api/tools');
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      allTools = data.tools || [];
      filteredTools = allTools;
      renderTools(allTools);

      updateText('tools-count', allTools.length);
    } catch (err) {
      console.error('[Tools] Fetch failed:', err);
      const container = document.getElementById('tools-grid');
      if (container) {
        container.innerHTML = `<div class="empty-state" style="grid-column: 1/-1;"><div class="empty-state-icon">🔧</div><div class="empty-state-title">Could not load tools</div><div class="empty-state-text">Make sure the VISION backend is running.</div></div>`;
      }
    }
  }

  function filterTools() {
    const query = searchInput.value.toLowerCase().trim();
    if (!query) {
      filteredTools = allTools;
    } else {
      filteredTools = allTools.filter(t => {
        const name = t.function?.name || '';
        const desc = t.function?.description || '';
        const meta = toolMeta[name];
        const cat = meta ? meta.cat.toLowerCase() : '';
        return name.toLowerCase().includes(query) ||
               desc.toLowerCase().includes(query) ||
               cat.includes(query);
      });
    }
    renderTools(filteredTools);
  }

  function renderTools(tools) {
    const container = document.getElementById('tools-grid');
    if (!container) return;

    if (!tools.length) {
      container.innerHTML = `<div class="empty-state" style="grid-column: 1/-1;"><div class="empty-state-icon"><i data-lucide="search" class="icon-xl"></i></div><div class="empty-state-title">No tools found</div></div>`;
      refreshIcons();
      return;
    }

    // Group by category
    const grouped = {};
    tools.forEach(t => {
      const name = t.function?.name || 'unknown';
      const meta = toolMeta[name] || { icon: 'wrench', cat: 'Other' };
      if (!grouped[meta.cat]) grouped[meta.cat] = [];
      grouped[meta.cat].push({ ...t, meta });
    });

    let html = '';
    Object.entries(grouped).forEach(([cat, items]) => {
      html += `<div class="tools-category-header" style="grid-column: 1/-1;">
        <span class="text-sm fw-semibold text-muted uppercase ls-wider">${cat}</span>
        <span class="badge badge-primary">${items.length}</span>
      </div>`;

      items.forEach(t => {
        const name = t.function?.name || 'unknown';
        const desc = t.function?.description || '';
        const iconName = t.meta.icon;

        html += `
          <div class="tool-card" data-tool="${escapeHtml(name)}">
            <div class="tool-card-icon"><i data-lucide="${iconName}" class="icon-md"></i></div>
            <div class="tool-card-name">${formatToolName(name)}</div>
            <div class="tool-card-desc">${escapeHtml(desc)}</div>
          </div>
        `;
      });
    });

    container.innerHTML = html;
    refreshIcons();

    // Attach click handlers via delegation (replaces inline onclick)
    container.querySelectorAll('.tool-card[data-tool]').forEach(card => {
      card.addEventListener('click', () => selectTool(card.dataset.tool));
    });
  }

  function selectTool(name) {
    const tool = allTools.find(t => t.function?.name === name);
    if (!tool) return;
    selectedTool = tool;
    renderExecutionPanel(tool);
  }

  function renderExecutionPanel(tool) {
    const panel = document.getElementById('tool-exec-panel');
    if (!panel) return;

    const fn = tool.function;
    const params = fn.parameters?.properties || {};
    const required = fn.parameters?.required || [];
    const iconName = (toolMeta[fn.name] || {}).icon || 'wrench';

    let fieldsHtml = '';
    Object.entries(params).forEach(([key, prop]) => {
      const isReq = required.includes(key);
      fieldsHtml += `
        <div style="margin-bottom: var(--sp-3);">
          <label class="text-sm fw-medium" style="display:block; margin-bottom:4px; color: var(--text-secondary);">
            ${key} ${isReq ? '<span style="color: var(--danger);">*</span>' : ''}
            <span class="text-xs text-muted">(${prop.type})</span>
          </label>
          <input class="input-field tool-arg-input" data-param="${key}" type="text"
                 placeholder="${prop.description || key}" style="font-size: var(--fs-sm);">
        </div>
      `;
    });

    panel.innerHTML = `
      <div class="card" style="border-color: var(--primary);">
        <div class="card-header">
          <div class="card-title">
            <span class="card-title-icon"><i data-lucide="${iconName}" class="icon-md"></i></span>
            <span class="font-mono">${fn.name}</span>
          </div>
          <button class="btn btn-sm btn-primary" id="tool-run-btn">
            <i data-lucide="play" class="icon-sm"></i>
            <span>Run</span>
          </button>
        </div>
        <div class="card-body">
          <p class="text-sm text-muted" style="margin-bottom: var(--sp-4);">${escapeHtml(fn.description)}</p>
          ${fieldsHtml || '<p class="text-xs text-muted">No parameters required.</p>'}
          <div id="tool-exec-result" style="margin-top: var(--sp-4);"></div>
        </div>
      </div>
    `;
    panel.style.display = 'block';
    refreshIcons();

    // Attach run handler
    const runBtn = document.getElementById('tool-run-btn');
    if (runBtn) runBtn.addEventListener('click', executeTool);
  }

  async function executeTool() {
    if (!selectedTool) return;

    const inputs = document.querySelectorAll('.tool-arg-input');
    const args = {};
    inputs.forEach(inp => {
      const val = inp.value.trim();
      if (val) args[inp.dataset.param] = val;
    });

    const resultEl = document.getElementById('tool-exec-result');
    if (resultEl) {
      resultEl.innerHTML = '<div class="text-sm text-muted"><div class="splash-spinner" style="display:inline-block; width:12px; height:12px; margin-right:8px; vertical-align:middle;"></div>Executing...</div>';
    }

    try {
      const res = await fetch('/api/tools/execute', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ tool_name: selectedTool.function.name, arguments: args })
      });
      const data = await res.json();

      if (resultEl) {
        const resultStr = typeof data.result === 'string' ? data.result : JSON.stringify(data.result, null, 2);
        resultEl.innerHTML = `
          <div class="text-xs fw-semibold" style="color: var(--accent); margin-bottom: 4px;">✅ Result</div>
          <pre style="background: var(--bg-code); padding: var(--sp-3); border-radius: var(--radius-md); font-size: var(--fs-sm); max-height: 200px; overflow: auto; border: 1px solid var(--border-subtle);">${escapeHtml(resultStr)}</pre>
        `;
      }

      if (typeof VisionApp !== 'undefined') VisionApp.showToast(`Tool "${formatToolName(selectedTool.function.name)}" executed!`, 'success');
    } catch (err) {
      if (resultEl) {
        resultEl.innerHTML = `<div class="text-sm" style="color: var(--danger);">❌ Error: ${escapeHtml(err.message)}</div>`;
      }
      if (typeof VisionApp !== 'undefined') VisionApp.showToast('Tool execution failed', 'error');
    }
  }

  function formatToolName(name) {
    return name.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
  }

  function updateText(id, value) {
    const el = document.getElementById(id);
    if (el) el.textContent = value;
  }

  function escapeHtml(str) {
    const el = document.createElement('span');
    el.textContent = str || '';
    return el.innerHTML;
  }

  function refreshIcons() {
    if (window.lucide && lucide.createIcons) lucide.createIcons();
  }

  function debounce(fn, delay) {
    let timer;
    return (...args) => { clearTimeout(timer); timer = setTimeout(() => fn(...args), delay); };
  }

  return { init, refresh, fetchTools, selectTool, executeTool };
})();
