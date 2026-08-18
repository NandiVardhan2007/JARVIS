/**
 * VISION AI — Main Application Controller
 * Router, theme, initialization, particles, command palette, toasts, event feed
 */

const VisionApp = (() => {
  let currentPage = 'chat';
  const eventFeed = [];

  function init() {
    // Boot sequence
    showSplash();

    // Initialize WebSocket
    VisionWS.connect();
    VisionWS.on('status', updateConnectionStatus);
    VisionWS.on('tool_event', (data) => addEvent('tool', `${data.tool} called`));

    // Navigation
    document.querySelectorAll('.nav-item[data-page]').forEach(item => {
      item.addEventListener('click', () => navigate(item.dataset.page));
    });

    // Sidebar toggle
    const toggleBtn = document.getElementById('sidebar-toggle');
    if (toggleBtn) {
      toggleBtn.addEventListener('click', () => {
        document.getElementById('sidebar').classList.toggle('collapsed');
      });
    }

    // Command palette
    setupCommandPalette();

    // Keyboard shortcuts
    document.addEventListener('keydown', handleKeyboard);

    // Start particles on splash
    initParticles();
  }

  function showSplash() {
    const splash = document.getElementById('splash-screen');
    const progressFill = document.querySelector('.splash-progress-fill');
    const statusText = document.getElementById('splash-status-text');

    const steps = [
      { pct: 15, text: 'Connecting to VISION engine...' },
      { pct: 35, text: 'Loading AI subsystems...' },
      { pct: 55, text: 'Initializing memory (MAG + CAG)...' },
      { pct: 75, text: 'Registering tool modules...' },
      { pct: 90, text: 'Establishing WebSocket...' },
      { pct: 100, text: 'VISION Online!' },
    ];

    let i = 0;
    const interval = setInterval(() => {
      if (i >= steps.length) {
        clearInterval(interval);
        setTimeout(() => {
          splash.classList.add('hidden');
          // Initialize modules after splash
          VisionChat.init();
          VisionDashboard.init();
          VisionMemory.init();
          VisionTools.init();
          navigate('chat');
        }, 600);
        return;
      }
      if (progressFill) progressFill.style.width = steps[i].pct + '%';
      if (statusText) statusText.textContent = steps[i].text;
      i++;
    }, 400);
  }

  function navigate(page) {
    // Update nav items
    document.querySelectorAll('.nav-item[data-page]').forEach(item => {
      item.classList.toggle('active', item.dataset.page === page);
    });

    // Update pages
    document.querySelectorAll('.page').forEach(p => {
      p.classList.toggle('active', p.id === `page-${page}`);
    });

    currentPage = page;

    // Re-render knowledge graph on memory page
    if (page === 'memory') {
      setTimeout(() => VisionMemory.fetchMemoryData(), 100);
    }
    // Refresh stats when navigating to dashboard
    if (page === 'dashboard') {
      VisionDashboard.fetchStats();
    }
  }

  function updateConnectionStatus(data) {
    const dot = document.getElementById('ws-status-dot');
    const text = document.getElementById('ws-status-text');
    if (dot) {
      dot.classList.toggle('offline', !data.connected);
    }
    if (text) {
      text.textContent = data.connected ? 'Connected' : 'Disconnected';
    }
  }

  // ── Command Palette ──
  function setupCommandPalette() {
    const trigger = document.getElementById('cmd-palette-trigger');
    const palette = document.getElementById('command-palette');
    const input = document.getElementById('cmd-palette-input');
    const results = document.getElementById('cmd-palette-results');

    if (trigger) {
      trigger.addEventListener('click', () => openCommandPalette());
    }

    if (palette) {
      palette.addEventListener('click', (e) => {
        if (e.target === palette) closeCommandPalette();
      });
    }

    if (input) {
      input.addEventListener('input', () => {
        renderPaletteResults(input.value.trim());
      });
      input.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') closeCommandPalette();
        if (e.key === 'Enter') {
          const selected = results.querySelector('.cmd-palette-item.selected') || results.querySelector('.cmd-palette-item');
          if (selected) selected.click();
        }
        if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
          e.preventDefault();
          navigatePaletteItems(e.key === 'ArrowDown' ? 1 : -1);
        }
      });
    }
  }

  function openCommandPalette() {
    const palette = document.getElementById('command-palette');
    const input = document.getElementById('cmd-palette-input');
    if (palette) {
      palette.classList.add('visible');
      if (input) { input.value = ''; input.focus(); }
      renderPaletteResults('');
    }
  }

  function closeCommandPalette() {
    const palette = document.getElementById('command-palette');
    if (palette) palette.classList.remove('visible');
  }

  function renderPaletteResults(query) {
    const results = document.getElementById('cmd-palette-results');
    if (!results) return;

    const commands = [
      { icon: '💬', label: 'Chat with VISION', action: () => navigate('chat') },
      { icon: '📊', label: 'System Dashboard', action: () => navigate('dashboard') },
      { icon: '🧠', label: 'Memory Explorer', action: () => navigate('memory') },
      { icon: '🔧', label: 'Tool Launcher', action: () => navigate('tools') },
      { icon: '📸', label: 'Take Screenshot', action: () => takeScreenshot() },
      { icon: '🔄', label: 'Refresh Stats', action: () => { VisionDashboard.fetchStats(); showToast('Stats refreshed', 'success'); } },
      { icon: '🧹', label: 'Clear Chat', action: () => clearChat() },
      { icon: '➕', label: 'Add Memory', action: () => { navigate('memory'); setTimeout(() => document.getElementById('memory-add-btn')?.click(), 200); } },
    ];

    const q = query.toLowerCase();
    const filtered = q ? commands.filter(c => c.label.toLowerCase().includes(q)) : commands;

    results.innerHTML = filtered.map((c, i) => `
      <div class="cmd-palette-item ${i === 0 ? 'selected' : ''}" data-index="${i}">
        <span class="cmd-palette-item-icon">${c.icon}</span>
        <span class="cmd-palette-item-label">${c.label}</span>
      </div>
    `).join('');

    results.querySelectorAll('.cmd-palette-item').forEach((el, i) => {
      el.addEventListener('click', () => {
        filtered[i].action();
        closeCommandPalette();
      });
    });
  }

  function navigatePaletteItems(dir) {
    const results = document.getElementById('cmd-palette-results');
    if (!results) return;
    const items = results.querySelectorAll('.cmd-palette-item');
    let idx = [...items].findIndex(i => i.classList.contains('selected'));
    items.forEach(i => i.classList.remove('selected'));
    idx = (idx + dir + items.length) % items.length;
    items[idx]?.classList.add('selected');
  }

  // ── Particles ──
  function initParticles() {
    const canvas = document.getElementById('particle-canvas');
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    const dpr = window.devicePixelRatio || 1;
    let particles = [];
    const PARTICLE_COUNT = 50;

    function resize() {
      canvas.width = window.innerWidth * dpr;
      canvas.height = window.innerHeight * dpr;
      canvas.style.width = window.innerWidth + 'px';
      canvas.style.height = window.innerHeight + 'px';
      ctx.scale(dpr, dpr);
    }

    function createParticle() {
      return {
        x: Math.random() * window.innerWidth,
        y: Math.random() * window.innerHeight,
        vx: (Math.random() - 0.5) * 0.3,
        vy: (Math.random() - 0.5) * 0.3,
        size: Math.random() * 2 + 0.5,
        opacity: Math.random() * 0.3 + 0.1,
      };
    }

    resize();
    window.addEventListener('resize', resize);

    for (let i = 0; i < PARTICLE_COUNT; i++) {
      particles.push(createParticle());
    }

    function draw() {
      ctx.clearRect(0, 0, window.innerWidth, window.innerHeight);

      particles.forEach(p => {
        p.x += p.vx;
        p.y += p.vy;

        if (p.x < 0 || p.x > window.innerWidth) p.vx *= -1;
        if (p.y < 0 || p.y > window.innerHeight) p.vy *= -1;

        ctx.beginPath();
        ctx.arc(p.x, p.y, p.size, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(108, 99, 255, ${p.opacity})`;
        ctx.fill();
      });

      // Draw subtle connections
      for (let i = 0; i < particles.length; i++) {
        for (let j = i + 1; j < particles.length; j++) {
          const dx = particles[i].x - particles[j].x;
          const dy = particles[i].y - particles[j].y;
          const dist = Math.sqrt(dx * dx + dy * dy);
          if (dist < 120) {
            ctx.beginPath();
            ctx.moveTo(particles[i].x, particles[i].y);
            ctx.lineTo(particles[j].x, particles[j].y);
            ctx.strokeStyle = `rgba(108, 99, 255, ${0.06 * (1 - dist / 120)})`;
            ctx.lineWidth = 0.5;
            ctx.stroke();
          }
        }
      }

      // Only animate while splash is visible
      const splash = document.getElementById('splash-screen');
      if (splash && !splash.classList.contains('hidden')) {
        requestAnimationFrame(draw);
      } else {
        // Fade out canvas
        canvas.style.transition = 'opacity 1s';
        canvas.style.opacity = '0';
        setTimeout(() => { canvas.style.display = 'none'; }, 1000);
      }
    }

    requestAnimationFrame(draw);
  }

  // ── Screenshot ──
  async function takeScreenshot() {
    try {
      const res = await fetch('/api/vision/screenshot');
      if (!res.ok) throw new Error('Failed');
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const win = window.open();
      win.document.write(`<img src="${url}" style="max-width:100%;">`);
      showToast('Screenshot captured!', 'success');
    } catch (err) {
      showToast('Screenshot failed', 'error');
    }
  }

  // ── Clear Chat ──
  function clearChat() {
    const container = document.getElementById('chat-messages');
    if (container) container.innerHTML = '';
    showToast('Chat cleared', 'info');
  }

  // ── Toast System ──
  function showToast(message, type = 'info') {
    const container = document.getElementById('toast-container');
    if (!container) return;

    const icons = { success: '✅', error: '❌', warning: '⚠️', info: 'ℹ️' };
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.innerHTML = `
      <span class="toast-icon">${icons[type] || 'ℹ️'}</span>
      <span class="toast-text">${message}</span>
      <button class="toast-close" onclick="this.parentElement.classList.add('removing'); setTimeout(() => this.parentElement.remove(), 300);">✕</button>
    `;

    container.appendChild(toast);

    setTimeout(() => {
      if (toast.parentElement) {
        toast.classList.add('removing');
        setTimeout(() => toast.remove(), 300);
      }
    }, 4000);
  }

  // ── Event Feed ──
  function addEvent(type, text) {
    const time = new Date().toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
    eventFeed.unshift({ type, text, time });
    if (eventFeed.length > 50) eventFeed.pop();
    renderEventFeed();
  }

  function renderEventFeed() {
    const container = document.getElementById('event-feed');
    if (!container) return;

    container.innerHTML = eventFeed.slice(0, 20).map(e => `
      <div class="event-item">
        <div class="event-dot ${e.type}"></div>
        <span class="event-text">${e.text}</span>
        <span class="event-time">${e.time}</span>
      </div>
    `).join('');
  }

  // ── Keyboard Shortcuts ──
  function handleKeyboard(e) {
    // Ctrl+K → Command Palette
    if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
      e.preventDefault();
      openCommandPalette();
    }
    // Escape → close palette
    if (e.key === 'Escape') {
      closeCommandPalette();
    }
  }

  return { init, navigate, showToast, addEvent, openCommandPalette };
})();

// Boot on DOM ready
document.addEventListener('DOMContentLoaded', VisionApp.init);
