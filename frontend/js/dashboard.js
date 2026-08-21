/**
 * VISION AI — Dashboard Module
 * Detailed system stats with SVG gauges, polling via /api/system/stats
 * Note: Basic telemetry (cpu/ram/battery) is also fetched by app.js via /api/telemetry.
 *       This module provides the richer /api/system/stats endpoint data for the dashboard page.
 */

const VisionDashboard = (() => {
  let pollTimer = null;
  const POLL_INTERVAL = 3000;
  let lastStats = null;
  let isPageActive = false;

  function init() {
    // Dashboard starts inactive; polling begins when user navigates to it
  }

  function refresh() {
    isPageActive = true;
    fetchStats();
    startPolling();
  }

  function startPolling() {
    stopPolling();
    pollTimer = setInterval(fetchStats, POLL_INTERVAL);
  }

  function stopPolling() {
    if (pollTimer) { clearInterval(pollTimer); pollTimer = null; }
    isPageActive = false;
  }

  async function fetchStats() {
    try {
      const res = await fetch('/api/system/stats');
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const stats = await res.json();
      lastStats = stats;
      renderStats(stats);
    } catch (err) {
      console.debug('[Dashboard] Stats fetch failed:', err.message);
    }
  }

  function renderStats(s) {
    // ── Stat Cards ──
    updateText('stat-cpu-val', `${s.cpu.percent}%`);
    updateText('stat-cpu-label', `CPU (${s.cpu.core_count} cores @ ${s.cpu.frequency_ghz} GHz)`);

    updateText('stat-ram-val', `${s.ram.percent}% — ${s.ram.used_gb} / ${s.ram.total_gb} GB`);
    updateText('stat-ram-label', 'RAM');

    if (s.battery) {
      updateText('stat-bat-val', `${s.battery.percent}% ${s.battery.power_plugged ? '⚡ Charging' : '🔋'}`);
      updateText('stat-bat-label', 'Battery');
    } else {
      updateText('stat-bat-val', 'N/A');
      updateText('stat-bat-label', 'No battery');
    }

    const mainDisk = s.storage && s.storage[0];
    if (mainDisk) {
      updateText('stat-disk-val', `${mainDisk.percent}%`);
      updateText('stat-disk-label', `Disk — ${mainDisk.used_gb} / ${mainDisk.total_gb} GB`);
    }

    // ── SVG Gauges ──
    if (typeof VisionApp !== 'undefined') {
      const cpuColor = s.cpu.percent > 80 ? 'var(--danger)' : (s.cpu.percent > 50 ? 'var(--warning)' : 'var(--primary)');
      const ramColor = s.ram.percent > 80 ? 'var(--danger)' : 'var(--secondary)';
      const batPct = s.battery ? s.battery.percent : 0;
      const batColor = (s.battery && s.battery.percent < 20) ? 'var(--danger)' : 'var(--accent)';

      VisionApp.updateGauge('gauge-cpu', s.cpu.percent, cpuColor);
      VisionApp.updateGauge('gauge-ram', s.ram.percent, ramColor);
      VisionApp.updateGauge('gauge-bat', batPct, batColor);
    }

    // ── Gauge Value Text ──
    updateText('gauge-cpu-val', `${Math.round(s.cpu.percent)}%`);
    updateText('gauge-ram-val', `${Math.round(s.ram.percent)}%`);
    updateText('gauge-bat-val', s.battery ? `${Math.round(s.battery.percent)}%` : 'N/A');

    // ── CPU Per-Core Bars ──
    renderCoreBars(s.cpu.cores);

    // ── Top Processes ──
    renderProcesses(s.top_processes);

    // ── Network ──
    updateText('net-sent', `${s.network.bytes_sent_mb} MB`);
    updateText('net-recv', `${s.network.bytes_recv_mb} MB`);

    // ── Storage Cards ──
    renderStorage(s.storage);

    // ── Uptime ──
    updateText('sys-uptime', formatUptime(s.uptime_seconds));

    // ── Load Balancer ──
    if (s.load_balancer) {
      updateText('lb-strategy', s.load_balancer.strategy);
      updateText('lb-primary', s.load_balancer.primary_model);
      updateText('lb-providers', `${s.load_balancer.provider_count} endpoints`);
    }
  }

  function renderCoreBars(cores) {
    const container = document.getElementById('cpu-cores');
    if (!container || !cores) return;

    container.innerHTML = cores.map((val, i) => {
      const color = val > 80 ? 'var(--danger)' : (val > 50 ? 'var(--warning)' : 'var(--primary)');
      return `<div style="flex:1; height:${Math.max(val, 3)}%; background:${color}; border-radius:3px 3px 0 0; transition: height 0.8s var(--ease-out);" title="Core ${i}: ${val}%"></div>`;
    }).join('');
  }

  function renderProcesses(procs) {
    const tbody = document.getElementById('proc-table-body');
    if (!tbody || !procs) return;

    tbody.innerHTML = procs.map(p => `
      <tr>
        <td class="truncate" style="max-width:180px; color: var(--text-primary); font-weight: 500;">${escapeHtml(p.name)}</td>
        <td class="font-mono">${p.cpu}%</td>
        <td class="font-mono">${p.mem_mb} MB</td>
      </tr>
    `).join('');
  }

  function renderStorage(disks) {
    const container = document.getElementById('storage-list');
    if (!container || !disks) return;

    container.innerHTML = disks.map(d => `
      <div style="margin-bottom: var(--sp-3);">
        <div style="display: flex; justify-content: space-between; margin-bottom: 4px;">
          <span class="text-sm fw-medium">${escapeHtml(d.device)}</span>
          <span class="text-xs text-muted">${d.free_gb} GB free</span>
        </div>
        <div class="progress-bar">
          <div class="progress-fill" style="width: ${d.percent}%; ${d.percent > 85 ? 'background: var(--danger);' : ''}"></div>
        </div>
      </div>
    `).join('');
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

  function updateText(id, value) {
    const el = document.getElementById(id);
    if (el) el.textContent = value;
  }

  function escapeHtml(str) {
    const el = document.createElement('span');
    el.textContent = str || '';
    return el.innerHTML;
  }

  return { init, refresh, startPolling, stopPolling, fetchStats };
})();
