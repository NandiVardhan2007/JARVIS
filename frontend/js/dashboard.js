/**
 * VISION AI — Dashboard Module
 * Smooth System Telemetry with Animated Number Tweening, SVG Gauges, and Zero-Jank Diffing
 */

const VisionDashboard = (() => {
  let pollTimer = null;
  const POLL_INTERVAL = 2500;
  let lastStats = null;
  let isPageActive = false;
  const currentValues = {};

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
    isPageActive = true;
    pollTimer = setInterval(() => {
      const page = document.getElementById('page-dashboard');
      if (page && page.classList.contains('active') && !document.hidden) {
        fetchStats();
      }
    }, POLL_INTERVAL);
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

  // ── Smooth Number Interpolation (Tweening) ──
  function tweenNumber(elementId, targetValue, formatFn = (v) => `${Math.round(v)}%`, duration = 650) {
    const el = document.getElementById(elementId);
    if (!el) return;

    const startVal = (currentValues[elementId] !== undefined) ? currentValues[elementId] : targetValue;
    currentValues[elementId] = targetValue;

    if (Math.abs(targetValue - startVal) < 0.1) {
      el.textContent = formatFn(targetValue);
      return;
    }

    const startTime = performance.now();

    function step(currentTime) {
      const elapsed = currentTime - startTime;
      const progress = Math.min(elapsed / duration, 1.0);
      // Cubic Ease-Out
      const easeOut = 1 - Math.pow(1 - progress, 3);
      const current = startVal + (targetValue - startVal) * easeOut;

      el.textContent = formatFn(current);

      if (progress < 1.0) {
        requestAnimationFrame(step);
      } else {
        el.textContent = formatFn(targetValue);
      }
    }

    requestAnimationFrame(step);
  }

  function renderStats(s) {
    const cpu = s.cpu ? s.cpu.percent : 0;
    const ramPct = s.ram ? s.ram.percent : 0;
    const ramUsed = s.ram ? s.ram.used_gb : 0;
    const ramTotal = s.ram ? s.ram.total_gb : 0;
    const batPct = s.battery ? s.battery.percent : null;
    const batPlugged = s.battery ? s.battery.power_plugged : false;
    const mainDisk = s.storage && s.storage[0];
    const diskPct = mainDisk ? mainDisk.percent : 0;

    // ── Smooth Number Counters ──
    tweenNumber('stat-cpu-val', cpu, (v) => `${v.toFixed(1)}%`);
    updateText('stat-cpu-label', `CPU (${s.cpu?.core_count || '?'} cores @ ${s.cpu?.frequency_ghz || '?'} GHz)`);

    tweenNumber('stat-ram-val', ramPct, () => `${ramPct.toFixed(1)}% — ${ramUsed.toFixed(1)} / ${ramTotal.toFixed(1)} GB`);
    updateText('stat-ram-label', 'RAM');

    if (batPct != null) {
      tweenNumber('stat-bat-val', batPct, (v) => `${Math.round(v)}% ${batPlugged ? '⚡ Charging' : '🔋'}`);
      updateText('stat-bat-label', 'Battery');
    } else {
      updateText('stat-bat-val', 'AC Power');
      updateText('stat-bat-label', 'Power Source');
    }

    if (mainDisk) {
      tweenNumber('stat-disk-val', diskPct, (v) => `${v.toFixed(1)}%`);
      updateText('stat-disk-label', `Disk — ${mainDisk.used_gb} / ${mainDisk.total_gb} GB`);
    }

    // ── Smooth SVG Gauges ──
    if (typeof VisionApp !== 'undefined') {
      const cpuColor = cpu > 80 ? 'var(--danger)' : (cpu > 50 ? 'var(--warning)' : 'var(--primary)');
      const ramColor = ramPct > 80 ? 'var(--danger)' : 'var(--secondary)';
      const batColor = (batPct != null && batPct < 20) ? 'var(--danger)' : 'var(--accent)';

      VisionApp.updateGauge('gauge-cpu', cpu, cpuColor);
      VisionApp.updateGauge('gauge-ram', ramPct, ramColor);
      VisionApp.updateGauge('gauge-bat', batPct != null ? batPct : 100, batColor);
    }

    tweenNumber('gauge-cpu-val', cpu, (v) => `${Math.round(v)}%`);
    tweenNumber('gauge-ram-val', ramPct, (v) => `${Math.round(v)}%`);
    if (batPct != null) {
      tweenNumber('gauge-bat-val', batPct, (v) => `${Math.round(v)}%`);
    } else {
      updateText('gauge-bat-val', 'AC');
    }

    // ── Smooth CPU Per-Core Bars (Preserve DOM Nodes) ──
    renderCoreBars(s.cpu?.cores);

    // ── Smooth Process Table ──
    renderProcesses(s.top_processes);

    // ── Network Counters ──
    if (s.network) {
      updateText('net-sent', `${s.network.bytes_sent_mb} MB`);
      updateText('net-recv', `${s.network.bytes_recv_mb} MB`);
    }

    // ── Storage Partitions ──
    renderStorage(s.storage);

    // ── System Uptime ──
    if (s.uptime_seconds) {
      updateText('sys-uptime', formatUptime(s.uptime_seconds));
    }

    // ── Load Balancer Info ──
    if (s.load_balancer) {
      updateText('lb-strategy', s.load_balancer.strategy || '--');
      updateText('lb-primary', s.load_balancer.primary_model || '--');
      updateText('lb-providers', `${s.load_balancer.provider_count || 0} endpoints`);
    }
  }

  // ── Smooth Core Bars (Update Heights in Place) ──
  function renderCoreBars(cores) {
    const container = document.getElementById('cpu-cores');
    if (!container || !cores || cores.length === 0) return;

    let bars = container.querySelectorAll('.core-bar-item');

    if (bars.length !== cores.length) {
      container.innerHTML = cores.map((val, i) => {
        const color = val > 80 ? 'var(--danger)' : (val > 50 ? 'var(--warning)' : 'var(--primary)');
        return `<div class="core-bar-item" style="flex:1; height:${Math.max(val, 4)}%; background:${color}; border-radius:3px 3px 0 0; transition: height 0.8s cubic-bezier(0.4, 0, 0.2, 1), background-color 0.5s ease;" title="Core ${i}: ${val}%"></div>`;
      }).join('');
      return;
    }

    cores.forEach((val, i) => {
      const bar = bars[i];
      if (bar) {
        const color = val > 80 ? 'var(--danger)' : (val > 50 ? 'var(--warning)' : 'var(--primary)');
        bar.style.height = `${Math.max(val, 4)}%`;
        bar.style.background = color;
        bar.title = `Core ${i}: ${val}%`;
      }
    });
  }

  // ── Process Table (Diff In Place) ──
  function renderProcesses(procs) {
    const tbody = document.getElementById('proc-table-body');
    if (!tbody || !procs) return;

    tbody.innerHTML = procs.slice(0, 8).map(p => `
      <tr style="transition: background-color 0.3s ease;">
        <td class="truncate" style="max-width:180px; color: var(--text-primary); font-weight: 500;">${escapeHtml(p.name || 'Unknown')}</td>
        <td class="font-mono" style="color: ${(p.cpu || 0) > 30 ? 'var(--warning)' : 'inherit'};">${(p.cpu || 0).toFixed(1)}%</td>
        <td class="font-mono">${p.mem_mb ? `${p.mem_mb} MB` : `${(p.memory || 0).toFixed(1)}%`}</td>
      </tr>
    `).join('');
  }

  // ── Storage Partitions ──
  function renderStorage(disks) {
    const container = document.getElementById('storage-list');
    if (!container || !disks) return;

    container.innerHTML = disks.map(d => `
      <div style="margin-bottom: var(--sp-3);">
        <div style="display: flex; justify-content: space-between; margin-bottom: 4px;">
          <span class="text-sm fw-medium">${escapeHtml(d.device || d.mountpoint)}</span>
          <span class="text-xs text-muted">${d.free_gb !== undefined ? `${d.free_gb} GB free` : `${d.percent}% used`}</span>
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
    if (h > 0) return `${h}h ${m}m ${s}s`;
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
