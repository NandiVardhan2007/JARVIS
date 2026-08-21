/**
 * VISION AI — App Shell Orchestrator v2.0
 * Page routing, sidebar, splash, command palette, telemetry, icon management
 */

const VisionApp = (() => {
  let currentPage = 'voice';
  let bootStartTime = null;
  let uptimeInterval = null;
  let telemetryInterval = null;
  let connectionStartTime = Date.now();

  // Module instances (loaded externally)
  const modules = {};

  function init() {
    bootStartTime = Date.now();
    console.log('[VISION] App init started');

    // 1. Boot Splash
    runSplashSequence();

    // 2. Initialize Lucide Icons
    initIcons();

    // 3. Set up navigation
    setupNavigation();

    // 4. Set up sidebar collapse
    setupSidebar();

    // 5. Set up command palette
    setupCommandPalette();

    // 6. Set up keyboard shortcuts
    setupKeyboardShortcuts();

    // 7. Init 3D Orb
    if (typeof VisionOrb !== 'undefined') VisionOrb.init();

    // 8. Init Voice Engine
    if (typeof VisionVoice !== 'undefined') VisionVoice.init();

    // 9. Init Transcript module
    if (typeof VisionTranscript !== 'undefined') VisionTranscript.init();

    // 10. Init Task Tracker
    if (typeof VisionTaskTracker !== 'undefined') VisionTaskTracker.init();

    // 11. Init Chat Module
    if (typeof VisionChat !== 'undefined') VisionChat.init();

    // 12. Init Dashboard
    if (typeof VisionDashboard !== 'undefined') VisionDashboard.init();

    // 13. Init Memory Module
    if (typeof VisionMemory !== 'undefined') VisionMemory.init();

    // 14. Init Tools Module
    if (typeof VisionTools !== 'undefined') VisionTools.init();

    // 15. Start Telemetry Loop
    startTelemetry();

    // 16. Start Uptime Counter
    startUptimeCounter();

    // 17. Set up gauge SVGs
    initGauges();

    console.log('[VISION] App init complete');
  }

  // ── Splash Screen ──
  function runSplashSequence() {
    const splash = document.getElementById('splash-screen');
    const progressFill = document.getElementById('splash-progress-fill');
    const statusText = document.getElementById('splash-status-text');
    if (!splash) return;

    function dismissSplash() {
      splash.classList.add('hidden');
      setTimeout(() => { splash.style.display = 'none'; }, 500);
    }

    // Click or key to immediately dismiss
    splash.addEventListener('click', dismissSplash);
    document.addEventListener('keydown', dismissSplash, { once: true });

    // Hard fallback: never get stuck on splash under any circumstances
    const fallbackTimer = setTimeout(dismissSplash, 1500);

    const stages = [
      { progress: 30, text: 'Initializing Neural Core...' },
      { progress: 65, text: 'Loading 3D Quantum Engine...' },
      { progress: 90, text: 'Activating Voice Pipeline...' },
      { progress: 100, text: 'VISION Online — Welcome.' }
    ];

    let i = 0;
    function nextStage() {
      if (i >= stages.length) {
        clearTimeout(fallbackTimer);
        setTimeout(dismissSplash, 200);
        return;
      }
      if (progressFill) progressFill.style.width = stages[i].progress + '%';
      if (statusText) statusText.textContent = stages[i].text;
      i++;
      setTimeout(nextStage, 140);
    }
    setTimeout(nextStage, 80);
  }

  // ── Icons ──
  function initIcons() {
    if (window.lucide && lucide.createIcons) {
      lucide.createIcons();
    }
  }

  // ── SVG Gauges ──
  function initGauges() {
    ['gauge-cpu', 'gauge-ram', 'gauge-bat'].forEach(id => {
      const svg = document.getElementById(id);
      if (!svg) return;
      const fill = svg.querySelector('.gauge-fill');
      if (!fill) return;
      const radius = 40;
      const circumference = 2 * Math.PI * radius;
      fill.style.strokeDasharray = circumference;
      fill.style.strokeDashoffset = circumference;
      fill.style.stroke = 'var(--primary)';
      fill.dataset.circumference = circumference;
    });
  }

  function updateGauge(id, percent, color) {
    const svg = document.getElementById(id);
    if (!svg) return;
    const fill = svg.querySelector('.gauge-fill');
    if (!fill) return;
    const circumference = parseFloat(fill.dataset.circumference);
    if (!circumference) return;
    const offset = circumference - (percent / 100) * circumference;
    fill.style.strokeDashoffset = offset;
    if (color) fill.style.stroke = color;
  }

  // ── Navigation ──
  function setupNavigation() {
    document.querySelectorAll('.nav-item[data-page]').forEach(item => {
      item.addEventListener('click', () => {
        navigateTo(item.dataset.page);
      });
    });
  }

  function navigateTo(page) {
    if (currentPage === page) return;
    currentPage = page;

    // Update nav items
    document.querySelectorAll('.nav-item[data-page]').forEach(item => {
      item.classList.toggle('active', item.dataset.page === page);
    });

    // Update pages
    document.querySelectorAll('.page').forEach(p => {
      p.classList.toggle('active', p.id === `page-${page}`);
    });

    // Trigger data refresh for page
    if (page === 'dashboard' && typeof VisionDashboard !== 'undefined') {
      VisionDashboard.refresh();
    } else if (page === 'memory' && typeof VisionMemory !== 'undefined') {
      VisionMemory.refresh();
    } else if (page === 'tools' && typeof VisionTools !== 'undefined') {
      VisionTools.refresh();
    }
  }

  // ── Sidebar ──
  function setupSidebar() {
    const sidebar = document.getElementById('sidebar');
    const collapseBtn = document.getElementById('sidebar-collapse-btn');
    if (!sidebar || !collapseBtn) return;

    collapseBtn.addEventListener('click', () => {
      sidebar.classList.toggle('collapsed');
      const isCollapsed = sidebar.classList.contains('collapsed');
      collapseBtn.querySelector('.nav-label').textContent = isCollapsed ? '' : 'Collapse';
      const iconEl = collapseBtn.querySelector('[data-lucide]');
      if (iconEl) {
        iconEl.setAttribute('data-lucide', isCollapsed ? 'panel-left-open' : 'panel-left-close');
        initIcons();
      }
    });
  }

  // ── Command Palette ──
  function setupCommandPalette() {
    const palette = document.getElementById('command-palette');
    const input = document.getElementById('cmd-palette-input');
    const results = document.getElementById('cmd-palette-results');
    const trigger = document.getElementById('cmd-palette-trigger');
    if (!palette || !input) return;

    if (trigger) {
      trigger.addEventListener('click', () => openCommandPalette());
    }

    const commands = [
      { icon: 'radio', label: 'Voice HUD', action: () => navigateTo('voice') },
      { icon: 'message-square', label: 'Open Chat', action: () => navigateTo('chat') },
      { icon: 'bar-chart-3', label: 'Dashboard', action: () => navigateTo('dashboard') },
      { icon: 'brain', label: 'Memory Explorer', action: () => navigateTo('memory') },
      { icon: 'wrench', label: 'Tools', action: () => navigateTo('tools') },
      { icon: 'check-square', label: 'Task Tracker', action: () => {
        const modal = document.getElementById('task-tracker-modal');
        if (modal) { modal.classList.add('active'); VisionTaskTracker.fetchTaskDashboard(); }
      }},
      { icon: 'mic', label: 'Toggle Mute', action: () => VisionVoice.toggleMute() },
      { icon: 'radio', label: 'Toggle Hands-Free', action: () => VisionVoice.toggleHandsFree() },
    ];

    let selectedIdx = 0;

    function openCommandPalette() {
      palette.classList.add('visible');
      input.value = '';
      input.focus();
      renderCommands(commands);
    }

    function closeCommandPalette() {
      palette.classList.remove('visible');
      input.value = '';
    }

    function renderCommands(cmds) {
      if (!results) return;
      results.innerHTML = cmds.map((c, i) => `
        <div class="cmd-palette-item ${i === selectedIdx ? 'selected' : ''}" data-cmd-idx="${i}">
          <span class="cmd-palette-item-icon"><i data-lucide="${c.icon}" class="icon-sm"></i></span>
          <span class="cmd-palette-item-label">${c.label}</span>
        </div>
      `).join('');
      initIcons();

      results.querySelectorAll('.cmd-palette-item').forEach(el => {
        el.addEventListener('click', () => {
          const idx = parseInt(el.dataset.cmdIdx);
          if (cmds[idx]) cmds[idx].action();
          closeCommandPalette();
        });
      });
    }

    input.addEventListener('input', () => {
      const q = input.value.toLowerCase().trim();
      const filtered = q ? commands.filter(c => c.label.toLowerCase().includes(q)) : commands;
      selectedIdx = 0;
      renderCommands(filtered);
    });

    input.addEventListener('keydown', (e) => {
      const items = results.querySelectorAll('.cmd-palette-item');
      if (e.key === 'ArrowDown') { e.preventDefault(); selectedIdx = Math.min(selectedIdx + 1, items.length - 1); highlightItem(items); }
      else if (e.key === 'ArrowUp') { e.preventDefault(); selectedIdx = Math.max(selectedIdx - 1, 0); highlightItem(items); }
      else if (e.key === 'Enter') {
        e.preventDefault();
        const q = input.value.toLowerCase().trim();
        const filtered = q ? commands.filter(c => c.label.toLowerCase().includes(q)) : commands;
        if (filtered[selectedIdx]) filtered[selectedIdx].action();
        closeCommandPalette();
      }
      else if (e.key === 'Escape') { closeCommandPalette(); }
    });

    function highlightItem(items) {
      items.forEach((el, i) => el.classList.toggle('selected', i === selectedIdx));
    }

    palette.addEventListener('click', (e) => {
      if (e.target === palette) closeCommandPalette();
    });

    // Global open shortcut
    document.addEventListener('keydown', (e) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
        e.preventDefault();
        if (palette.classList.contains('visible')) closeCommandPalette();
        else openCommandPalette();
      }
    });
  }

  // ── Keyboard Shortcuts ──
  function setupKeyboardShortcuts() {
    document.addEventListener('keydown', (e) => {
      const cmdInput = document.getElementById('command-input');
      const chatInput = document.getElementById('chat-input');
      const isInInput = (document.activeElement === cmdInput || document.activeElement === chatInput || document.activeElement?.tagName === 'INPUT' || document.activeElement?.tagName === 'TEXTAREA');
      if (isInInput) return;

      if (e.key === 'Escape') {
        // Close modals
        const taskModal = document.getElementById('task-tracker-modal');
        if (taskModal?.classList.contains('active')) { taskModal.classList.remove('active'); return; }
        const cmdPalette = document.getElementById('command-palette');
        if (cmdPalette?.classList.contains('visible')) { cmdPalette.classList.remove('visible'); return; }
      }

      if (e.key === '1') navigateTo('voice');
      if (e.key === '2') navigateTo('chat');
      if (e.key === '3') navigateTo('dashboard');
      if (e.key === '4') navigateTo('memory');
      if (e.key === '5') navigateTo('tools');
    });
  }

  // ── Telemetry ──
  function startTelemetry() {
    async function fetchTelemetry() {
      try {
        const res = await fetch('/api/system/stats');
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        updateVitals(data);
      } catch (err) {
        // Server likely offline, show offline state
        const dot = document.getElementById('sidebar-status-dot');
        if (dot) dot.classList.add('offline');
      }
    }

    fetchTelemetry();
    telemetryInterval = setInterval(fetchTelemetry, 3000);
  }

  function updateVitals(data) {
    const cpu = (data.cpu && data.cpu.percent) || 0;
    const ramUsed = (data.ram && data.ram.used_gb) || 0;
    const ramTotal = (data.ram && data.ram.total_gb) || 0;
    const ramPct = (data.ram && data.ram.percent) || 0;
    const batteryPct = data.battery ? data.battery.percent : null;
    const batteryPlugged = data.battery ? data.battery.power_plugged : false;
    const disk = (data.storage && data.storage[0]) ? data.storage[0].percent : 0;

    // Voice HUD vitals
    setText('cpu-stat', `${cpu}%`);
    setText('ram-stat', `${ramUsed.toFixed(1)} / ${ramTotal.toFixed(1)} GB`);
    setText('battery-stat', batteryPct != null ? `${batteryPct}% ${batteryPlugged ? '⚡' : '🔋'}` : 'AC Power');

    setBarWidth('cpu-bar', cpu);
    setBarWidth('ram-bar', ramPct);
    setBarWidth('battery-bar', batteryPct || 100);

    // Dashboard gauges
    updateGauge('gauge-cpu', cpu, cpu > 80 ? 'var(--danger)' : (cpu > 50 ? 'var(--warning)' : 'var(--primary)'));
    updateGauge('gauge-ram', ramPct, ramPct > 80 ? 'var(--danger)' : 'var(--secondary)');
    updateGauge('gauge-bat', batteryPct || 100, batteryPct && batteryPct < 20 ? 'var(--danger)' : 'var(--accent)');

    setText('gauge-cpu-val', `${cpu}%`);
    setText('gauge-ram-val', `${ramPct}%`);
    setText('gauge-bat-val', batteryPct != null ? `${batteryPct}%` : 'N/A');

    setText('stat-cpu-val', `${cpu}%`);
    setText('stat-cpu-label', `CPU (${data.cpu?.core_count || '?'} cores)`);
    setText('stat-ram-val', `${ramPct}% — ${ramUsed.toFixed(1)} / ${ramTotal.toFixed(1)} GB`);
    setText('stat-ram-label', 'RAM');
    setText('stat-bat-val', batteryPct != null ? `${batteryPct}% ${batteryPlugged ? '⚡ Charging' : '🔋'}` : 'AC Power');
    setText('stat-bat-label', 'Battery');
    setText('stat-disk-val', `${disk}%`);
    setText('stat-disk-label', 'Disk Usage');
    setText('sys-uptime', data.uptime_seconds ? formatUptime(data.uptime_seconds) : '--');

    // CPU cores bar chart
    if (data.cpu && data.cpu.cores) renderCpuCores(data.cpu.cores);

    // Top processes
    if (data.top_processes) renderProcessTable(data.top_processes);

    // Load Balancer
    if (data.load_balancer) {
      setText('lb-strategy', data.load_balancer.strategy || '--');
      setText('lb-primary', data.load_balancer.primary_model || '--');
      setText('lb-providers', data.load_balancer.provider_count ? `${data.load_balancer.provider_count} endpoints` : '--');
    }

    // Storage
    if (data.storage) renderStorage(data.storage);

    // Sidebar online
    const dot = document.getElementById('sidebar-status-dot');
    if (dot) dot.classList.remove('offline');
  }

  function formatUptime(secs) {
    if (!secs) return '--';
    const h = Math.floor(secs / 3600);
    const m = Math.floor((secs % 3600) / 60);
    const s = secs % 60;
    if (h > 0) return `${h}h ${m}m`;
    if (m > 0) return `${m}m ${s}s`;
    return `${s}s`;
  }

  function renderCpuCores(cores) {
    const container = document.getElementById('cpu-cores');
    if (!container || !cores) return;

    container.innerHTML = cores.map((pct, i) => {
      const color = pct > 80 ? 'var(--danger)' : (pct > 50 ? 'var(--warning)' : 'var(--primary)');
      return `<div style="flex:1;height:${Math.max(4, pct)}%;background:${color};border-radius:3px 3px 0 0;transition:height 0.8s var(--ease-out);" title="Core ${i}: ${pct}%"></div>`;
    }).join('');
  }

  function renderProcessTable(procs) {
    const tbody = document.getElementById('proc-table-body');
    if (!tbody) return;
    tbody.innerHTML = procs.slice(0, 8).map(p => `
      <tr>
        <td class="truncate" style="max-width:180px;">${escapeHtml(p.name || 'Unknown')}</td>
        <td class="font-mono">${(p.cpu || 0).toFixed(1)}%</td>
        <td class="font-mono">${(p.memory || 0).toFixed(1)}%</td>
      </tr>
    `).join('');
  }

  function renderStorage(partitions) {
    const container = document.getElementById('storage-list');
    if (!container) return;
    container.innerHTML = partitions.slice(0, 4).map(p => `
      <div class="stat-row" style="margin-bottom:8px;">
        <div class="stat-label-row">
          <span class="text-xs text-muted">${escapeHtml(p.mountpoint || p.device)}</span>
          <span class="text-xs font-mono">${p.percent || 0}%</span>
        </div>
        <div class="progress-bar">
          <div class="progress-fill" style="width:${p.percent || 0}%;${p.percent > 85 ? 'background:var(--danger);' : ''}"></div>
        </div>
      </div>
    `).join('');
  }

  // ── Uptime Counter ──
  function startUptimeCounter() {
    uptimeInterval = setInterval(() => {
      const elapsed = Math.floor((Date.now() - connectionStartTime) / 1000);
      const h = String(Math.floor(elapsed / 3600)).padStart(2, '0');
      const m = String(Math.floor((elapsed % 3600) / 60)).padStart(2, '0');
      const s = String(elapsed % 60).padStart(2, '0');
      const formatted = `${h}:${m}:${s}`;
      setText('telemetry-uptime', formatted);
      setText('sidebar-uptime', formatted);
    }, 1000);
  }

  // ── Toast Notifications ──
  function showToast(message, type = 'info', duration = 4000) {
    const container = document.getElementById('toast-container');
    if (!container) return;

    const icons = { success: 'check-circle', error: 'alert-circle', warning: 'alert-triangle', info: 'info' };
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.innerHTML = `
      <span class="toast-icon"><i data-lucide="${icons[type] || 'info'}" class="icon-sm"></i></span>
      <span class="toast-message">${escapeHtml(message)}</span>
      <div class="toast-progress" style="animation-duration:${duration}ms;"></div>
    `;
    container.appendChild(toast);
    initIcons();

    setTimeout(() => {
      toast.classList.add('exiting');
      setTimeout(() => toast.remove(), 300);
    }, duration);
  }

  // ── Helpers ──
  function setText(id, val) {
    const el = document.getElementById(id);
    if (el) el.textContent = val;
  }

  function setBarWidth(id, pct) {
    const el = document.getElementById(id);
    if (el) el.style.width = `${Math.min(100, Math.max(0, pct))}%`;
  }

  function updateGauge(containerId, percent, strokeColor = 'var(--primary)') {
    const container = document.getElementById(containerId);
    if (!container) return;
    const fill = container.querySelector('.gauge-fill, .donut-fill');
    if (!fill) return;

    const radius = parseFloat(fill.getAttribute('r')) || 35;
    const circumference = 2 * Math.PI * radius;
    const clamped = Math.min(100, Math.max(0, percent));
    const offset = circumference - (clamped / 100) * circumference;

    fill.style.strokeDasharray = `${circumference}`;
    fill.style.strokeDashoffset = `${offset}`;
    if (strokeColor) fill.style.stroke = strokeColor;
  }

  function formatBytes(bytes) {
    if (!bytes) return '0 MB';
    const gb = bytes / (1024 * 1024 * 1024);
    if (gb > 1) return `${gb.toFixed(1)} GB`;
    return `${(bytes / (1024 * 1024)).toFixed(0)} MB`;
  }

  function escapeHtml(s) {
    if (!s) return '';
    const d = document.createElement('div');
    d.textContent = s; return d.innerHTML;
  }

  // Auto-init on DOMContentLoaded
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

  return { init, navigateTo, showToast, updateGauge };
})();
