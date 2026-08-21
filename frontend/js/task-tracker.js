/**
 * VISION AI — Task Tracker Module
 * Expandable month view, day accordions, KPI dashboard, Chart.js integration
 */

const VisionTaskTracker = (() => {
  let currentSelectedMonth = "August";
  let currentSelectedDay = (new Date()).getDate();
  let currentTaskFilter = "all";
  let currentViewMode = "expandable";
  let currentDashboardData = null;
  let taskChartInstance = null;
  const expandedDays = new Set([(new Date()).getDate()]);

  function init() {
    const modal = document.getElementById('task-tracker-modal');
    const toggleBtn = document.getElementById('task-tracker-toggle-btn');
    const closeBtn = document.getElementById('task-modal-close-btn');
    const monthSelect = document.getElementById('task-month-select');
    const openExcelBtn = document.getElementById('open-excel-btn');
    const syncExcelBtn = document.getElementById('sync-excel-btn');
    const addForm = document.getElementById('task-add-form');
    const daySelect = document.getElementById('new-task-day-select');

    // Populate Day dropdown
    if (daySelect) {
      let options = '';
      for (let d = 1; d <= 31; d++) {
        const sel = (d === currentSelectedDay) ? 'selected' : '';
        options += `<option value="${d}" ${sel}>Day ${d < 10 ? '0' + d : d}</option>`;
      }
      daySelect.innerHTML = options;
    }

    // Set initial month
    const months = ["January", "February", "March", "April", "May", "June",
                    "July", "August", "September", "October", "November", "December"];
    const now = new Date();
    currentSelectedMonth = months[now.getMonth()];
    currentSelectedDay = now.getDate();
    expandedDays.add(currentSelectedDay);
    if (monthSelect) monthSelect.value = currentSelectedMonth;

    // Open Modal
    if (toggleBtn && modal) {
      toggleBtn.addEventListener('click', () => {
        modal.classList.add('active');
        renderDaysBar();
        fetchTaskDashboard();
      });
    }

    // Close Modal
    if (closeBtn && modal) {
      closeBtn.addEventListener('click', () => modal.classList.remove('active'));
    }
    if (modal) {
      modal.addEventListener('click', (e) => {
        if (e.target === modal) modal.classList.remove('active');
      });
    }

    // Month select
    if (monthSelect) {
      monthSelect.addEventListener('change', (e) => {
        currentSelectedMonth = e.target.value;
        renderDaysBar();
        fetchTaskDashboard();
      });
    }

    // View Mode Switcher
    const btnExpandable = document.getElementById('view-mode-expandable');
    const btnSingle = document.getElementById('view-mode-single');
    const expandActions = document.getElementById('expand-collapse-actions');
    const timelineBarWrap = document.querySelector('.task-days-timeline-wrap');

    if (btnExpandable && btnSingle) {
      btnExpandable.addEventListener('click', () => {
        currentViewMode = 'expandable';
        btnExpandable.classList.add('active');
        btnSingle.classList.remove('active');
        if (expandActions) expandActions.style.display = 'flex';
        if (timelineBarWrap) timelineBarWrap.style.display = 'block';
        renderTaskItems();
      });

      btnSingle.addEventListener('click', () => {
        currentViewMode = 'single';
        btnSingle.classList.add('active');
        btnExpandable.classList.remove('active');
        if (expandActions) expandActions.style.display = 'none';
        if (timelineBarWrap) timelineBarWrap.style.display = 'block';
        renderTaskItems();
      });
    }

    // Expand/Collapse All
    const btnExpandAll = document.getElementById('btn-expand-all');
    const btnCollapseAll = document.getElementById('btn-collapse-all');
    if (btnExpandAll) {
      btnExpandAll.addEventListener('click', () => {
        for (let d = 1; d <= 31; d++) expandedDays.add(d);
        renderTaskItems();
      });
    }
    if (btnCollapseAll) {
      btnCollapseAll.addEventListener('click', () => {
        expandedDays.clear();
        renderTaskItems();
      });
    }

    // Filter tabs
    document.querySelectorAll('.task-filter-pill[data-filter]').forEach(btn => {
      btn.addEventListener('click', () => {
        document.querySelectorAll('.task-filter-pill[data-filter]').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        currentTaskFilter = btn.getAttribute('data-filter');
        renderTaskItems();
      });
    });

    // Add Task Form
    if (addForm) {
      addForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const titleInput = document.getElementById('new-task-title');
        const dayInput = document.getElementById('new-task-day-select');
        const catSelect = document.getElementById('new-task-category');
        const prioSelect = document.getElementById('new-task-priority');
        const title = titleInput.value.trim();
        if (!title) return;

        const chosenDay = dayInput ? parseInt(dayInput.value) : currentSelectedDay;

        try {
          await fetch('/api/tasks', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              title, day: chosenDay, month: currentSelectedMonth,
              category: catSelect.value, priority: prioSelect.value
            })
          });
          titleInput.value = '';
          expandedDays.add(chosenDay);
          fetchTaskDashboard();
        } catch (err) {
          console.error('[Tasks] Add task error:', err);
        }
      });
    }

    // Open in Excel
    if (openExcelBtn) {
      openExcelBtn.addEventListener('click', async () => {
        try {
          openExcelBtn.disabled = true;
          const originalHTML = openExcelBtn.innerHTML;
          openExcelBtn.innerHTML = `<span>LAUNCHING...</span>`;
          await fetch('/api/tasks/excel/open', { method: 'POST' });
          setTimeout(() => {
            openExcelBtn.disabled = false;
            openExcelBtn.innerHTML = originalHTML;
            refreshIcons();
          }, 1200);
        } catch (err) {
          openExcelBtn.disabled = false;
        }
      });
    }

    // Sync Excel
    if (syncExcelBtn) {
      syncExcelBtn.addEventListener('click', async () => {
        try {
          syncExcelBtn.disabled = true;
          const originalHTML = syncExcelBtn.innerHTML;
          syncExcelBtn.innerHTML = `<span>SYNCING...</span>`;
          await fetch('/api/tasks/excel/sync', { method: 'POST' });
          setTimeout(() => {
            syncExcelBtn.disabled = false;
            syncExcelBtn.innerHTML = originalHTML;
            refreshIcons();
          }, 800);
        } catch (err) {
          syncExcelBtn.disabled = false;
        }
      });
    }

    // Quick LeetCode Solve
    const btnQuickSolveLC = document.getElementById('btn-quick-solve-leetcode');
    if (btnQuickSolveLC) {
      btnQuickSolveLC.addEventListener('click', async () => {
        try {
          const daysMap = currentDashboardData?.month_metrics?.days_breakdown || {};
          const todayDayTasks = daysMap[currentSelectedDay]?.tasks || [];
          const lcTask = todayDayTasks.find(t => (t.title || '').toLowerCase().includes('leetcode'));

          if (lcTask) {
            await toggleTask(lcTask.id, lcTask.is_completed === 1);
          } else {
            const res = await fetch('/api/tasks', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({
                title: 'Daily LeetCode Problem Solving (LeetCode / CodeChef / GFG)',
                day: currentSelectedDay, month: currentSelectedMonth,
                category: 'Coding', priority: 'High'
              })
            });
            const newTask = await res.json();
            if (newTask && newTask.id) {
              await toggleTask(newTask.id, false);
            } else {
              fetchTaskDashboard();
            }
          }
        } catch (err) {
          console.error('[LeetCode] Quick solve error:', err);
        }
      });
    }

    renderDaysBar();
  }

  function renderDaysBar() {
    const daysBar = document.getElementById('task-days-bar');
    if (!daysBar) return;

    const now = new Date();
    const todayDay = now.getDate();
    const months = ["January", "February", "March", "April", "May", "June",
                    "July", "August", "September", "October", "November", "December"];
    const isCurrentMonth = (currentSelectedMonth === months[now.getMonth()]);

    let html = '';
    for (let d = 1; d <= 31; d++) {
      const isActive = (d === currentSelectedDay) ? 'active' : '';
      const isToday = (isCurrentMonth && d === todayDay) ? 'is-today' : '';
      html += `
        <div class="day-pill ${isActive} ${isToday}" data-day="${d}">
          <span class="day-pill-num">${d < 10 ? '0' + d : d}</span>
          <span class="day-pill-sub">DAY</span>
        </div>
      `;
    }
    daysBar.innerHTML = html;

    // Attach click handlers via delegation
    daysBar.querySelectorAll('.day-pill').forEach(pill => {
      pill.addEventListener('click', () => {
        selectTaskDay(parseInt(pill.dataset.day));
      });
    });

    setTimeout(() => {
      const activePill = daysBar.querySelector('.day-pill.active');
      if (activePill) {
        activePill.scrollIntoView({ behavior: 'smooth', inline: 'center', block: 'nearest' });
      }
    }, 100);
  }

  function selectTaskDay(dayNum) {
    currentSelectedDay = dayNum;
    expandedDays.add(dayNum);

    const daySelect = document.getElementById('new-task-day-select');
    if (daySelect) daySelect.value = dayNum;

    renderDaysBar();
    fetchTaskDashboard();

    if (currentViewMode === 'expandable') {
      setTimeout(() => {
        const cardEl = document.getElementById(`day-accordion-${dayNum}`);
        if (cardEl) cardEl.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }, 150);
    }
  }

  function toggleDayAccordion(dayNum) {
    if (expandedDays.has(dayNum)) {
      expandedDays.delete(dayNum);
    } else {
      expandedDays.add(dayNum);
    }
    renderTaskItems();
  }

  async function fetchTaskDashboard() {
    try {
      const res = await fetch(`/api/tasks/dashboard?day=${currentSelectedDay}&month=${encodeURIComponent(currentSelectedMonth)}`);
      const data = await res.json();
      currentDashboardData = data;

      // Update viewing label
      const viewLbl = document.getElementById('task-current-viewing-label');
      if (viewLbl) {
        viewLbl.textContent = currentViewMode === 'expandable'
          ? `${currentSelectedMonth} ${data.year} (31 Days Breakdown)`
          : `Day ${currentSelectedDay} (${currentSelectedMonth})`;
      }

      // Update KPIs
      setText('kpi-streak', `${data.streak_days} 🔥`);
      setText('kpi-day-rate', `${data.day_metrics.completion_rate}%`);
      setText('kpi-month-rate', `${data.month_metrics.completion_rate}%`);
      setText('kpi-pending-count', `${data.month_metrics.pending}`);

      // Update LeetCode card
      if (data.leetcode_metrics) {
        const lc = data.leetcode_metrics;
        setText('leetcode-streak-badge', `${lc.streak} DAYS 🔥`);

        const lcStatus = document.getElementById('leetcode-today-status');
        const lcBtnText = document.getElementById('btn-quick-solve-text');
        const lcBtn = document.getElementById('btn-quick-solve-leetcode');

        if (lcStatus) {
          lcStatus.innerHTML = lc.today_done
            ? `<span style="color:var(--accent); font-weight:800;">✅ SOLVED (${lc.month_solved}/${lc.monthly_target} Mo)</span>`
            : `<span style="color:#FFA116; font-weight:700;">⏳ PENDING (1+ Q)</span>`;
        }

        if (lcBtnText && lcBtn) {
          if (lc.today_done) {
            lcBtnText.textContent = 'SOLVED ✨';
            lcBtn.style.background = 'rgba(16, 185, 129, 0.2)';
            lcBtn.style.color = 'var(--accent)';
            lcBtn.style.border = '1px solid rgba(16, 185, 129, 0.4)';
          } else {
            lcBtnText.textContent = 'MARK SOLVED';
            lcBtn.style.background = 'linear-gradient(135deg, #FFA116, #FF6B00)';
            lcBtn.style.color = '#000';
            lcBtn.style.border = 'none';
          }
        }
      }

      // Update Chart
      updateTaskChart(data.month_metrics.completed, data.month_metrics.pending);

      // Category Breakdown
      renderCategoryBreakdown(data.month_metrics.category_breakdown);

      // Render Tasks
      renderTaskItems();

    } catch (err) {
      console.error('[Tasks] Dashboard fetch error:', err);
    }
  }

  function updateTaskChart(completed, pending) {
    const canvas = document.getElementById('task-pie-chart');
    if (!canvas || typeof Chart === 'undefined') return;

    const total = completed + pending;
    const dataValues = total === 0 ? [1, 0] : [completed, pending];
    const bgColors = total === 0
      ? ['rgba(255, 255, 255, 0.1)', 'rgba(255, 255, 255, 0.02)']
      : ['#10b981', '#f59e0b'];

    if (taskChartInstance) {
      taskChartInstance.data.datasets[0].data = dataValues;
      taskChartInstance.data.datasets[0].backgroundColor = bgColors;
      taskChartInstance.update();
    } else {
      const ctx = canvas.getContext('2d');
      taskChartInstance = new Chart(ctx, {
        type: 'doughnut',
        data: {
          labels: ['Completed', 'Pending'],
          datasets: [{
            data: dataValues,
            backgroundColor: bgColors,
            borderColor: ['#09090b', '#09090b'],
            borderWidth: 3,
            hoverOffset: 4
          }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          cutout: '72%',
          plugins: {
            legend: {
              position: 'bottom',
              labels: {
                color: '#a1a1aa',
                font: { family: 'Inter', size: 10 },
                padding: 12
              }
            },
            tooltip: {
              callbacks: {
                label: (ctx) => ` ${ctx.label}: ${ctx.raw} task${ctx.raw === 1 ? '' : 's'}`
              }
            }
          },
          animation: { animateRotate: true, duration: 800 }
        }
      });
    }
  }

  function renderCategoryBreakdown(cats) {
    const container = document.getElementById('task-category-breakdown');
    if (!container) return;

    const entries = Object.entries(cats || {});
    if (entries.length === 0) {
      container.innerHTML = `<span class="text-2xs text-muted font-mono">No categorical tasks yet.</span>`;
      return;
    }

    let html = '';
    for (const [catName, catInfo] of entries) {
      const pct = catInfo.total > 0 ? Math.round((catInfo.completed / catInfo.total) * 100) : 0;
      html += `
        <div class="category-row">
          <div class="category-header-row">
            <span style="color:var(--text-primary);">${catName}</span>
            <span style="color:var(--hud-cyan);">${catInfo.completed}/${catInfo.total} (${pct}%)</span>
          </div>
          <div class="cat-track">
            <div class="cat-fill" style="width: ${pct}%;"></div>
          </div>
        </div>
      `;
    }
    container.innerHTML = html;
  }

  function renderTaskItems() {
    const listContainer = document.getElementById('task-items-list');
    if (!listContainer || !currentDashboardData) return;

    const now = new Date();
    const todayDay = now.getDate();
    const months = ["January", "February", "March", "April", "May", "June",
                    "July", "August", "September", "October", "November", "December"];
    const isCurrentMonth = (currentSelectedMonth === months[now.getMonth()]);

    // MODE 1: EXPANDABLE
    if (currentViewMode === 'expandable') {
      const daysMap = currentDashboardData.month_metrics.days_breakdown || {};
      let html = '';

      for (let d = 1; d <= 31; d++) {
        const dayInfo = daysMap[d] || { day: d, total: 0, completed: 0, pending: 0, completion_rate: 0, tasks: [] };
        let tasks = dayInfo.tasks || [];

        if (currentTaskFilter === 'pending') tasks = tasks.filter(t => t.is_completed === 0);
        else if (currentTaskFilter === 'completed') tasks = tasks.filter(t => t.is_completed === 1);

        const isExpanded = expandedDays.has(d);
        const isToday = (isCurrentMonth && d === todayDay);

        let statusBadge = '';
        if (dayInfo.total === 0) {
          statusBadge = `<span class="text-2xs text-muted font-mono">0 tasks</span>`;
        } else if (dayInfo.completed === dayInfo.total) {
          statusBadge = `<span class="text-2xs font-mono fw-bold" style="color:var(--accent);">${dayInfo.completed}/${dayInfo.total} Done 🌟</span>`;
        } else {
          statusBadge = `<span class="text-2xs font-mono fw-semibold" style="color:var(--warning);">${dayInfo.completed}/${dayInfo.total} (${dayInfo.completion_rate}%)</span>`;
        }

        html += `
          <div class="day-accordion-card ${isExpanded ? 'expanded' : ''} ${isToday ? 'is-today' : ''}" id="day-accordion-${d}">
            <div class="day-acc-header" data-accordion-day="${d}">
              <div class="day-acc-left">
                <div class="day-acc-badge">
                  <span class="day-acc-num">${d < 10 ? '0' + d : d}</span>
                  <span class="day-acc-sub">DAY</span>
                </div>
                <div class="day-acc-title-group">
                  <div class="day-acc-title">
                    <span>Day ${d} — ${currentSelectedMonth} ${d}</span>
                    ${isToday ? '<span class="day-today-tag">TODAY</span>' : ''}
                  </div>
                  <div class="day-acc-count-text">${statusBadge}</div>
                </div>
              </div>
              <div class="day-acc-right">
                ${dayInfo.total > 0 ? `
                  <div class="day-acc-mini-bar" title="${dayInfo.completion_rate}% completed">
                    <div class="day-acc-mini-fill" style="width: ${dayInfo.completion_rate}%;"></div>
                  </div>
                ` : ''}
                <div class="day-acc-chevron">
                  <i data-lucide="chevron-down" class="icon-sm"></i>
                </div>
              </div>
            </div>

            <div class="day-acc-body">
              <div style="display:flex; flex-direction:column; gap:8px;">
        `;

        if (tasks.length === 0) {
          html += `
            <div style="padding:12px; text-align:center; color:var(--text-muted); font-size:0.72rem; font-family:var(--font-mono);">
              No ${currentTaskFilter === 'all' ? '' : currentTaskFilter} tasks for Day ${d}.
            </div>
          `;
        } else {
          for (const t of tasks) {
            html += renderTaskCard(t);
          }
        }

        html += `
              </div>
              <form class="day-inline-add-row" data-inline-day="${d}">
                <input type="text" class="day-inline-input" data-inline-input="${d}" placeholder="+ Add task for Day ${d}..." autocomplete="off">
                <button type="submit" class="task-btn task-btn-cyan" style="padding:4px 10px; font-size:0.65rem;">
                  <i data-lucide="plus" class="icon-xs"></i> ADD
                </button>
              </form>
            </div>
          </div>
        `;
      }

      listContainer.innerHTML = html;
      attachTaskEventListeners(listContainer);
      refreshIcons();
      return;
    }

    // MODE 2: SINGLE DAY
    const dayTasks = currentDashboardData.day_metrics.tasks || [];
    let filtered = dayTasks;
    if (currentTaskFilter === 'pending') filtered = dayTasks.filter(t => t.is_completed === 0);
    else if (currentTaskFilter === 'completed') filtered = dayTasks.filter(t => t.is_completed === 1);

    if (filtered.length === 0) {
      listContainer.innerHTML = `
        <div class="task-empty-state">
          <i data-lucide="check-circle" class="icon-lg" style="margin-bottom:8px; opacity:0.4;"></i>
          <div>No ${currentTaskFilter === 'all' ? '' : currentTaskFilter} tasks for Day ${currentSelectedDay}.</div>
          <div class="text-2xs" style="margin-top:4px; opacity:0.7;">Use the form above or tell VISION.</div>
        </div>
      `;
      refreshIcons();
      return;
    }

    let html = '';
    for (const t of filtered) { html += renderTaskCard(t); }
    listContainer.innerHTML = html;
    attachTaskEventListeners(listContainer);
    refreshIcons();
  }

  function renderTaskCard(t) {
    const isDone = t.is_completed === 1;
    const prioClass = (t.priority || '').toLowerCase() === 'high' ? 'prio-high' : ((t.priority || '').toLowerCase() === 'low' ? 'prio-low' : 'prio-medium');
    return `
      <div class="task-item-card ${isDone ? 'completed' : ''}" id="task-card-${t.id}">
        <div class="task-item-left">
          <button class="task-checkbox-btn" data-toggle-id="${t.id}" data-toggle-done="${isDone}" title="${isDone ? 'Mark Pending' : 'Mark Completed'}">
            <i data-lucide="check" class="icon-xs" style="stroke-width:3;"></i>
          </button>
          <div class="task-details">
            <span class="task-title-text">${escapeHtml(t.title)}</span>
            <div class="task-meta-row">
              <span class="task-badge-cat">${escapeHtml(t.category || 'General')}</span>
              <span class="task-badge-prio ${prioClass}">${escapeHtml(t.priority || 'Medium')}</span>
            </div>
          </div>
        </div>
        <button class="task-delete-btn" data-delete-id="${t.id}" title="Delete Task">
          <i data-lucide="trash-2" class="icon-sm"></i>
        </button>
      </div>
    `;
  }

  function attachTaskEventListeners(container) {
    // Accordion headers
    container.querySelectorAll('[data-accordion-day]').forEach(el => {
      el.addEventListener('click', () => toggleDayAccordion(parseInt(el.dataset.accordionDay)));
    });

    // Toggle buttons
    container.querySelectorAll('[data-toggle-id]').forEach(btn => {
      btn.addEventListener('click', () => {
        toggleTask(parseInt(btn.dataset.toggleId), btn.dataset.toggleDone === 'true');
      });
    });

    // Delete buttons
    container.querySelectorAll('[data-delete-id]').forEach(btn => {
      btn.addEventListener('click', () => deleteTaskItem(parseInt(btn.dataset.deleteId)));
    });

    // Inline add forms
    container.querySelectorAll('[data-inline-day]').forEach(form => {
      form.addEventListener('submit', (e) => {
        e.preventDefault();
        const dayNum = parseInt(form.dataset.inlineDay);
        const input = form.querySelector(`[data-inline-input="${dayNum}"]`);
        if (input) quickAddTask(dayNum, input);
      });
    });
  }

  async function quickAddTask(dayNum, input) {
    const title = input.value.trim();
    if (!title) return;
    try {
      await fetch('/api/tasks', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          title, day: dayNum, month: currentSelectedMonth,
          category: 'General', priority: 'Medium'
        })
      });
      input.value = '';
      expandedDays.add(dayNum);
      fetchTaskDashboard();
    } catch (err) {
      console.error('[Tasks] Quick add error:', err);
    }
  }

  async function toggleTask(taskId, currentStatus) {
    try {
      await fetch(`/api/tasks/${taskId}/toggle`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ completed: !currentStatus })
      });
      fetchTaskDashboard();
    } catch (err) {
      console.error('[Tasks] Toggle error:', err);
    }
  }

  async function deleteTaskItem(taskId) {
    try {
      await fetch(`/api/tasks/${taskId}`, { method: 'DELETE' });
      fetchTaskDashboard();
    } catch (err) {
      console.error('[Tasks] Delete error:', err);
    }
  }

  // ── Helpers ──
  function setText(id, val) {
    const el = document.getElementById(id);
    if (el) el.textContent = val;
  }

  function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }

  function refreshIcons() {
    if (window.lucide && lucide.createIcons) lucide.createIcons();
  }

  return { init, fetchTaskDashboard };
})();
