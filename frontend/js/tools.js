/**
 * VISION AI — Tools Module
 * Searchable tool grid, categories, execution panel, history log
 */

const VisionTools = (() => {
  let allTools = [];
  let filteredTools = [];
  let searchInput = null;
  let selectedTool = null;

  // Tool name → icon + category mapping
  const toolMeta = {
    // Browser
    open_browser: { icon: '🌐', cat: 'Browser' },
    browser_navigate: { icon: '🧭', cat: 'Browser' },
    browser_click: { icon: '👆', cat: 'Browser' },
    browser_type_text: { icon: '⌨️', cat: 'Browser' },
    browser_scroll: { icon: '📜', cat: 'Browser' },
    browser_screenshot: { icon: '📸', cat: 'Browser' },
    close_browser: { icon: '❌', cat: 'Browser' },
    // File
    read_file: { icon: '📄', cat: 'Files' },
    write_file: { icon: '✏️', cat: 'Files' },
    list_directory: { icon: '📁', cat: 'Files' },
    move_file: { icon: '📦', cat: 'Files' },
    delete_file: { icon: '🗑️', cat: 'Files' },
    search_files: { icon: '🔍', cat: 'Files' },
    organize_folder: { icon: '🗂️', cat: 'Files' },
    // System
    run_terminal: { icon: '💻', cat: 'System' },
    get_system_stats: { icon: '📊', cat: 'System' },
    execute_python: { icon: '🐍', cat: 'System' },
    // Media
    play_youtube_video: { icon: '▶️', cat: 'Media' },
    control_volume: { icon: '🔊', cat: 'Media' },
    control_brightness: { icon: '🔆', cat: 'Media' },
    // Communication
    send_whatsapp: { icon: '💬', cat: 'Communication' },
    send_email: { icon: '📧', cat: 'Communication' },
    // Memory
    remember: { icon: '🧠', cat: 'Memory' },
    forget: { icon: '🗑️', cat: 'Memory' },
    recall_memories: { icon: '💭', cat: 'Memory' },
    // Input
    type_text_into_application: { icon: '⌨️', cat: 'Input' },
    press_hotkey: { icon: '🎹', cat: 'Input' },
    // Mobile
    unlock_phone: { icon: '📱', cat: 'Mobile' },
    // Reminder
    set_reminder: { icon: '⏰', cat: 'Reminders' },
    // Server
    ssh_run: { icon: '🖥️', cat: 'Server' },
    // Web
    web_search: { icon: '🔎', cat: 'Web' },
    // Printer
    print_document: { icon: '🖨️', cat: 'Hardware' },
  };

  function init() {
    searchInput = document.getElementById('tools-search');
    if (searchInput) {
      searchInput.addEventListener('input', debounce(filterTools, 150));
    }
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
        container.innerHTML = `<div class="empty-state"><div class="empty-state-icon">🔧</div><div class="empty-state-title">Could not load tools</div><div class="empty-state-text">Make sure the VISION backend is running.</div></div>`;
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
      container.innerHTML = `<div class="empty-state" style="grid-column: 1/-1;"><div class="empty-state-icon">🔍</div><div class="empty-state-title">No tools found</div></div>`;
      return;
    }

    // Group by category
    const grouped = {};
    tools.forEach(t => {
      const name = t.function?.name || 'unknown';
      const meta = toolMeta[name] || { icon: '🔧', cat: 'Other' };
      if (!grouped[meta.cat]) grouped[meta.cat] = [];
      grouped[meta.cat].push({ ...t, meta });
    });

    let html = '';
    Object.entries(grouped).forEach(([cat, items]) => {
      html += `<div class="tools-category-header" style="grid-column: 1/-1;">
        <span class="text-sm fw-semibold text-muted uppercase ls-wider">${cat}</span>
        <span class="badge badge-info">${items.length}</span>
      </div>`;

      items.forEach(t => {
        const name = t.function?.name || 'unknown';
        const desc = t.function?.description || '';
        const icon = t.meta.icon;

        html += `
          <div class="tool-card" data-tool="${escapeHtml(name)}" onclick="VisionTools.selectTool('${name}')">
            <div class="tool-card-icon">${icon}</div>
            <div class="tool-card-name">${formatToolName(name)}</div>
            <div class="tool-card-desc">${escapeHtml(desc)}</div>
          </div>
        `;
      });
    });

    container.innerHTML = html;
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

    let fieldsHtml = '';
    Object.entries(params).forEach(([key, prop]) => {
      const isReq = required.includes(key);
      fieldsHtml += `
        <div style="margin-bottom: var(--sp-3);">
          <label class="text-sm fw-medium" style="display:block; margin-bottom:4px; color: var(--text-secondary);">
            ${key} ${isReq ? '<span style="color: var(--accent-danger);">*</span>' : ''}
            <span class="text-xs text-muted">(${prop.type})</span>
          </label>
          <input class="input-field tool-arg-input" data-param="${key}" type="text"
                 placeholder="${prop.description || key}" style="font-size: var(--fs-sm);">
        </div>
      `;
    });

    panel.innerHTML = `
      <div class="card" style="border-color: var(--accent-primary); border-width: 1px;">
        <div class="card-header">
          <div class="card-title">
            <span class="card-title-icon">${(toolMeta[fn.name] || {}).icon || '🔧'}</span>
            <span class="font-mono">${fn.name}</span>
          </div>
          <button class="btn btn-sm btn-primary" onclick="VisionTools.executeTool()">▶ Run</button>
        </div>
        <p class="text-sm text-muted" style="margin-bottom: var(--sp-4);">${escapeHtml(fn.description)}</p>
        ${fieldsHtml || '<p class="text-xs text-muted">No parameters required.</p>'}
        <div id="tool-exec-result" style="margin-top: var(--sp-4);"></div>
      </div>
    `;
    panel.style.display = 'block';
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
      resultEl.innerHTML = '<div class="text-sm text-muted"><span class="splash-spinner" style="display:inline-block; width:12px; height:12px; margin-right:8px; vertical-align:middle;"></span>Executing...</div>';
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
          <div class="text-xs fw-semibold" style="color: var(--accent-secondary); margin-bottom: 4px;">✅ Result</div>
          <pre style="background: var(--bg-code); padding: var(--sp-3); border-radius: var(--radius-md); font-size: var(--fs-sm); max-height: 200px; overflow: auto; border: 1px solid var(--border-subtle);">${escapeHtml(resultStr)}</pre>
        `;
      }

      VisionApp.showToast(`Tool "${formatToolName(selectedTool.function.name)}" executed!`, 'success');
      VisionApp.addEvent('tool', `Executed ${selectedTool.function.name}`);
    } catch (err) {
      if (resultEl) {
        resultEl.innerHTML = `<div class="text-sm" style="color: var(--accent-danger);">❌ Error: ${escapeHtml(err.message)}</div>`;
      }
      VisionApp.showToast('Tool execution failed', 'error');
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

  function debounce(fn, delay) {
    let timer;
    return (...args) => { clearTimeout(timer); timer = setTimeout(() => fn(...args), delay); };
  }

  return { init, fetchTools, selectTool, executeTool };
})();
