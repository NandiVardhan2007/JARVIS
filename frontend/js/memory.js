/**
 * VISION AI — Memory Explorer & Neural Knowledge Graph Module
 * Interactive Force-Directed Knowledge Graph with Physics, Drag & Drop, Zoom/Pan & Memory Filtering
 */

const VisionMemory = (() => {
  let searchInput = null;
  let allMemories = [];
  let allEvents = [];
  let cagStats = {};

  // ── Knowledge Graph State ──
  let graphCanvas = null;
  let graphCtx = null;
  let graphAnimId = null;
  let graphNodes = [];
  let graphEdges = [];
  let graphPulses = [];
  let graphCamera = { x: 0, y: 0, zoom: 1.0 };
  let draggedNode = null;
  let hoveredNode = null;
  let selectedCategory = null;
  let isPanning = false;
  let panStart = { x: 0, y: 0 };
  let isPhysicsLive = true;
  let graphSearchTerm = '';

  const CAT_CONFIG = {
    PROFILE:          { color: '#818cf8', glow: 'rgba(129, 140, 248, 0.55)', icon: '👤' },
    CONTACT:          { color: '#38bdf8', glow: 'rgba(56, 189, 248, 0.55)',  icon: '📞' },
    FAMILY:           { color: '#ec4899', glow: 'rgba(236, 72, 153, 0.55)',  icon: '👨‍👩‍👧' },
    FAMILY_PROFILE:   { color: '#f43f5e', glow: 'rgba(244, 63, 94, 0.55)',   icon: '👪' },
    FRIENDS_PROFILE:  { color: '#a855f7', glow: 'rgba(168, 85, 247, 0.55)',  icon: '🤝' },
    NICKNAMES:        { color: '#f59e0b', glow: 'rgba(245, 158, 11, 0.55)',  icon: '🏷️' },
    HARDWARE:         { color: '#10b981', glow: 'rgba(16, 185, 129, 0.55)',  icon: '🖨️' },
    SERVERS:          { color: '#06b6d4', glow: 'rgba(6, 182, 212, 0.55)',   icon: '🖥️' },
    WORKSPACE:        { color: '#3b82f6', glow: 'rgba(59, 130, 246, 0.55)',  icon: '📁' },
    ACADEMIC:         { color: '#eab308', glow: 'rgba(234, 179, 8, 0.55)',   icon: '🎓' },
    SCHEDULE:         { color: '#14b8a6', glow: 'rgba(20, 184, 166, 0.55)',  icon: '📅' },
    AUTO_LEARNED:     { color: '#6366f1', glow: 'rgba(99, 102, 241, 0.55)',  icon: '🤖' },
    USER_PREFERENCE:  { color: '#f43f5e', glow: 'rgba(244, 63, 94, 0.55)',   icon: '❤️' },
    GENERAL:          { color: '#a1a1aa', glow: 'rgba(161, 161, 170, 0.55)', icon: '📝' }
  };

  function init() {
    searchInput = document.getElementById('memory-search');
    if (searchInput) {
      searchInput.addEventListener('input', debounce(filterMemories, 200));
    }

    const addBtn = document.getElementById('memory-add-btn');
    if (addBtn) addBtn.addEventListener('click', showAddMemoryForm);

    setupGraphEvents();
  }

  function refresh() {
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
      initKnowledgeGraph(allMemories);
      renderWorkingMemory(data.working_memory || {});
    } catch (err) {
      console.error('[Memory] Fetch failed:', err);
    }
  }

  function filterMemories() {
    const query = (searchInput ? searchInput.value : '').toLowerCase().trim();
    let filtered = allMemories;

    if (selectedCategory) {
      filtered = filtered.filter(m => (m.category || 'general').toUpperCase() === selectedCategory);
    }

    if (query) {
      filtered = filtered.filter(m =>
        m.content.toLowerCase().includes(query) ||
        (m.category || '').toLowerCase().includes(query) ||
        (m.tags || '').toLowerCase().includes(query)
      );
    }
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
          <div class="empty-state-text">
            ${selectedCategory ? `No memories in category "${selectedCategory}". <button class="btn btn-link btn-xs" id="clear-cat-filter" style="color:var(--primary);cursor:pointer;">Clear filter</button>` : 'VISION memory is empty or search didn\'t match.'}
          </div>
        </div>
      `;
      const clearBtn = document.getElementById('clear-cat-filter');
      if (clearBtn) {
        clearBtn.addEventListener('click', () => {
          selectedCategory = null;
          filterMemories();
        });
      }
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
    if (selectedCategory) {
      html += `
        <div style="display:flex; align-items:center; justify-content:space-between; margin-bottom:var(--sp-3); padding:var(--sp-2) var(--sp-3); background:var(--primary-dim); border-radius:var(--radius-md); border:1px solid rgba(99,102,241,0.2);">
          <span style="font-size:var(--fs-xs); font-weight:var(--fw-semibold); color:var(--primary);">Filtered by: ${selectedCategory}</span>
          <button class="btn btn-ghost btn-xs" id="clear-cat-btn" style="padding:2px 8px; font-size:var(--fs-2xs);">Show All</button>
        </div>
      `;
    }

    Object.entries(grouped).forEach(([cat, items]) => {
      const cfg = CAT_CONFIG[cat] || CAT_CONFIG.GENERAL;
      html += `<div class="memory-group">
        <div class="memory-group-header">
          <span>${cfg.icon} ${cat}</span>
          <span class="badge badge-primary">${items.length}</span>
        </div>`;

      items.forEach(m => {
        html += `
          <div class="memory-item" data-id="${m.id}">
            <div class="memory-content">${escapeHtml(m.content)}</div>
            <div class="memory-meta">
              ${m.tags ? `<span class="memory-tags">${m.tags.split(',').map(t => `<span class="tag">${escapeHtml(t.trim())}</span>`).join('')}</span>` : ''}
              <button class="btn-icon memory-delete" data-query="${escapeHtml(m.content.substring(0, 40))}" title="Forget this memory" style="width:24px;height:24px;">
                <i data-lucide="x" class="icon-xs"></i>
              </button>
            </div>
          </div>
        `;
      });

      html += '</div>';
    });

    container.innerHTML = html;
    refreshIcons();

    const clearCatBtn = document.getElementById('clear-cat-btn');
    if (clearCatBtn) {
      clearCatBtn.addEventListener('click', () => {
        selectedCategory = null;
        filterMemories();
      });
    }

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
          if (typeof VisionApp !== 'undefined') VisionApp.showToast('Memory forgotten', 'success');
          fetchMemoryData();
        } catch (err) {
          if (typeof VisionApp !== 'undefined') VisionApp.showToast('Failed to forget', 'error');
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
    circle.style.stroke = 'var(--primary)';
  }

  // ═══════════════════════════════════════════════════════════════
  // NEURAL FORCE-DIRECTED KNOWLEDGE GRAPH ENGINE
  // ═══════════════════════════════════════════════════════════════

  function initKnowledgeGraph(memories) {
    graphCanvas = document.getElementById('knowledge-graph-canvas');
    if (!graphCanvas) return;

    graphCtx = graphCanvas.getContext('2d');
    resizeGraphCanvas();

    // Build categories & sub-nodes
    const categories = {};
    memories.forEach(m => {
      const cat = (m.category || 'general').toUpperCase();
      if (!categories[cat]) categories[cat] = { count: 0, items: [] };
      categories[cat].count++;
      categories[cat].items.push(m.content);
    });

    const catKeys = Object.keys(categories);
    const nodeCountEl = document.getElementById('graph-node-count');
    if (nodeCountEl) nodeCountEl.textContent = `${catKeys.length + 1} Nodes · ${memories.length} Facts`;

    const w = graphCanvas.width / (window.devicePixelRatio || 1);
    const h = graphCanvas.height / (window.devicePixelRatio || 1);

    graphNodes = [];
    graphEdges = [];
    graphPulses = [];

    // Central Nucleus Node (User Identity)
    const centerNode = {
      id: 'center',
      label: 'NANDU',
      sublabel: 'IDENTITY CORE',
      type: 'nucleus',
      color: '#6366f1',
      glow: 'rgba(99, 102, 241, 0.7)',
      radius: 28,
      x: w / 2,
      y: h / 2,
      vx: 0,
      vy: 0,
      isCenter: true,
      items: [`Active Core: Kovvuri Nandi Vardhan Reddy`, `Total Memories: ${memories.length}`]
    };
    graphNodes.push(centerNode);

    // Create Category Nodes with Radial Force Offsets
    catKeys.forEach((cat, idx) => {
      const cfg = CAT_CONFIG[cat] || CAT_CONFIG.GENERAL;
      const count = categories[cat].count;
      const angle = (idx / catKeys.length) * Math.PI * 2 + (Math.random() - 0.5) * 0.2;
      const dist = 130 + Math.random() * 50;

      const nodeRadius = Math.min(14 + Math.sqrt(count) * 4.5, 26);

      const catNode = {
        id: `cat_${cat}`,
        label: cat,
        sublabel: `${count} Facts`,
        category: cat,
        type: 'category',
        icon: cfg.icon,
        color: cfg.color,
        glow: cfg.glow,
        radius: nodeRadius,
        x: (w / 2) + Math.cos(angle) * dist,
        y: (h / 2) + Math.sin(angle) * dist,
        vx: (Math.random() - 0.5) * 0.5,
        vy: (Math.random() - 0.5) * 0.5,
        count: count,
        items: categories[cat].items
      };
      graphNodes.push(catNode);

      // Primary Edge: Center <-> Category
      graphEdges.push({
        source: centerNode,
        target: catNode,
        length: 140 + Math.min(count * 3, 40),
        strength: 0.045
      });
    });

    // Create 12 Animated Neural Impulse Pulses
    for (let i = 0; i < 12; i++) {
      if (graphEdges.length > 0) {
        graphPulses.push({
          edgeIdx: Math.floor(Math.random() * graphEdges.length),
          progress: Math.random(),
          speed: 0.006 + Math.random() * 0.008,
          size: 2.2 + Math.random() * 1.5
        });
      }
    }

    if (!graphAnimId) {
      animateKnowledgeGraph();
    }
  }

  function resizeGraphCanvas() {
    if (!graphCanvas) return;
    const parent = graphCanvas.parentElement;
    if (!parent) return;

    const dpr = window.devicePixelRatio || 1;
    const rect = parent.getBoundingClientRect();
    const w = rect.width || 600;
    const h = rect.height || 440;

    graphCanvas.width = w * dpr;
    graphCanvas.height = h * dpr;
    graphCanvas.style.width = w + 'px';
    graphCanvas.style.height = h + 'px';
    if (graphCtx) graphCtx.scale(dpr, dpr);
  }

  function setupGraphEvents() {
    const canvas = document.getElementById('knowledge-graph-canvas');
    if (!canvas) return;

    const tooltip = document.getElementById('graph-node-tooltip');
    const resetBtn = document.getElementById('graph-reset-btn');
    const physicsBtn = document.getElementById('graph-physics-btn');
    const searchField = document.getElementById('graph-search');

    if (searchField) {
      searchField.addEventListener('input', (e) => {
        graphSearchTerm = e.target.value.toLowerCase().trim();
      });
    }

    if (resetBtn) {
      resetBtn.addEventListener('click', () => {
        graphCamera = { x: 0, y: 0, zoom: 1.0 };
        const w = canvas.clientWidth;
        const h = canvas.clientHeight;
        if (graphNodes[0] && graphNodes[0].isCenter) {
          graphNodes[0].x = w / 2;
          graphNodes[0].y = h / 2;
          graphNodes[0].vx = 0;
          graphNodes[0].vy = 0;
        }
      });
    }

    if (physicsBtn) {
      physicsBtn.addEventListener('click', () => {
        isPhysicsLive = !isPhysicsLive;
        const label = document.getElementById('graph-physics-label');
        if (label) label.textContent = isPhysicsLive ? 'Live' : 'Frozen';
        physicsBtn.classList.toggle('active-hud', isPhysicsLive);
      });
    }

    window.addEventListener('resize', () => {
      resizeGraphCanvas();
    });

    // ── Mouse & Touch Handlers ──
    function getCanvasCoords(e) {
      const rect = canvas.getBoundingClientRect();
      const clientX = e.touches ? e.touches[0].clientX : e.clientX;
      const clientY = e.touches ? e.touches[0].clientY : e.clientY;
      const screenX = clientX - rect.left;
      const screenY = clientY - rect.top;

      // Transform via Camera
      const worldX = (screenX - graphCamera.x - (canvas.clientWidth / 2)) / graphCamera.zoom + (canvas.clientWidth / 2);
      const worldY = (screenY - graphCamera.y - (canvas.clientHeight / 2)) / graphCamera.zoom + (canvas.clientHeight / 2);

      return { screenX, screenY, worldX, worldY };
    }

    function findNodeAt(worldX, worldY) {
      for (let i = graphNodes.length - 1; i >= 0; i--) {
        const n = graphNodes[i];
        const dx = worldX - n.x;
        const dy = worldY - n.y;
        if (Math.sqrt(dx * dx + dy * dy) <= n.radius + 6) {
          return n;
        }
      }
      return null;
    }

    let dragDistance = 0;
    let startScreenPos = { x: 0, y: 0 };

    canvas.addEventListener('mousedown', (e) => {
      e.preventDefault();
      const coords = getCanvasCoords(e);
      const hit = findNodeAt(coords.worldX, coords.worldY);
      startScreenPos = { x: coords.screenX, y: coords.screenY };
      dragDistance = 0;

      if (hit) {
        draggedNode = hit;
        canvas.style.cursor = 'grabbing';
      } else {
        isPanning = true;
        panStart = { x: coords.screenX - graphCamera.x, y: coords.screenY - graphCamera.y };
        canvas.style.cursor = 'move';
      }
    });

    canvas.addEventListener('mousemove', (e) => {
      const coords = getCanvasCoords(e);
      const dx = coords.screenX - startScreenPos.x;
      const dy = coords.screenY - startScreenPos.y;
      dragDistance = Math.sqrt(dx * dx + dy * dy);

      if (draggedNode) {
        draggedNode.x = coords.worldX;
        draggedNode.y = coords.worldY;
        draggedNode.vx = 0;
        draggedNode.vy = 0;
        hideTooltip();
        return;
      }

      if (isPanning) {
        graphCamera.x = coords.screenX - panStart.x;
        graphCamera.y = coords.screenY - panStart.y;
        return;
      }

      const hit = findNodeAt(coords.worldX, coords.worldY);
      hoveredNode = hit;
      canvas.style.cursor = hit ? 'pointer' : 'grab';

      if (hit) {
        showTooltip(hit, coords.screenX, coords.screenY);
      } else {
        hideTooltip();
      }
    });

    window.addEventListener('mouseup', () => {
      if (draggedNode) {
        draggedNode = null;
        canvas.style.cursor = 'grab';
      }
      if (isPanning) {
        isPanning = false;
        canvas.style.cursor = 'grab';
      }
    });

    canvas.addEventListener('click', (e) => {
      if (dragDistance > 6) return; // User was dragging the graph/node, not clicking
      const coords = getCanvasCoords(e);
      const hit = findNodeAt(coords.worldX, coords.worldY);
      if (hit && hit.category) {
        selectedCategory = (selectedCategory === hit.category) ? null : hit.category;
        filterMemories();
      }
    });

    canvas.addEventListener('wheel', (e) => {
      e.preventDefault();
      const zoomFactor = e.deltaY < 0 ? 1.08 : 0.92;
      graphCamera.zoom = Math.max(0.55, Math.min(2.4, graphCamera.zoom * zoomFactor));
    }, { passive: false });

    function showTooltip(node, screenX, screenY) {
      if (!tooltip) return;
      const titleEl = document.getElementById('graph-tooltip-title');
      const countEl = document.getElementById('graph-tooltip-count');
      const bodyEl = document.getElementById('graph-tooltip-body');
      const dotEl = document.getElementById('graph-tooltip-dot');

      if (titleEl) titleEl.textContent = node.label;
      if (countEl) countEl.textContent = node.count !== undefined ? `${node.count} Facts` : 'Core';
      if (dotEl) {
        dotEl.style.background = node.color;
        dotEl.style.boxShadow = `0 0 8px ${node.color}`;
      }

      if (bodyEl) {
        const preview = node.items && node.items.length > 0 ?
          node.items.slice(0, 2).map(item => `• ${escapeHtml(item.substring(0, 55))}${item.length > 55 ? '...' : ''}`).join('<br>') :
          'Click to filter memories';
        bodyEl.innerHTML = preview;
      }

      tooltip.style.left = `${screenX}px`;
      tooltip.style.top = `${screenY}px`;
      tooltip.classList.add('visible');
    }

    function hideTooltip() {
      if (tooltip) tooltip.classList.remove('visible');
    }
  }

  function animateKnowledgeGraph() {
    graphAnimId = requestAnimationFrame(animateKnowledgeGraph);
    if (!graphCanvas || !graphCtx) return;

    // Performance gating: only render when Memory page is visible & active
    const memPage = document.getElementById('page-memory');
    if (!memPage || !memPage.classList.contains('active') || document.hidden) return;

    const w = graphCanvas.clientWidth;
    const h = graphCanvas.clientHeight;
    if (w === 0 || h === 0) return;

    // ── 1. Physics Step ──
    if (isPhysicsLive) {
      const centerX = w / 2;
      const centerY = h / 2;

      // Center Gravitational Well
      graphNodes.forEach(node => {
        if (node === draggedNode) return;
        const targetX = node.isCenter ? centerX : centerX;
        const targetY = node.isCenter ? centerY : centerY;
        const gravityStrength = node.isCenter ? 0.08 : 0.0025;

        node.vx += (targetX - node.x) * gravityStrength;
        node.vy += (targetY - node.y) * gravityStrength;
      });

      // Coulomb Node-Node Repulsion
      for (let i = 0; i < graphNodes.length; i++) {
        for (let j = i + 1; j < graphNodes.length; j++) {
          const n1 = graphNodes[i];
          const n2 = graphNodes[j];
          const dx = n2.x - n1.x;
          const dy = n2.y - n1.y;
          const distSq = dx * dx + dy * dy + 1;
          const dist = Math.sqrt(distSq);

          const minSafeDist = n1.radius + n2.radius + 30;
          const repulsion = (dist < minSafeDist) ? 1400 : 700;
          const force = repulsion / distSq;

          const fx = (dx / dist) * force;
          const fy = (dy / dist) * force;

          if (n1 !== draggedNode) { n1.vx -= fx; n1.vy -= fy; }
          if (n2 !== draggedNode) { n2.vx += fx; n2.vy += fy; }
        }
      }

      // Hooke's Law Spring Edges
      graphEdges.forEach(edge => {
        const src = edge.source;
        const tgt = edge.target;
        const dx = tgt.x - src.x;
        const dy = tgt.y - src.y;
        const dist = Math.sqrt(dx * dx + dy * dy) + 0.1;
        const displacement = dist - edge.length;
        const force = displacement * edge.strength;

        const fx = (dx / dist) * force;
        const fy = (dy / dist) * force;

        if (src !== draggedNode) { src.vx += fx; src.vy += fy; }
        if (tgt !== draggedNode) { tgt.vx -= fx; tgt.vy -= fy; }
      });

      // Velocity Integration & Air Damping
      graphNodes.forEach(node => {
        if (node === draggedNode) return;
        node.vx *= 0.88;
        node.vy *= 0.88;
        node.x += node.vx;
        node.y += node.vy;

        // Boundary Soft Containment
        const pad = node.radius + 15;
        if (node.x < pad) { node.x = pad; node.vx *= -0.5; }
        if (node.x > w - pad) { node.x = w - pad; node.vx *= -0.5; }
        if (node.y < pad) { node.y = pad; node.vy *= -0.5; }
        if (node.y > h - pad) { node.y = h - pad; node.vy *= -0.5; }
      });
    }

    // ── 2. Render Step ──
    const dpr = window.devicePixelRatio || 1;
    graphCtx.save();
    graphCtx.setTransform(1, 0, 0, 1, 0, 0);
    graphCtx.clearRect(0, 0, graphCanvas.width, graphCanvas.height);
    graphCtx.restore();

    graphCtx.save();
    // Camera Transform (Centered Zoom & Pan)
    graphCtx.translate(w / 2 + graphCamera.x, h / 2 + graphCamera.y);
    graphCtx.scale(graphCamera.zoom, graphCamera.zoom);
    graphCtx.translate(-w / 2, -h / 2);

    // Cybernetic Grid Background
    drawGraphGrid(graphCtx, w, h);

    // Draw Edges
    graphEdges.forEach((edge, idx) => {
      const isHighlighted = (hoveredNode && (hoveredNode === edge.source || hoveredNode === edge.target)) ||
                            (selectedCategory && edge.target.category === selectedCategory);

      graphCtx.beginPath();
      graphCtx.moveTo(edge.source.x, edge.source.y);
      graphCtx.lineTo(edge.target.x, edge.target.y);

      if (isHighlighted) {
        graphCtx.strokeStyle = edge.target.color || '#6366f1';
        graphCtx.lineWidth = 2.0;
        graphCtx.shadowColor = edge.target.glow || 'rgba(99,102,241,0.5)';
        graphCtx.shadowBlur = 8;
      } else {
        graphCtx.strokeStyle = 'rgba(255, 255, 255, 0.07)';
        graphCtx.lineWidth = 1.0;
        graphCtx.shadowBlur = 0;
      }
      graphCtx.stroke();
    });

    // Draw Animated Neural Pulses
    graphPulses.forEach(pulse => {
      const edge = graphEdges[pulse.edgeIdx];
      if (!edge) return;

      pulse.progress += pulse.speed;
      if (pulse.progress > 1) {
        pulse.progress = 0;
        pulse.edgeIdx = Math.floor(Math.random() * graphEdges.length);
      }

      const px = edge.source.x + (edge.target.x - edge.source.x) * pulse.progress;
      const py = edge.source.y + (edge.target.y - edge.source.y) * pulse.progress;

      graphCtx.beginPath();
      graphCtx.arc(px, py, pulse.size, 0, Math.PI * 2);
      graphCtx.fillStyle = edge.target.color || '#22d3ee';
      graphCtx.shadowColor = edge.target.color || '#22d3ee';
      graphCtx.shadowBlur = 6;
      graphCtx.fill();
    });

    // Draw Nodes
    const time = Date.now() * 0.002;

    graphNodes.forEach(node => {
      const isHovered = (hoveredNode === node);
      const isSelected = (selectedCategory && node.category === selectedCategory);
      const isSearchMatch = (graphSearchTerm && node.label.toLowerCase().includes(graphSearchTerm));

      graphCtx.save();

      // Node Halo / Glow Aura
      const glowRadius = node.radius + (isHovered || isSelected || isSearchMatch ? 12 : 5);
      const grad = graphCtx.createRadialGradient(node.x, node.y, node.radius * 0.3, node.x, node.y, glowRadius);
      grad.addColorStop(0, node.glow || 'rgba(99,102,241,0.3)');
      grad.addColorStop(1, 'rgba(0, 0, 0, 0)');

      graphCtx.beginPath();
      graphCtx.arc(node.x, node.y, glowRadius, 0, Math.PI * 2);
      graphCtx.fillStyle = grad;
      graphCtx.fill();

      // Central Nucleus Rotating Orbital Ring
      if (node.isCenter) {
        graphCtx.save();
        graphCtx.translate(node.x, node.y);
        graphCtx.rotate(time * 0.8);
        graphCtx.beginPath();
        graphCtx.setLineDash([5, 5]);
        graphCtx.arc(0, 0, node.radius + 6, 0, Math.PI * 2);
        graphCtx.strokeStyle = 'rgba(99, 102, 241, 0.6)';
        graphCtx.lineWidth = 1.5;
        graphCtx.stroke();
        graphCtx.restore();
      }

      // Search Highlight Ring
      if (isSearchMatch) {
        graphCtx.beginPath();
        graphCtx.arc(node.x, node.y, node.radius + 8 + Math.sin(time * 4) * 3, 0, Math.PI * 2);
        graphCtx.strokeStyle = '#f59e0b';
        graphCtx.lineWidth = 2.5;
        graphCtx.shadowColor = '#f59e0b';
        graphCtx.shadowBlur = 10;
        graphCtx.stroke();
      }

      // Node Core Body
      graphCtx.beginPath();
      graphCtx.arc(node.x, node.y, node.radius, 0, Math.PI * 2);
      graphCtx.fillStyle = isHovered || isSelected ? node.color : 'rgba(15, 23, 42, 0.92)';
      graphCtx.fill();
      graphCtx.strokeStyle = node.color;
      graphCtx.lineWidth = isHovered || isSelected ? 2.5 : 1.8;
      graphCtx.shadowColor = node.color;
      graphCtx.shadowBlur = isHovered || isSelected ? 12 : 4;
      graphCtx.stroke();

      // Node Icon / Inner Count
      graphCtx.fillStyle = isHovered || isSelected ? '#090d16' : '#ffffff';
      graphCtx.font = node.isCenter ? 'bold 11px Inter, sans-serif' : 'bold 10px Inter, sans-serif';
      graphCtx.textAlign = 'center';
      graphCtx.textBaseline = 'middle';

      if (node.isCenter) {
        graphCtx.fillText('NANDU', node.x, node.y);
      } else {
        graphCtx.fillText(node.count !== undefined ? String(node.count) : '1', node.x, node.y);
      }

      // Node Badge Pill Label (with dark glass backing to eliminate text overlap!)
      const labelText = node.label;
      graphCtx.font = '500 10px Inter, sans-serif';
      const textMetrics = graphCtx.measureText(labelText);
      const pillW = textMetrics.width + 12;
      const pillH = 16;
      const pillX = node.x - pillW / 2;
      const pillY = node.y + node.radius + 6;

      graphCtx.beginPath();
      graphCtx.roundRect(pillX, pillY, pillW, pillH, 8);
      graphCtx.fillStyle = isHovered || isSelected ? 'rgba(99, 102, 241, 0.95)' : 'rgba(13, 17, 28, 0.88)';
      graphCtx.fill();
      graphCtx.strokeStyle = isHovered || isSelected ? '#a5b4fc' : 'rgba(255, 255, 255, 0.12)';
      graphCtx.lineWidth = 1;
      graphCtx.stroke();

      graphCtx.fillStyle = isHovered || isSelected ? '#ffffff' : '#cbd5e1';
      graphCtx.textAlign = 'center';
      graphCtx.textBaseline = 'middle';
      graphCtx.fillText(labelText, node.x, pillY + pillH / 2);

      graphCtx.restore();
    });

    graphCtx.restore();
  }

  function drawGraphGrid(ctx, w, h) {
    const gridSize = 40;
    ctx.fillStyle = 'rgba(255, 255, 255, 0.025)';
    for (let x = 0; x < w; x += gridSize) {
      for (let y = 0; y < h; y += gridSize) {
        ctx.beginPath();
        ctx.arc(x, y, 1.0, 0, Math.PI * 2);
        ctx.fill();
      }
    }
  }

  // ═══════════════════════════════════════════════════════════════

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
      if (typeof VisionApp !== 'undefined') VisionApp.showToast('Memory stored! 🧠', 'success');
      fetchMemoryData();
    })
    .catch(() => {
      if (typeof VisionApp !== 'undefined') VisionApp.showToast('Failed to store memory', 'error');
    });
  }

  function formatTimeAgo(dateStr) {
    try {
      const d = new Date(dateStr);
      const now = new Date();
      const diff = Math.floor((now - d) / 1000);
      if (diff < 60) return 'Just now';
      if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
      if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
      return `${Math.floor(diff / 86400)}d ago`;
    } catch {
      return dateStr;
    }
  }

  function updateText(id, val) {
    const el = document.getElementById(id);
    if (el) el.textContent = val;
  }

  function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
  }

  function debounce(fn, delay) {
    let timer;
    return function (...args) {
      clearTimeout(timer);
      timer = setTimeout(() => fn.apply(this, args), delay);
    };
  }

  function refreshIcons() {
    if (window.lucide && lucide.createIcons) {
      lucide.createIcons();
    }
  }

  return { init, refresh };
})();
