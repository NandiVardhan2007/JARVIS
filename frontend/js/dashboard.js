/**
 * VISION AI — Dashboard Module
 * Real-time system stats with animated SVG gauges, polling every 3s
 */

const VisionDashboard = (() => {
  let pollTimer = null;
  const POLL_INTERVAL = 3000;
  let lastStats = null;

  function init() {
    fetchStats();
    startPolling();
  }

  function startPolling() {
    stopPolling();
    pollTimer = setInterval(fetchStats, POLL_INTERVAL);
  }

  function stopPolling() {
    if (pollTimer) { clearInterval(pollTimer); pollTimer = null; }
  }

  async function fetchStats() {
    try {
      const res = await fetch('/api/system/stats');
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const stats = await res.json();
      lastStats = stats;
      renderStats(stats);
    } catch (err) {
      // Silently retry on next poll
      console.debug('[Dashboard] Stats fetch failed:', err.message);
    }
  }

  function renderStats(s) {
    // ── Stat Cards ──
    updateText('stat-cpu-val', `${s.cpu.percent}%`);
    updateText('stat-cpu-label', `${s.cpu.core_count} cores @ ${s.cpu.frequency_ghz} GHz`);

    updateText('stat-ram-val', `${s.ram.percent}%`);
    updateText('stat-ram-label', `${s.ram.used_gb} / ${s.ram.total_gb} GB`);

    if (s.battery) {
      updateText('stat-bat-val', `${s.battery.percent}%`);
      updateText('stat-bat-label', s.battery.power_plugged ? '⚡ Plugged In' : '🔋 On Battery');
    } else {
      updateText('stat-bat-val', 'N/A');
      updateText('stat-bat-label', 'No battery');
    }

    const mainDisk = s.storage && s.storage[0];
    if (mainDisk) {
      updateText('stat-disk-val', `${mainDisk.percent}%`);
      updateText('stat-disk-label', `${mainDisk.used_gb} / ${mainDisk.total_gb} GB`);
    }

    // ── SVG Gauges ──
    updateGauge('gauge-cpu', s.cpu.percent);
    updateGauge('gauge-ram', s.ram.percent);
    updateGauge('gauge-bat', s.battery ? s.battery.percent : 0);

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
    updateText('lb-strategy', s.load_balancer.strategy);
    updateText('lb-primary', s.load_balancer.primary_model);
    updateText('lb-providers', `${s.load_balancer.provider_count} endpoints`);
  }

  function updateGauge(id, percent) {
    const el = document.getElementById(id);
    if (!el) return;
    const circle = el.querySelector('.gauge-fill');
    if (!circle) return;

    const radius = parseFloat(circle.getAttribute('r'));
    const circumference = 2 * Math.PI * radius;
    const offset = circumference - (percent / 100) * circumference;

    circle.style.strokeDasharray = circumference;
    circle.style.strokeDashoffset = offset;

    // Dynamic color based on value
    let color;
    if (percent < 50) color = '#00d4aa';
    else if (percent < 75) color = '#ff9f43';
    else color = '#ff6b6b';
    circle.style.stroke = color;
  }

  function renderCoreBars(cores) {
    const container = document.getElementById('cpu-cores');
    if (!container || !cores) return;

    container.innerHTML = cores.map((val, i) => {
      let color;
      if (val < 50) color = 'var(--accent-secondary)';
      else if (val < 75) color = 'var(--accent-warning)';
      else color = 'var(--accent-danger)';

      return `
        <div class="core-bar-wrapper" data-tooltip="Core ${i}: ${val}%">
          <div class="core-bar" style="height: ${Math.max(val, 3)}%; background: ${color};"></div>
        </div>
      `;
    }).join('');
  }

  function renderProcesses(procs) {
    const tbody = document.getElementById('proc-table-body');
    if (!tbody || !procs) return;

    tbody.innerHTML = procs.map(p => `
      <tr>
        <td style="color: var(--text-primary); font-weight: 500;">${escapeHtml(p.name)}</td>
        <td><span class="badge badge-info">${p.cpu}%</span></td>
        <td>${p.mem_mb} MB</td>
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
          <div class="progress-fill" style="width: ${d.percent}%; ${d.percent > 85 ? 'background: linear-gradient(90deg, var(--accent-warning), var(--accent-danger));' : ''}"></div>
        </div>
      </div>
    `).join('');
  }

  function formatUptime(secs) {
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

  return { init, startPolling, stopPolling, fetchStats };
})();
