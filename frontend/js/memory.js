/**
 * VISION AI — Memory Explorer Module
 * Browse semantic memories, episodic timeline, knowledge graph, CAG stats
 */

const VisionMemory = (() => {
  let searchInput = null;
  let allMemories = [];
  let allEvents = [];
  let cagStats = {};
  let graphRelations = [];

  function init() {
    searchInput = document.getElementById('memory-search');
    if (searchInput) {
      searchInput.addEventListener('input', debounce(filterMemories, 200));
    }

    const addBtn = document.getElementById('memory-add-btn');
    if (addBtn) addBtn.addEventListener('click', showAddMemoryForm);

    fetchMemoryData();
  }

  async function fetchMemoryData() {
    try {
      const res = await fetch('/api/memory/stats');
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();

      allMemories = data.semantic_memories || [];
      allEvents = data.episodic_events || [];
      cagStats = data.cag_cache || {};

      renderMemories(allMemories);
      renderEpisodic(allEvents);
      renderCagStats(cagStats);
      renderKnowledgeGraph();
      renderWorkingMemory(data.working_memory || {});
    } catch (err) {
      console.error('[Memory] Fetch failed:', err);
    }
  }

  function filterMemories() {
    const query = searchInput.value.toLowerCase().trim();
    if (!query) {
      renderMemories(allMemories);
      return;
    }
    const filtered = allMemories.filter(m =>
      m.content.toLowerCase().includes(query) ||
      (m.category || '').toLowerCase().includes(query) ||
      (m.tags || '').toLowerCase().includes(query)
    );
    renderMemories(filtered);
  }

  function renderMemories(memories) {
    const container = document.getElementById('memory-list');
    if (!container) return;

    if (!memories.length) {
      container.innerHTML = `
        <div class="empty-state" style="padding: var(--sp-8);">
          <div class="empty-state-icon">🧠</div>
          <div class="empty-state-title">No memories found</div>
          <div class="empty-state-text">VISION's memory is empty or your search didn't match any entries.</div>
        </div>
      `;
      return;
    }

    // Group by category
    const grouped = {};
    memories.forEach(m => {
      const cat = (m.category || 'general').toUpperCase();
      if (!grouped[cat]) grouped[cat] = [];
      grouped[cat].push(m);
    });

    let html = '';
    const catIcons = {
      PROFILE: '👤', HARDWARE: '🖨️', PREFERENCE: '⚙️', WORKSPACE: '📁',
      CONTACT: '📞', FAMILY: '👨‍👩‍👧', FAMILY_PROFILE: '👪', FRIENDS_PROFILE: '🤝',
      AUTO_LEARNED: '🤖', USER_PREFERENCE: '❤️', GENERAL: '📝', NICKNAMES: '🏷️',
      ACADEMIC: '🎓', SCHEDULE: '📅'
    };

    Object.entries(grouped).forEach(([cat, items]) => {
      const icon = catIcons[cat] || '📌';
      html += `<div class="memory-group">
        <div class="memory-group-header">
          <span>${icon} ${cat}</span>
          <span class="badge badge-info">${items.length}</span>
        </div>`;

      items.forEach(m => {
        html += `
          <div class="memory-item" data-id="${m.id}">
            <div class="memory-content">${escapeHtml(m.content)}</div>
            <div class="memory-meta">
              ${m.tags ? `<span class="memory-tags">${m.tags.split(',').map(t => `<span class="tag">${t.trim()}</span>`).join('')}</span>` : ''}
              <button class="btn-icon memory-delete" data-query="${escapeHtml(m.content.substring(0, 40))}" title="Forget this memory" style="width:24px;height:24px;font-size:12px;">✕</button>
            </div>
          </div>
        `;
      });

      html += '</div>';
    });

    container.innerHTML = html;

    // Attach delete handlers
    container.querySelectorAll('.memory-delete').forEach(btn => {
      btn.addEventListener('click', async (e) => {
        e.stopPropagation();
        const query = btn.dataset.query;
        if (!confirm(`Delete memories matching "${query}"?`)) return;
        try {
          await fetch('/api/memory/forget', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ query })
          });
          VisionApp.showToast('Memory forgotten', 'success');
          fetchMemoryData();
        } catch (err) {
          VisionApp.showToast('Failed to forget', 'error');
        }
      });
    });
  }

  function renderEpisodic(events) {
    const container = document.getElementById('episodic-timeline');
    if (!container) return;

    if (!events.length) {
      container.innerHTML = '<div class="text-sm text-muted" style="padding: var(--sp-4);">No events recorded yet.</div>';
      return;
    }

    container.innerHTML = events.slice(0, 15).map(e => {
      const typeIcons = {
        tool_execution: '🔧', user_interaction: '💬', system: '⚡',
        reminder: '⏰', error: '❌'
      };
      const icon = typeIcons[e.event_type] || '📋';
      const time = e.created_at ? formatTimeAgo(e.created_at) : '';

      return `
        <div class="event-item">
          <span style="font-size: var(--fs-md); flex-shrink:0;">${icon}</span>
          <div style="flex:1; min-width:0;">
            <div class="text-sm" style="color: var(--text-primary);">${escapeHtml(e.description)}</div>
            <div class="text-xs text-muted">${e.event_type} · ${time}</div>
          </div>
        </div>
      `;
    }).join('');
  }

  function renderCagStats(stats) {
    updateText('cag-entries', stats.active_entries || 0);
    updateText('cag-capacity', stats.max_capacity || 500);
    updateText('cag-hits', stats.total_hits || 0);
    updateText('cag-misses', stats.misses || 0);
    updateText('cag-ratio', stats.hit_ratio || '0%');

    // Donut chart for cache utilization
    const donut = document.getElementById('cag-donut');
    if (donut && stats.active_entries !== undefined && stats.max_capacity) {
      const pct = (stats.active_entries / stats.max_capacity) * 100;
      updateDonut(donut, pct);
    }
  }

  function updateDonut(svg, percent) {
    const circle = svg.querySelector('.donut-fill');
    if (!circle) return;
    const radius = parseFloat(circle.getAttribute('r'));
    const circ = 2 * Math.PI * radius;
    circle.style.strokeDasharray = circ;
    circle.style.strokeDashoffset = circ - (percent / 100) * circ;
  }

  function renderKnowledgeGraph() {
    const canvas = document.getElementById('knowledge-graph-canvas');
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    const dpr = window.devicePixelRatio || 1;
    const rect = canvas.parentElement.getBoundingClientRect();
    canvas.width = rect.width * dpr;
    canvas.height = rect.height * dpr;
    canvas.style.width = rect.width + 'px';
    canvas.style.height = rect.height + 'px';
    ctx.scale(dpr, dpr);

    // Fetch knowledge graph relations
    fetch('/api/memory/stats').then(r => r.json()).then(data => {
      const memories = data.semantic_memories || [];
      drawMiniGraph(ctx, rect.width, rect.height, memories);
    }).catch(() => {
      drawMiniGraph(ctx, rect.width, rect.height, []);
    });
  }

  function drawMiniGraph(ctx, w, h, memories) {
    ctx.clearRect(0, 0, w, h);

    // Create nodes from memory categories
    const categories = {};
    memories.forEach(m => {
      const cat = m.category || 'general';
      if (!categories[cat]) categories[cat] = { count: 0, items: [] };
      categories[cat].count++;
      categories[cat].items.push(m.content.substring(0, 30));
    });

    const catKeys = Object.keys(categories);
    if (catKeys.length === 0) {
      ctx.fillStyle = '#555566';
      ctx.font = '13px Inter, sans-serif';
      ctx.textAlign = 'center';
      ctx.fillText('Knowledge graph will appear here', w / 2, h / 2);
      return;
    }

    const centerX = w / 2;
    const centerY = h / 2;
    const radius = Math.min(w, h) * 0.32;

    // Draw central node (VISION)
    ctx.beginPath();
    ctx.arc(centerX, centerY, 24, 0, Math.PI * 2);
    ctx.fillStyle = 'rgba(108, 99, 255, 0.2)';
    ctx.fill();
    ctx.strokeStyle = '#6c63ff';
    ctx.lineWidth = 2;
    ctx.stroke();

    ctx.fillStyle = '#e8e6f0';
    ctx.font = 'bold 11px Inter, sans-serif';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText('NANDU', centerX, centerY);

    // Draw category nodes in a circle
    const colors = ['#6c63ff', '#00d4aa', '#ff9f43', '#3b82f6', '#f472b6', '#22d3ee', '#ff6b6b', '#a78bfa'];

    catKeys.forEach((cat, i) => {
      const angle = (i / catKeys.length) * Math.PI * 2 - Math.PI / 2;
      const x = centerX + radius * Math.cos(angle);
      const y = centerY + radius * Math.sin(angle);
      const color = colors[i % colors.length];
      const nodeRadius = Math.min(8 + categories[cat].count * 2, 22);

      // Draw edge
      ctx.beginPath();
      ctx.moveTo(centerX, centerY);
      ctx.lineTo(x, y);
      ctx.strokeStyle = 'rgba(255,255,255,0.06)';
      ctx.lineWidth = 1;
      ctx.stroke();

      // Draw node
      ctx.beginPath();
      ctx.arc(x, y, nodeRadius, 0, Math.PI * 2);
      ctx.fillStyle = color + '30';
      ctx.fill();
      ctx.strokeStyle = color;
      ctx.lineWidth = 1.5;
      ctx.stroke();

      // Label
      ctx.fillStyle = '#8a8a9a';
      ctx.font = '10px Inter, sans-serif';
      ctx.textAlign = 'center';
      ctx.textBaseline = 'top';
      ctx.fillText(cat.toUpperCase(), x, y + nodeRadius + 4);

      // Count
      ctx.fillStyle = '#e8e6f0';
      ctx.font = 'bold 10px Inter, sans-serif';
      ctx.textBaseline = 'middle';
      ctx.fillText(categories[cat].count, x, y);
    });
  }

  function renderWorkingMemory(wm) {
    updateText('wm-files', wm.recent_files_count || 0);
    updateText('wm-indexed', wm.indexed_files_count || 0);
    updateText('wm-last-dir', wm.last_directory || 'None');
    updateText('wm-last-app', wm.last_opened_app || 'None');
  }

  function showAddMemoryForm() {
    const content = prompt('What should VISION remember?');
    if (!content || !content.trim()) return;

    const category = prompt('Category (e.g., preference, contact, workspace):', 'user_preference');

    fetch('/api/memory/remember', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ content: content.trim(), category: category || 'user_preference', tags: '' })
    })
    .then(r => r.json())
    .then(() => {
      VisionApp.showToast('Memory stored! 🧠', 'success');
      fetchMemoryData();
    })
    .catch(() => VisionApp.showToast('Failed to store memory', 'error'));
  }

  function formatTimeAgo(dateStr) {
    const now = new Date();
    const date = new Date(dateStr);
    const diff = Math.floor((now - date) / 1000);
    if (diff < 60) return 'just now';
    if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
    if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
    return `${Math.floor(diff / 86400)}d ago`;
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
    return (...args) => {
      clearTimeout(timer);
      timer = setTimeout(() => fn(...args), delay);
    };
  }

  return { init, fetchMemoryData };
})();
