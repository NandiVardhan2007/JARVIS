"""
JARVIS Dynamic Island v2 — Pro Desktop HUD
Apple Dynamic Island-inspired overlay with:
  - Pill-split animation (two separate pills for secondary alerts)
  - Live clock in idle state
  - Notification toast queue with slide-in
  - History drawer (last 10 events) on long-press
  - Glassmorphism shimmer layer
  - Live microphone level bar in listening state
  - Per-category accent glow ring on the orb
  - Keyboard shortcut: Ctrl+J to show/hide
  - Right-click full context menu
  - Smooth state badge transitions
"""

import sys, os, json, math, time, threading
from collections import deque
from PyQt5.QtWidgets import (
    QApplication, QWidget, QGraphicsDropShadowEffect,
    QMenu, QAction, QLineEdit
)
from PyQt5.QtCore import (
    Qt, QTimer, QRectF, QPointF, QPropertyAnimation,
    QEasingCurve, pyqtSignal, QThread
)
from PyQt5.QtGui import (
    QPainter, QColor, QPainterPath, QPen, QBrush,
    QFont, QRadialGradient, QLinearGradient,
    QFontDatabase, QFontMetrics, QConicalGradient,
    QKeySequence, QImage
)
from PyQt5.QtNetwork import QUdpSocket, QHostAddress

# ══════════════════════════════════════════════════════════
#  Category Styles
# ══════════════════════════════════════════════════════════
CATEGORY_STYLE = {
    'MEDIA':     {'icon': '♫',  'color': (255, 45, 85),    'label': 'Now Playing',  'glow': (255, 45, 85)},
    'FINANCE':   {'icon': '◆',  'color': (52, 199, 89),    'label': 'Finance',      'glow': (52, 199, 89)},
    'EMAIL':     {'icon': '✉',  'color': (90, 200, 250),   'label': 'Mail',         'glow': (90, 200, 250)},
    'WEB':       {'icon': '◉',  'color': (0, 122, 255),    'label': 'Web Search',   'glow': (0, 122, 255)},
    'SYSTEM':    {'icon': '⚙',  'color': (160, 160, 170),  'label': 'System',       'glow': (160, 160, 170)},
    'FILES':     {'icon': '▤',  'color': (0, 122, 255),    'label': 'Files',        'glow': (0, 122, 255)},
    'CALENDAR':  {'icon': '▦',  'color': (255, 59, 48),    'label': 'Calendar',     'glow': (255, 59, 48)},
    'AI':        {'icon': '✦',  'color': (175, 82, 222),   'label': 'AI Engine',    'glow': (175, 82, 222)},
    'AI-GEN':    {'icon': '✧',  'color': (191, 90, 242),   'label': 'AI Generate',  'glow': (191, 90, 242)},
    'MESSAGING': {'icon': '◈',  'color': (50, 215, 75),    'label': 'Message',      'glow': (50, 215, 75)},
    'CODE':      {'icon': '❮❯', 'color': (94, 92, 230),    'label': 'Code',         'glow': (94, 92, 230)},
    'RESEARCH':  {'icon': '◇',  'color': (255, 214, 10),   'label': 'Research',     'glow': (255, 214, 10)},
    'MEMORY':    {'icon': '◐',  'color': (100, 210, 255),  'label': 'Memory',       'glow': (100, 210, 255)},
    'TASKS':     {'icon': '☑',  'color': (48, 209, 88),    'label': 'Tasks',        'glow': (48, 209, 88)},
    'TERMINAL':  {'icon': '❯_', 'color': (142, 142, 147),  'label': 'Terminal',     'glow': (142, 142, 147)},
    'GITHUB':    {'icon': '⊛',  'color': (200, 200, 200),  'label': 'GitHub',       'glow': (200, 200, 200)},
    'SCRAPER':   {'icon': '⊞',  'color': (100, 210, 255),  'label': 'Web Scraper',  'glow': (100, 210, 255)},
    'INPUT':     {'icon': '⌨',  'color': (172, 142, 104),  'label': 'Input',        'glow': (172, 142, 104)},
    'VISION':    {'icon': '◉',  'color': (0, 212, 255),    'label': 'Vision',       'glow': (0, 212, 255)},
    'IOT':       {'icon': '◈',  'color': (255, 159, 10),   'label': 'Smart Home',   'glow': (255, 159, 10)},
    'MULTI':     {'icon': '⊞',  'color': (175, 82, 222),   'label': 'Multi-Task',   'glow': (175, 82, 222)},
    'CONTACTS':  {'icon': '◎',  'color': (90, 200, 250),   'label': 'Contacts',     'glow': (90, 200, 250)},
    'DESKTOP':   {'icon': '▣',  'color': (142, 142, 147),  'label': 'Desktop',      'glow': (142, 142, 147)},
    'TOOL':      {'icon': '⚡',  'color': (255, 159, 10),   'label': 'Tool',         'glow': (255, 159, 10)},
    'SECURITY':  {'icon': '⊘',  'color': (255, 69, 58),    'label': 'Security',     'glow': (255, 69, 58)},
    'KNOWLEDGE': {'icon': '❖',  'color': (255, 214, 10),   'label': 'Knowledge',    'glow': (255, 214, 10)},
    'NEWS':      {'icon': '◫',  'color': (90, 200, 250),   'label': 'News',         'glow': (90, 200, 250)},
    'WEATHER':   {'icon': '◎',  'color': (0, 180, 255),    'label': 'Weather',      'glow': (0, 180, 255)},
    'PHONE':     {'icon': '◈',  'color': (50, 215, 75),    'label': 'Phone',        'glow': (50, 215, 75)},
    'TRANSLATE': {'icon': '◇',  'color': (255, 159, 10),   'label': 'Translate',    'glow': (255, 159, 10)},
}
DEFAULT_STYLE = {'icon': '⚡', 'color': (0, 212, 255), 'label': 'Processing', 'glow': (0, 212, 255)}

# ══════════════════════════════════════════════════════════
#  Notification Toast
# ══════════════════════════════════════════════════════════
class NotificationToast:
    def __init__(self, title, body, color, icon, created_at=None, action_label=None, action_cmd=None):
        self.title = title
        self.body  = body
        self.color = color
        self.icon  = icon
        self.action_label = action_label
        self.action_cmd = action_cmd
        self.action_rect = QRectF()
        self.created_at = created_at or time.time()
        self.alpha = 0.0         # 0→1 on enter, 1→0 on exit
        self.offset_y = 20.0    # slides up to 0
        self.alive = True
        self.duration = 5.0

    def tick(self, dt=1/60):
        age = time.time() - self.created_at
        if age < 0.3:
            self.alpha  = min(1.0, self.alpha + 0.12)
            self.offset_y = max(0.0, self.offset_y - 2.5)
        elif age > self.duration - 0.4:
            self.alpha = max(0.0, self.alpha - 0.12)
            if self.alpha <= 0:
                self.alive = False
        return self.alive


# ══════════════════════════════════════════════════════════
#  History Item
# ══════════════════════════════════════════════════════════
class HistoryItem:
    def __init__(self, tool_name, cat, desc, status, ts):
        self.tool_name = tool_name
        self.cat = cat
        self.desc = desc
        self.status = status
        self.ts = ts


# ══════════════════════════════════════════════════════════
#  Main Widget
# ══════════════════════════════════════════════════════════
class PremiumDynamicIsland(QWidget):

    # Sizes
    COMPACT  = (280, 46)
    PILL     = (360, 54)
    EXPANDED = (400, 168)
    LARGE    = (400, 220)
    HISTORY  = (400, 320)

    def __init__(self):
        super().__init__()
        self.setWindowFlags(
            Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setMouseTracking(True)

        self.screen_rect = QApplication.primaryScreen().geometry()

        # ── Core state ──
        self.state       = 'idle'
        self.prev_state  = 'idle'  # track for ripple trigger
        self.context     = ''
        self.tool_name   = ''
        self.tool_cat    = ''
        self.tool_desc   = ''
        self.transcript  = ''
        self.last_response = ''
        self.frame       = 0
        self.visible_flag = True
        self.mouse_pos = None
        self.drag_position = None
        self.custom_x = None
        self.custom_y = 14
        self.is_drag_hover = False
        self.mic_muted = False

        # ── Smooth text transitions ──
        self.current_label = ''
        self.prev_label    = ''
        self.label_alpha   = 1.0   # 1.0 = fully showing current, fading in
        self.prev_label_alpha = 0.0  # fading out

        # ── State transition ripple ──
        self.ripple_alpha  = 0.0
        self.ripple_radius = 0.0
        self.ripple_max_radius = 60.0
        self.ripple_color  = (0, 212, 255)
        
        self.setAcceptDrops(True)

        # ── Album art ──
        self.album_art = None
        self.current_image_url = ''
        self.btn_play_rect  = QRectF()
        self.btn_stop_rect  = QRectF()
        self.btn_prev_rect  = QRectF()

        # ── Spring physics ──
        self.current_w, self.current_h = self.COMPACT
        self.target_w,  self.target_h  = self.COMPACT
        self.vel_w = 0.0
        self.vel_h = 0.0

        # ── Face ──
        self.mouth        = 0.0
        self.target_mouth = 0.0
        self.blink        = 0.0
        self.target_blink = 0.0
        self.last_blink_f = 0
        self.pupil_x      = 0.0   # subtle gaze shift
        self.pupil_target = 0.0

        # ── Interaction ──
        self.hover        = 0.0
        self.target_hover = 0.0
        self.click_scale  = 1.0
        self.target_click_scale = 1.0
        self.long_press_start = 0
        self.showing_history  = False

        # ── Progress ──
        self.progress         = 0.0
        self.progress_target  = 0.0
        self.progress_start   = 0

        # ── Microphone level (0-1) ──
        self.mic_level        = 0.0
        self.target_mic_level = 0.0
        
        # ── AI Speaker level (0-1) ──
        self.ai_level         = 0.0
        self.target_ai_level  = 0.0

        # ── Auto-collapse ──
        self.expand_time      = 0
        self.auto_collapse_s  = 9

        # ── Notification queue ──
        self.toasts: list[NotificationToast] = []

        # ── History (last 10 tool calls) ──
        self.history: deque[HistoryItem] = deque(maxlen=10)

        # ── Response Scroll ──
        self.response_scroll = 0.0
        self.target_response_scroll = 0.0
        self.max_response_scroll = 0.0

        # ── Split pill (secondary notification) ──
        self.split_active = False
        self.split_text   = ''
        self.split_color  = (50, 215, 75)
        self.split_alpha  = 0.0
        self.split_w      = 120.0
        self.split_target_w = 0.0
        self.split_end_time = 0.0

        # ── Shimmer ──
        self.shimmer_x = -100.0

        # ── Orb accent ──
        self.orb_accent_alpha = 0.0
        self.orb_accent_color = (0, 212, 255)

        # ── Breathing pulse (idle alive feel) ──
        self.breath_phase = 0.0

        # ── Animated border hue ──
        self.border_hue = 0.0

        # ── Thinking particles (Phase 4: 16 particles with trails) ──
        self.particles = []
        import random as _rng
        for i in range(16):
            self.particles.append({
                'angle': i * (2 * math.pi / 16),
                'speed': 0.015 + _rng.random() * 0.025,
                'radius': 18.0 + _rng.random() * 10,
                'size': 1.5 + _rng.random() * 2.0,
                'alpha': 0.0,
                'trail': deque(maxlen=4),  # last 4 positions for afterglow
            })

        # ── Spark particles (Phase 4: occasional burst sparks) ──
        self.sparks = []  # list of {x, y, vx, vy, alpha, size, color}

        # ── Source indicator (voice/telegram/desktop) ──
        self.source = ''

        # ── Connection status ──
        self.last_heartbeat = time.time()
        self.agent_connected = True

        # ── System stats ──
        self.cpu_percent = 0.0
        self.ram_percent = 0.0
        self._start_sys_stats_thread()

        # ── Idle carousel ──
        self.carousel_slides = ['clock', 'tasks', 'reminders', 'tips']
        self.carousel_index = 0
        self.carousel_timer = time.time()
        self.carousel_interval = 10.0 # seconds
        self.tips_list = [
            "Tip: Ctrl+K to type commands",
            "Tip: Shift+Drag to move HUD",
            "Tip: Double-click to expand",
            "Tip: Ctrl+M to mute microphone",
            "Tip: Right-click for settings",
            "Tip: Long-press for history"
        ]
        self.current_tip_index = 0
        self.pending_tasks_count = 0
        self.today_reminders_count = 0
        self._update_carousel_counts()

        # ── Quick Actions Bar (Phase 4) ──
        self.quick_action_buttons = [
            {'icon': '🎤', 'label': 'Mute Mic',   'action': 'mute',       'rect': QRectF()},
            {'icon': '📋', 'label': 'Copy',       'action': 'copy',       'rect': QRectF()},
            {'icon': '📸', 'label': 'Screenshot', 'action': 'screenshot', 'rect': QRectF()},
            {'icon': '⌨',  'label': 'Type',       'action': 'type',       'rect': QRectF()},
            {'icon': '📌', 'label': 'Pin HUD',    'action': 'pin',        'rect': QRectF()},
            {'icon': '◫',  'label': 'History',    'action': 'history',    'rect': QRectF()},
        ]
        self.qa_hover_index = -1  # which quick action is hovered
        self.pinned = False

        # ── Segmented Progress (Phase 4) ──
        self.steps_total = 0
        self.step_current = 0
        self.step_name = ''

        # ── Text Input Field (Ctrl+K) ──
        self.input_field = QLineEdit(self)
        self.input_field.setPlaceholderText("Ask JARVIS anything...")
        self.input_field.hide()
        self.input_field.returnPressed.connect(self._submit_text_input)
        self.input_field.installEventFilter(self)
        self.input_field.setStyleSheet('''
            QLineEdit {
                background-color: rgba(20, 20, 25, 200);
                color: #ffffff;
                border: 1px solid rgba(255, 255, 255, 25);
                border-radius: 12px;
                padding: 6px 12px;
                font-family: "Segoe UI";
                font-size: 13px;
            }
            QLineEdit:focus {
                border: 1px solid rgba(0, 212, 255, 180);
                background-color: rgba(15, 15, 20, 220);
            }
        ''')

        # Placement
        self.setGeometry(
            int((self.screen_rect.width() - self.current_w) / 2), 14,
            int(self.current_w), int(self.current_h)
        )

        # ── UDP ──
        self.udp = QUdpSocket(self)
        self.udp.bind(QHostAddress.LocalHost, 5005)
        self.udp.readyRead.connect(self._read_udp)

        # ── 60 FPS tick ──
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(16)

        # ── Global hotkey: Ctrl+J ──
        from PyQt5.QtWidgets import QShortcut
        shortcut = QShortcut(QKeySequence("Ctrl+J"), self)
        shortcut.setContext(Qt.ApplicationShortcut)
        shortcut.activated.connect(self._toggle_visibility)
        
        # ── Global hotkey: Ctrl+M (Mute) ──
        mute_shortcut = QShortcut(QKeySequence("Ctrl+M"), self)
        mute_shortcut.setContext(Qt.ApplicationShortcut)
        mute_shortcut.activated.connect(self._toggle_mute)

        # ── Global hotkey: Ctrl+K (Text Input) ──
        input_shortcut = QShortcut(QKeySequence("Ctrl+K"), self)
        input_shortcut.setContext(Qt.ApplicationShortcut)
        input_shortcut.activated.connect(self._enter_input_mode)

    # ════════════════════════════════════════════════
    #  System Stats Thread
    # ════════════════════════════════════════════════
    def _start_sys_stats_thread(self):
        def _poll():
            while True:
                try:
                    import psutil
                    self.cpu_percent = psutil.cpu_percent(interval=2)
                    self.ram_percent = psutil.virtual_memory().percent
                except ImportError:
                    # Fallback: no psutil
                    self.cpu_percent = 0.0
                    self.ram_percent = 0.0
                    break
                except Exception:
                    pass
        threading.Thread(target=_poll, daemon=True).start()

    # ════════════════════════════════════════════════
    #  UDP
    # ════════════════════════════════════════════════
    def _read_udp(self):
        while self.udp.hasPendingDatagrams():
            raw, _, _ = self.udp.readDatagram(self.udp.pendingDatagramSize())
            try:
                d = json.loads(raw.decode('utf-8'))
                self._handle_message(d)
            except Exception as e:
                print(e)
                pass

    def _send_media_cmd(self, cmd):
        import socket
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            msg = cmd.encode()
            for p in range(5006, 5011):
                sock.sendto(msg, ("127.0.0.1", p))
            sock.close()
        except:
            pass

    def _handle_message(self, d):
        s   = d.get('state', self.state)
        ctx = d.get('context', '')

        # Heartbeat: agent sends periodic pings
        if s == 'heartbeat':
            self.last_heartbeat = time.time()
            self.agent_connected = True
            return

        prev_state = self.state
        self.prev_state = prev_state
        self.state      = s
        self.context    = ctx
        self.last_heartbeat = time.time()  # any message counts as heartbeat
        self.agent_connected = True

        if prev_state == 'input' and s != 'input':
            self.input_field.hide()

        # ── Trigger ripple on major state transitions ──
        if s != prev_state and s in ('listening', 'thinking', 'speaking'):
            c1, _ = self._state_colors()
            self.ripple_color = c1
            self.ripple_alpha = 0.85
            self.ripple_radius = 0.0

        # Track source
        if 'source' in d:
            self.source = d['source']

        if s == 'speaking' and prev_state != 'speaking':
            self._send_media_cmd("duck")
        elif s != 'speaking' and prev_state == 'speaking':
            self._send_media_cmd("unduck")

        self.tool_name  = d.get('tool_name', self.tool_name)
        self.tool_cat   = d.get('category',  self.tool_cat)
        self.tool_desc  = d.get('description', self.tool_desc)

        # ── Segmented progress fields (Phase 4) ──
        if 'steps_total' in d:
            self.steps_total = int(d['steps_total'])
        if 'step_current' in d:
            self.step_current = int(d['step_current'])
        if 'step_name' in d:
            self.step_name = str(d['step_name'])

        if 'mic_level' in d:
            self.target_mic_level = float(d['mic_level'])

        if 'transcript' in d:
            if ctx == 'response':
                self.last_response = d['transcript']
            else:
                self.transcript = d['transcript']

        if 'notify' in d:
            n = d['notify']
            self._push_toast(n.get('title',''), n.get('body',''), n.get('category','TOOL'))

        if 'image_url' in d and d['image_url'] != self.current_image_url:
            self.current_image_url = d['image_url']
            self.album_art = None
            def fetch(url):
                try:
                    import requests
                    res = requests.get(url, timeout=3)
                    img = QImage(); img.loadFromData(res.content)
                    self.album_art = img
                except: pass
            threading.Thread(target=fetch, args=(self.current_image_url,), daemon=True).start()

        # ── History ──
        if ctx == 'tool' and self.tool_name:
            status = d.get('status', 'success')
            self.history.appendleft(HistoryItem(
                self.tool_name, self.tool_cat, self.tool_desc, status, time.time()
            ))

        # ── Split pill: transient alerts while in another state ──
        if ctx == 'notify_secondary' or (ctx == 'tool' and self.context not in ('', 'idle') and prev_state == 'speaking'):
            self._activate_split(d.get('split_text', self.tool_cat), d.get('category', 'TOOL'))

        # ── Decide target size ──
        if self.showing_history:
            self.target_w, self.target_h = self.HISTORY
        elif self.target_hover > 0.0:
            pass # Leave it expanded
        elif s == 'speaking' or s == 'thinking':
            self.target_w, self.target_h = self.PILL
        elif s == 'listening':
            self.target_w, self.target_h = (320, 50)
        elif s == 'input':
            self.target_w, self.target_h = (400, 60)
        else:
            self.target_w, self.target_h = self._get_compact_size()

        if ctx == 'tool':
            self.progress = 0.0
            self.progress_target = 1.0
            self.progress_start = time.time()
            self.expand_time = time.time()
            # orb accent
            cat = self.tool_cat.upper()
            style = CATEGORY_STYLE.get(cat, DEFAULT_STYLE)
            self.orb_accent_color = style['glow']
            self.orb_accent_alpha = 1.0
        elif ctx == 'response' and self.last_response:
            self.expand_time = time.time()

    def _push_toast(self, title, body, cat='TOOL'):
        style = CATEGORY_STYLE.get(cat.upper(), DEFAULT_STYLE)
        t = NotificationToast(title, body, style['color'], style['icon'])
        self.toasts.append(t)
        # cap at 3
        if len(self.toasts) > 3:
            self.toasts.pop(0)

    def _activate_split(self, label, cat='TOOL'):
        style = CATEGORY_STYLE.get(cat.upper(), DEFAULT_STYLE)
        self.split_text   = f"{style['icon']} {label}"
        self.split_color  = style['color']
        self.split_active = True
        self.split_alpha  = 0.0
        self.split_target_w = 130.0
        self.split_end_time = time.time() + 5.0

    def _toggle_visibility(self):
        self.visible_flag = not self.visible_flag
        if self.visible_flag:
            self.show()
        else:
            self.hide()

    def _toggle_mute(self):
        self.mic_muted = not getattr(self, 'mic_muted', False)
        state = "Muted" if self.mic_muted else "Unmuted"
        self._push_toast("Microphone", f"Native mic {state}", "SYSTEM")

    def _enter_input_mode(self):
        self.state = 'input'
        self.target_w, self.target_h = (400, 60)
        self.input_field.show()
        self.input_field.setFocus()
        self.activateWindow()

    def _exit_input_mode(self):
        self.input_field.clear()
        self.input_field.hide()
        self.state = 'idle'
        self.target_w, self.target_h = self._get_compact_size()
        self.update()

    def _submit_text_input(self):
        text = self.input_field.text().strip()
        if text:
            self._send_udp_message({"type": "text_input", "text": text})
            self._push_toast("Keyboard", f"Sent: {text}", "INPUT")
            self.input_field.clear()
        self._exit_input_mode()

    def eventFilter(self, obj, event):
        from PyQt5.QtCore import QEvent
        if obj == self.input_field and event.type() == QEvent.KeyPress:
            if event.key() == Qt.Key_Escape:
                self._exit_input_mode()
                return True
        return super().eventFilter(obj, event)

    def _send_udp_message(self, data):
        try:
            raw = json.dumps(data).encode('utf-8')
            self.udp.writeDatagram(raw, QHostAddress.LocalHost, 5004)
        except Exception as e:
            print("UDP send error:", e)

    def _get_compact_size(self):
        txt = self._get_carousel_text()
        fm = QFontMetrics(QFont("Segoe UI", 11, QFont.DemiBold))
        text_w = fm.horizontalAdvance(txt)
        needed_w = text_w + 110  # face orb (50) + padding (10) + stats (50)
        target_w = max(self.COMPACT[0], min(360, needed_w))
        return target_w, self.COMPACT[1]

    def _get_carousel_text(self):
        slide = self.carousel_slides[self.carousel_index]
        if slide == 'clock':
            import datetime
            now = datetime.datetime.now()
            date_str = now.strftime("%a, %b %d").replace(' 0', ' ')
            time_str = now.strftime("%I:%M %p").lstrip('0')
            return f"{date_str} \u00b7 {time_str}"
        elif slide == 'tasks':
            return f"☑ {self.pending_tasks_count} Tasks Pending"
        elif slide == 'reminders':
            return f"🔔 {self.today_reminders_count} Reminders Today"
        elif slide == 'tips':
            return self.tips_list[self.current_tip_index]
        return "JARVIS"

    def _update_carousel_counts(self):
        def _query():
            # Query pending tasks count
            try:
                db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "jarvis_memory", "tasks.db")
                if os.path.exists(db_path):
                    import sqlite3
                    with sqlite3.connect(db_path) as conn:
                        c = conn.cursor()
                        c.execute("SELECT COUNT(*) FROM tasks WHERE status = 'pending'")
                        self.pending_tasks_count = c.fetchone()[0]
                else:
                    self.pending_tasks_count = 0
            except Exception:
                self.pending_tasks_count = 0

            # Query today's reminders count
            try:
                db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "jarvis_memory", "reminders.db")
                if os.path.exists(db_path):
                    import datetime
                    today = datetime.datetime.now().strftime("%Y-%m-%d")
                    import sqlite3
                    with sqlite3.connect(db_path) as conn:
                        c = conn.cursor()
                        c.execute("SELECT COUNT(*) FROM reminders WHERE timestamp LIKE ?", (f"{today}%",))
                        self.today_reminders_count = c.fetchone()[0]
                else:
                    self.today_reminders_count = 0
            except Exception:
                self.today_reminders_count = 0
        threading.Thread(target=_query, daemon=True).start()

    # ════════════════════════════════════════════════
    #  Game Loop
    # ════════════════════════════════════════════════
    def _tick(self):
        self.frame += 1
        now = time.time()

        # ── Idle carousel rotation ──
        if self.state == 'idle':
            if now - self.carousel_timer > self.carousel_interval:
                self.carousel_timer = now
                self.carousel_index = (self.carousel_index + 1) % len(self.carousel_slides)
                if self.carousel_slides[self.carousel_index] == 'tips':
                    self.current_tip_index = (self.current_tip_index + 1) % len(self.tips_list)
                self._update_carousel_counts()

        # ── Dynamic size update for idle state carousel ──
        if self.state == 'idle' and not self.showing_history and self.target_hover == 0.0:
            self.target_w, self.target_h = self._get_compact_size()

        # ── Auto-collapse ──
        if self.expand_time and now - self.expand_time > self.auto_collapse_s:
            if self.state not in ('speaking',) and not self.showing_history:
                # Don't auto-collapse media or if pinned
                if self.tool_cat.upper() != 'MEDIA' and not getattr(self, 'pinned', False):
                    self.expand_time   = 0
                    self.last_response = ''
                    sz = self.PILL if self.state == 'thinking' else self._get_compact_size()
                    self.target_w, self.target_h = sz

        # ── Spring physics ──
        tension, damp = 0.04, 0.82
        self.vel_w += (self.target_w - self.current_w) * tension
        self.vel_w *= damp
        self.current_w += self.vel_w
        self.vel_h += (self.target_h - self.current_h) * tension
        self.vel_h *= damp
        self.current_h += self.vel_h

        # ── Click bounce ──
        self.click_scale += (self.target_click_scale - self.click_scale) * 0.22

        # ── Positioning ──
        if self.custom_x is not None:
            tx = self.custom_x
            nx = self.x() + (tx - self.x()) * 0.2
            ny = self.y() + (self.custom_y - self.y()) * 0.2
        else:
            tx = (self.screen_rect.width() - self.current_w) / 2
            nx = self.x() + (tx - self.x()) * 0.09
            ny = 14
        
        extra_w = 0
        if self.split_alpha > 0.01:
            extra_w = int(140 * self.split_alpha)

        self.setGeometry(int(nx), int(ny), int(self.current_w) + extra_w, int(self.current_h))

        # ── Position QLineEdit text box dynamically in input mode ──
        if self.state == 'input':
            face_cx = 28.0
            face_r = 13.0
            tx_in = face_cx + face_r + 14
            self.input_field.setGeometry(
                int(tx_in), 
                int((self.current_h - 32) / 2), 
                int(self.current_w - tx_in - 20), 
                32
            )

        # ── Blink ──
        if self.frame - self.last_blink_f > 150 + (hash(self.frame // 3) % 90):
            self.last_blink_f = self.frame
            self.target_blink = 1
        if self.target_blink > 0 and self.frame - self.last_blink_f > 6:
            self.target_blink = 0
        self.blink += (self.target_blink - self.blink) * 0.38

        # ── Mouth ──
        if self.state == 'speaking':
            self.target_mouth = 0.3 + abs(math.sin(self.frame * 0.18)) * 0.5
        elif self.state == 'listening':
            lv = self.mic_level
            self.target_mouth = 0.05 + lv * 0.4
        else:
            self.target_mouth = 0.0
        self.mouth += (self.target_mouth - self.mouth) * 0.22

        # ── Pupil gaze ──
        if self.frame % 120 == 0:
            import random
            self.pupil_target = random.uniform(-2.5, 2.5)
        self.pupil_x += (self.pupil_target - self.pupil_x) * 0.04

        # ── Hover ──
        self.hover += (self.target_hover - self.hover) * 0.13

        # ── Response Scroll ──
        self.response_scroll += (self.target_response_scroll - self.response_scroll) * 0.2

        # ── Mic & AI Audio level ──
        self.mic_level += (self.target_mic_level - self.mic_level) * 0.25
        self.ai_level  += (self.target_ai_level - self.ai_level) * 0.25
        
        # Decay AI level so it drops smoothly to 0 when the AI stops speaking
        self.target_ai_level *= 0.85

        # ── Progress ──
        if self.progress_target > self.progress:
            elapsed = now - self.progress_start
            self.progress = min(1.0, elapsed / 8.0)

        # ── Shimmer ──
        self.shimmer_x = (self.shimmer_x + 2.5) % (self.current_w + 120)

        # ── Orb accent fade ──
        if self.orb_accent_alpha > 0:
            self.orb_accent_alpha = max(0.0, self.orb_accent_alpha - 0.003)

        # ── Breathing pulse ──
        self.breath_phase = (self.breath_phase + 0.025) % (2 * math.pi)

        # ── Animated border hue ──
        self.border_hue = (self.border_hue + 0.3) % 360

        # ── State transition ripple ──
        if self.ripple_alpha > 0:
            self.ripple_radius += (self.ripple_max_radius - self.ripple_radius) * 0.12
            self.ripple_alpha = max(0.0, self.ripple_alpha - 0.025)

        # ── Label cross-fade ──
        if self.label_alpha < 1.0:
            self.label_alpha = min(1.0, self.label_alpha + 0.08)
        if self.prev_label_alpha > 0.0:
            self.prev_label_alpha = max(0.0, self.prev_label_alpha - 0.10)

        # ── Thinking particles (Phase 4: trails + sparks) ──
        is_thinking = self.state == 'thinking'
        # Optimization: skip particle updates if idle and no visual output
        skip_particles = (self.state == 'idle' and self.hover == 0.0 and 
                          not any(pt['alpha'] > 0 for pt in self.particles) and 
                          len(self.sparks) == 0)
                          
        if not skip_particles:
            for pt in self.particles:
                pt['angle'] += pt['speed']
                if is_thinking:
                    pt['alpha'] = min(1.0, pt['alpha'] + 0.06)
                    # Store trail position
                    face_cx = 28.0
                    face_cy = min(self.current_h / 2, 26.0) if self.current_h > 60 else self.current_h / 2
                    px = face_cx + math.cos(pt['angle']) * pt['radius']
                    py = face_cy + math.sin(pt['angle']) * pt['radius']
                    pt['trail'].append((px, py))
                else:
                    pt['alpha'] = max(0.0, pt['alpha'] - 0.04)
                    if pt['alpha'] <= 0:
                        pt['trail'].clear()

            # ── Spark particles update ──
            if is_thinking and self.frame % 3 == 0:
                import random
                if random.random() < 0.02:  # 2% chance per 3 frames
                    face_cx = 28.0
                    face_cy = min(self.current_h / 2, 26.0) if self.current_h > 60 else self.current_h / 2
                    angle = random.uniform(0, 2 * math.pi)
                    speed = random.uniform(1.0, 3.0)
                    self.sparks.append({
                        'x': face_cx + math.cos(angle) * 18,
                        'y': face_cy + math.sin(angle) * 18,
                        'vx': math.cos(angle) * speed,
                        'vy': math.sin(angle) * speed,
                        'alpha': 1.0,
                        'size': random.uniform(1.0, 2.5),
                        'color': random.choice([
                            (255, 200, 80), (255, 160, 50), (255, 240, 120),
                            (0, 212, 255), (175, 82, 222)
                        ]),
                    })
            # Update existing sparks
            new_sparks = []
            for sp in self.sparks:
                sp['x'] += sp['vx']
                sp['y'] += sp['vy']
                sp['vy'] += 0.05  # gravity
                sp['alpha'] -= 0.025
                if sp['alpha'] > 0:
                    new_sparks.append(sp)
            self.sparks = new_sparks

        # ── Connection status ──
        if time.time() - self.last_heartbeat > 15:
            self.agent_connected = False

        # ── Split pill ──
        if self.split_active:
            self.split_alpha = min(1.0, self.split_alpha + 0.08)
            if now > self.split_end_time:
                self.split_alpha = max(0.0, self.split_alpha - 0.06)
                if self.split_alpha <= 0:
                    self.split_active = False
                    self.split_target_w = 0.0

        # ── Toast queue ──
        self.toasts = [t for t in self.toasts if t.tick()]

        # ── Adaptive frame rate ──
        # Drop to ~10 FPS when idle to save CPU; restore 60 FPS when animating
        is_animating = (
            self.state != 'idle' or
            abs(self.vel_w) > 0.5 or
            abs(self.vel_h) > 0.5 or
            self.toasts or
            self.split_active or
            self.ripple_alpha > 0.01 or
            self.hover > 0.01 or
            self.showing_history or
            any(pt['alpha'] > 0.01 for pt in self.particles) or
            self.sparks
        )
        new_interval = 16 if is_animating else 100
        if self.timer.interval() != new_interval:
            self.timer.setInterval(new_interval)

        self.update()

    # ════════════════════════════════════════════════
    #  Interaction
    # ════════════════════════════════════════════════
    def enterEvent(self, e):
        self.target_hover = 1.0
        if not self.showing_history:
            cat = self.tool_cat.upper() if self.tool_cat else ''
            if cat in ('MEDIA', 'FINANCE', 'RESEARCH', 'CALENDAR', 'CODE') or self.last_response:
                self.target_w, self.target_h = self.EXPANDED
            else:
                self.target_w, self.target_h = self.PILL

    def leaveEvent(self, e):
        self.target_hover = 0.0
        self.mouse_pos = None
        if not self.showing_history:
            self.target_w, self.target_h = self._get_compact_size()

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            if QApplication.keyboardModifiers() & Qt.ShiftModifier:
                self.drag_position = e.globalPos() - self.frameGeometry().topLeft()
                e.accept()
                return

            pos = QPointF(e.pos())

            # ── Toast Actions (Phase 5) ──
            if self.toasts:
                for toast in self.toasts:
                    if toast.action_label and toast.action_rect.contains(pos):
                        self._handle_toast_action(toast.action_cmd)
                        toast.alive = False  # Dismiss on click
                        self._bounce(0.96)
                        return

            # ── Quick Actions Bar clicks (Phase 4) ──
            if self.current_h > 60 and not self.showing_history:
                for btn in self.quick_action_buttons:
                    if btn['rect'].contains(pos):
                        self._handle_quick_action(btn['action'])
                        self._bounce(0.96)
                        self.long_press_start = time.time() + 999999
                        return

            # Media controls
            if self.context == 'tool' and self.tool_cat.upper() == 'MEDIA':
                cmd = None
                if self.btn_prev_rect.contains(pos): cmd = "prev"
                elif self.btn_play_rect.contains(pos): cmd = "playpause"
                elif self.btn_stop_rect.contains(pos): cmd = "stop"
                if cmd:
                    self._send_media_cmd(cmd)
                    self._bounce()
                    self.long_press_start = time.time() + 999999
                    return

            # Copy response text
            if self.current_h > 150 and not self.showing_history:
                body_rect = QRectF(50, 58, self.current_w - 70, 55) # approximate body rect
                if body_rect.contains(pos):
                    text_to_copy = self.last_response if self.context == 'response' else self.tool_desc
                    if text_to_copy:
                        QApplication.clipboard().setText(text_to_copy)
                        self._push_toast("Copied", "Response copied to clipboard", "SYSTEM")
                        self._bounce(0.96)
                        return

            self._bounce(0.96)
            self.long_press_start = time.time()

    def mouseMoveEvent(self, e):
        self.mouse_pos = e.pos()
        if self.drag_position and (e.buttons() & Qt.LeftButton):
            new_pos = e.globalPos() - self.drag_position
            self.custom_x = new_pos.x()
            self.custom_y = new_pos.y()
            self.move(new_pos)
            e.accept()

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.LeftButton:
            if getattr(self, 'drag_position', None):
                self.drag_position = None
                e.accept()
                return
            
            held = time.time() - self.long_press_start
            self.target_click_scale = 1.0
            # Long press → toggle history
            if held > 0.6:
                self.showing_history = not self.showing_history
                if self.showing_history:
                    self.target_w, self.target_h = self.HISTORY
                else:
                    self.target_w, self.target_h = self._get_compact_size()

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls() or e.mimeData().hasText():
            self.is_drag_hover = True
            self.target_w, self.target_h = self.EXPANDED
            e.accept()
        else:
            e.ignore()

    def dragLeaveEvent(self, e):
        self.is_drag_hover = False
        if not self.showing_history:
            self.target_w, self.target_h = self._get_compact_size()

    def dropEvent(self, e):
        self.is_drag_hover = False
        if not self.showing_history:
            self.target_w, self.target_h = self._get_compact_size()
            
        urls = e.mimeData().urls()
        text = e.mimeData().text()
        
        dropped_items = []
        if urls:
            dropped_items = [u.toLocalFile() for u in urls if u.isLocalFile()]
        elif text:
            dropped_items = [text]
            
        if dropped_items:
            item_name = dropped_items[0].replace('\\', '/').split('/')[-1]
            if len(item_name) > 20: item_name = item_name[:17] + "..."
            
            self._bounce(1.08)
            self._push_toast("Item Dropped", f"Sent '{item_name}' to JARVIS", "SYSTEM")
            
            try:
                import os, json
                drop_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dropped_items.json")
                with open(drop_file, "w") as f:
                    json.dump(dropped_items, f)
            except Exception as ex:
                print("Drop error:", ex)

    def mouseDoubleClickEvent(self, e):
        if self.current_h > 60:
            self.target_w, self.target_h = self._get_compact_size()
            self.last_response = ''
            self.expand_time = 0
            self.showing_history = False
        else:
            cat = self.tool_cat.upper() if self.tool_cat else ''
            if cat in ('MEDIA', 'FINANCE', 'RESEARCH', 'CALENDAR', 'CODE') or self.last_response:
                self.target_w, self.target_h = self.EXPANDED
            else:
                self.target_w, self.target_h = self.PILL
            self.expand_time = time.time()

    def wheelEvent(self, e):
        # Scroll through history or response
        if self.current_h > 150 and not self.showing_history: # Expanded view
            delta = e.angleDelta().y()
            if delta > 0:
                self.target_response_scroll = max(0.0, self.target_response_scroll - 30.0)
            elif delta < 0:
                self.target_response_scroll = min(self.max_response_scroll, self.target_response_scroll + 30.0)

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        menu.setStyleSheet('''
            QMenu {
                background-color: #1e1e22;
                color: #f0f0f0;
                border: 1px solid #3a3a4a;
                border-radius: 10px;
                padding: 6px 4px;
                font-family: "Segoe UI";
                font-size: 12px;
            }
            QMenu::item {
                padding: 7px 22px;
                border-radius: 6px;
                margin: 1px 4px;
            }
            QMenu::item:selected {
                background-color: rgba(0,180,255,0.18);
                color: #00d4ff;
            }
            QMenu::separator {
                height: 1px;
                background: #3a3a4a;
                margin: 4px 10px;
            }
        ''')

        collapse_a = QAction("⊖  Collapse", self)
        history_a  = QAction("◫  History" + (" ✓" if self.showing_history else ""), self)
        reset_pos_a = QAction("⌖  Reset Position", self)
        
        mute_lbl = "Unmute Mic" if getattr(self, 'mic_muted', False) else "Mute Mic"
        mute_a = QAction(f"🎤  {mute_lbl}  (Ctrl+M)", self)
        
        settings_a = QAction("⚙  Settings", self)
        
        sep1 = menu.addSeparator()
        stop_a     = QAction("⊘  Stop JARVIS", self)
        hide_a     = QAction("◎  Hide  (Ctrl+J)", self)

        menu.addAction(collapse_a)
        menu.addAction(history_a)
        menu.addAction(reset_pos_a)
        menu.addAction(mute_a)
        menu.addAction(settings_a)
        menu.addSeparator()
        menu.addAction(hide_a)
        menu.addSeparator()
        menu.addAction(stop_a)

        action = menu.exec_(self.mapToGlobal(event.pos()))
        if action == collapse_a:
            self.target_w, self.target_h = self._get_compact_size()
            self.last_response = ''; self.expand_time = 0; self.showing_history = False
        elif action == history_a:
            self.showing_history = not self.showing_history
            self.target_w, self.target_h = self.HISTORY if self.showing_history else self._get_compact_size()
        elif action == reset_pos_a:
            self.custom_x = None
            self.custom_y = 14
        elif action == mute_a:
            self._toggle_mute()
        elif action == settings_a:
            self._open_settings()
        elif action == hide_a:
            self._toggle_visibility()
        elif action == stop_a:
            os.system('taskkill /F /FI "WINDOWTITLE eq JARVIS - Agent" >nul 2>&1')
            os.system('taskkill /F /FI "WINDOWTITLE eq JARVIS - Token Server" >nul 2>&1')
            os.system('taskkill /F /FI "WINDOWTITLE eq JARVIS - Telegram Bot" >nul 2>&1')
            QTimer.singleShot(500, QApplication.quit)

    def _open_settings(self):
        from PyQt5.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QSpinBox, QPushButton
        dlg = QDialog(self)
        dlg.setWindowTitle("JARVIS HUD Settings")
        dlg.setFixedSize(300, 150)
        dlg.setStyleSheet("background-color: #1e1e22; color: white;")
        layout = QVBoxLayout()
        
        row1 = QHBoxLayout()
        lbl1 = QLabel("Auto-collapse Timeout (s):")
        spn1 = QSpinBox()
        spn1.setRange(3, 60)
        spn1.setValue(self.auto_collapse_s)
        spn1.setStyleSheet("background-color: #2a2a32; color: white; border: 1px solid #3a3a4a;")
        row1.addWidget(lbl1)
        row1.addWidget(spn1)
        layout.addLayout(row1)
        
        btn_box = QHBoxLayout()
        save_btn = QPushButton("Save")
        save_btn.setStyleSheet("background-color: #007aff; color: white; padding: 5px;")
        save_btn.clicked.connect(lambda: dlg.accept())
        btn_box.addStretch()
        btn_box.addWidget(save_btn)
        layout.addLayout(btn_box)
        
        dlg.setLayout(layout)
        if dlg.exec_():
            self.auto_collapse_s = spn1.value()
            try:
                import json, os
                s_path = os.path.join(os.path.dirname(__file__), "jarvis_memory", "hud_settings.json")
                with open(s_path, "w") as f:
                    json.dump({"auto_collapse_s": self.auto_collapse_s}, f)
            except Exception as e:
                print("Failed to save settings:", e)

    def _bounce(self, s=0.95):
        self.target_click_scale = s
        QTimer.singleShot(140, lambda: setattr(self, 'target_click_scale', 1.0))

    def _handle_quick_action(self, action):
        """Handle quick action button clicks."""
        if action == 'mute':
            self._toggle_mute()
        elif action == 'copy':
            text_to_copy = self.last_response or self.tool_desc or self.transcript
            if text_to_copy:
                QApplication.clipboard().setText(text_to_copy)
                self._push_toast("Copied", "Text copied to clipboard", "SYSTEM")
            else:
                self._push_toast("Copy", "Nothing to copy yet", "SYSTEM")
        elif action == 'screenshot':
            self._send_udp_message({"type": "action", "action": "screenshot"})
            self._push_toast("Screenshot", "Taking screenshot...", "VISION")
        elif action == 'type':
            self._enter_input_mode()
        elif action == 'history':
            self.showing_history = not self.showing_history
            if self.showing_history:
                self.target_w, self.target_h = self.HISTORY
            else:
                self.target_w, self.target_h = self._get_compact_size()
        elif action == 'pin':
            self.pinned = not getattr(self, 'pinned', False)
            if self.pinned:
                self._push_toast("Pinned", "HUD will stay expanded.", "SYSTEM")
            else:
                self._push_toast("Unpinned", "HUD will auto-collapse.", "SYSTEM")

    def _handle_toast_action(self, cmd):
        """Handle clicks on interactive toast buttons."""
        if cmd == 'undo_close':
            self._push_toast("Undo", "Action reverted.", "SYSTEM")
            # Logic to undo closing an app or file could go here
        elif cmd.startswith("open_file:"):
            filepath = cmd.split(":", 1)[1]
            try:
                os.startfile(filepath)
                self._push_toast("Opened", f"Opened {os.path.basename(filepath)}", "FILES")
            except Exception as e:
                self._push_toast("Error", "Could not open file", "SYSTEM")
        elif cmd == 'dismiss':
            pass # Toast already dismissed in mousePressEvent

    # ════════════════════════════════════════════════
    #  Paint
    # ════════════════════════════════════════════════
    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.TextAntialiasing)
        p.setRenderHint(QPainter.SmoothPixmapTransform)

        w = self.current_w
        h = self.height()
        is_expanded = h > 60

        # Click scale transform
        if abs(self.click_scale - 1.0) > 0.001:
            p.translate(w/2, h/2)
            p.scale(self.click_scale, self.click_scale)
            p.translate(-w/2, -h/2)

        # ─── 1. OUTER GLOW / DROP SHADOW ───
        radius = 20 if is_expanded else h / 2
        c1, c2 = self._state_colors()

        for i in range(5):
            d = (5 - i) * 2.5
            shadow = QPainterPath()
            shadow.addRoundedRect(QRectF(-d, -d, w + d*2, h + d*2), radius + d, radius + d)
            p.setPen(Qt.NoPen)
            p.fillPath(shadow, QColor(0, 0, 0, 8 + i * 8))

        # State-colored glow ring (subtle)
        glow_alpha = int(18 + 22 * self.hover)
        for i in range(2):
            d2 = (2-i)
            gr = QPainterPath()
            gr.addRoundedRect(QRectF(-d2, -d2, w+d2*2, h+d2*2), radius+d2, radius+d2)
            p.fillPath(gr, QColor(c1[0], c1[1], c1[2], glow_alpha))

        # ─── 2. BACKGROUND PILL ───
        bg = QPainterPath()
        bg.addRoundedRect(QRectF(0, 0, w, h), radius, radius)

        bg_grad = QLinearGradient(0, 0, 0, h)
        bg_grad.setColorAt(0, QColor(26, 26, 30, 245))
        bg_grad.setColorAt(0.5, QColor(18, 18, 22, 248))
        bg_grad.setColorAt(1, QColor(10, 10, 14, 252))
        p.fillPath(bg, bg_grad)

        # Glassmorphism shimmer
        shimmer_grad = QLinearGradient(self.shimmer_x - 60, 0, self.shimmer_x + 60, 0)
        shimmer_grad.setColorAt(0, QColor(255, 255, 255, 0))
        shimmer_grad.setColorAt(0.5, QColor(255, 255, 255, int(9 + 7 * self.hover)))
        shimmer_grad.setColorAt(1, QColor(255, 255, 255, 0))
        p.setClipPath(bg)
        p.fillRect(QRectF(0, 0, w, h), shimmer_grad)
        p.setClipping(False)

        # Top highlight line — animated gradient border
        border_intensity = 0.3 + 0.2 * self.hover
        if self.state == 'thinking':
            border_intensity = 0.7
        elif self.state == 'speaking':
            border_intensity = 0.5
        elif self.state == 'listening':
            border_intensity = 0.4

        cg = QConicalGradient(w/2, h/2, self.border_hue)
        h1 = QColor.fromHslF(self.border_hue / 360.0, 0.8, 0.65)
        h2 = QColor.fromHslF(((self.border_hue + 120) % 360) / 360.0, 0.7, 0.6)
        h3 = QColor.fromHslF(((self.border_hue + 240) % 360) / 360.0, 0.75, 0.55)
        h1.setAlphaF(border_intensity)
        h2.setAlphaF(border_intensity * 0.7)
        h3.setAlphaF(border_intensity * 0.5)
        cg.setColorAt(0.0, h1)
        cg.setColorAt(0.33, h2)
        cg.setColorAt(0.66, h3)
        cg.setColorAt(1.0, h1)
        p.setPen(QPen(QBrush(cg), 1.2))
        p.setBrush(Qt.NoBrush)
        p.drawPath(bg)

        if getattr(self, 'is_drag_hover', False):
            p.setPen(QPen(QColor(0, 212, 255, 200), 2.5, Qt.DashLine, Qt.RoundCap))
            p.setBrush(QColor(0, 212, 255, 20))
            p.drawRoundedRect(QRectF(4, 4, w - 8, h - 8), radius - 4, radius - 4)
            
            p.setPen(QColor(0, 212, 255, 240))
            p.setFont(QFont("Segoe UI", 13, QFont.Bold))
            p.drawText(QRectF(0, 0, w, h), Qt.AlignCenter, "Drop to Send to JARVIS")
            p.end()
            return

        # ─── 3. FACE ORB ───
        face_cx = 28.0
        face_cy = min(h/2, 26.0) if is_expanded else h/2
        face_r  = 13.0
        self._draw_face(p, face_cx, face_cy, face_r)

        # ─── 3b. CONNECTION STATUS DOT ───
        dot_r = 3.5
        dot_x = w - 12
        dot_y = 8 if is_expanded else h / 2 - dot_r
        if self.agent_connected:
            p.setBrush(QColor(50, 215, 75, 200))
        else:
            p.setBrush(QColor(255, 59, 48, 200))
        p.setPen(Qt.NoPen)
        p.drawEllipse(QRectF(dot_x - dot_r, dot_y, dot_r*2, dot_r*2))

        # ─── 4. CONTENT ───
        text_x = face_cx + face_r + 14
        p.setPen(Qt.NoPen)

        if self.showing_history:
            self._draw_history(p, text_x, w, h)
        elif is_expanded:
            self._draw_expanded(p, text_x, w, h)
        else:
            self._draw_compact(p, text_x, w, h)

        # ─── 5. TOASTS (below pill) ───
        self._draw_toasts(p, w, h)

        # ─── 6. SPLIT PILL ───
        if self.split_alpha > 0.01:
            self._draw_split_pill(p, w, h)

        p.end()

    # ─────────────────────────────────────────────
    #  Split Pill
    # ─────────────────────────────────────────────
    def _draw_split_pill(self, p, w, h):
        sp_w = self.split_target_w * self.split_alpha
        if sp_w < 10: return
        sp_h = 36
        gap = 12
        sp_x = w + gap
        sp_y = (h - sp_h) / 2
        
        path = QPainterPath()
        path.addRoundedRect(QRectF(sp_x, sp_y, sp_w, sp_h), sp_h/2, sp_h/2)
        p.setPen(Qt.NoPen)
        p.fillPath(path, QColor(20, 20, 24, int(240 * self.split_alpha)))
        
        bc = QColor(*self.split_color)
        bc.setAlpha(int(100 * self.split_alpha))
        p.setPen(QPen(bc, 1))
        p.drawPath(path)
        
        if sp_w > 40:
            p.setClipPath(path)
            font = QFont("Segoe UI", 9, QFont.DemiBold)
            p.setFont(font)
            tc = QColor(*self.split_color)
            tc.setAlpha(int(255 * self.split_alpha))
            p.setPen(tc)
            p.drawText(QRectF(sp_x + 10, sp_y, sp_w - 20, sp_h), Qt.AlignCenter, self.split_text)
            p.setClipping(False)
            p.setPen(Qt.NoPen)

    # ─────────────────────────────────────────────
    #  Face Orb
    # ─────────────────────────────────────────────
    def _get_emotion(self):
        if self.state == 'thinking':
            return 'thinking'
        text = (self.last_response if self.state == 'speaking' else self.transcript).lower()
        if any(w in text for w in ['sorry', 'error', 'fail', 'cannot', 'unable', 'issue', 'unfortunately']):
            return 'sad'
        if any(w in text for w in ['happy', 'great', 'awesome', 'good', 'success', 'done', 'yes', 'perfect', 'love']):
            return 'happy'
        return 'neutral'

    def _draw_face(self, p, cx, cy, R):
        c1, c2 = self._state_colors()
        t = self.frame * 0.04
        deform = 4 if self.state == 'speaking' else 2 if self.state == 'thinking' else 1
        emotion = self._get_emotion()

        # Orb accent ring (category color)
        if self.orb_accent_alpha > 0.01:
            ac = self.orb_accent_color
            ring = QRadialGradient(cx, cy, R * 2.2)
            ring.setColorAt(0, QColor(ac[0], ac[1], ac[2], int(50 * self.orb_accent_alpha)))
            ring.setColorAt(0.5, QColor(ac[0], ac[1], ac[2], int(20 * self.orb_accent_alpha)))
            ring.setColorAt(1, QColor(0,0,0,0))
            p.setPen(Qt.NoPen)
            p.setBrush(ring)
            p.drawEllipse(QRectF(cx - R*2.2, cy - R*2.2, R*4.4, R*4.4))

        # Aura (modulated by breathing pulse in idle)
        breath_mod = 1.0
        if self.state == 'idle':
            breath_mod = 0.6 + 0.4 * (0.5 + 0.5 * math.sin(self.breath_phase))
        aura_alpha = int(45 * breath_mod)
        aura = QRadialGradient(cx, cy, R * 2.6)
        aura.setColorAt(0, QColor(c1[0], c1[1], c1[2], aura_alpha))
        aura.setColorAt(1, QColor(0, 0, 0, 0))
        p.setBrush(aura); p.setPen(Qt.NoPen)
        aura_scale = 1.0 + 0.08 * math.sin(self.breath_phase) if self.state == 'idle' else 1.0
        aura_r = R * 2.6 * aura_scale
        p.drawEllipse(QRectF(cx-aura_r, cy-aura_r, aura_r*2, aura_r*2))

        # Fluid blobs
        for i in range(3):
            a = t + i * 2.094
            ox = math.cos(a) * deform
            oy = math.sin(a) * deform
            br = R + math.sin(t * 2 + i) * deform * 0.5
            c  = c1 if i % 2 == 0 else c2
            g  = QRadialGradient(cx+ox, cy+oy, br*1.1)
            g.setColorAt(0, QColor(c[0], c[1], c[2], 210))
            g.setColorAt(0.6, QColor(c[0], c[1], c[2], 60))
            g.setColorAt(1, QColor(c[0], c[1], c[2], 0))
            p.setBrush(g)
            p.drawEllipse(QRectF(cx+ox-br*1.1, cy+oy-br*1.1, br*2.2, br*2.2))

        # Eyes
        ey  = cy - R * 0.12
        eo  = R * 0.42
        er  = R * 0.14
        
        for side in (-1, 1):
            ex = cx + side * eo + self.pupil_x * 0.5
            
            if self.blink > 0.8:
                p.setPen(QPen(QColor(255, 255, 255, 235), 2.5, Qt.SolidLine, Qt.RoundCap))
                p.setBrush(Qt.NoBrush)
                p.drawLine(QPointF(ex - er, ey), QPointF(ex + er, ey))
            else:
                if emotion == 'happy':
                    path = QPainterPath()
                    path.moveTo(ex - er, ey + er*0.2)
                    path.quadTo(ex, ey - er*1.2, ex + er, ey + er*0.2)
                    p.setPen(QPen(QColor(255, 255, 255, 235), 2.0, Qt.SolidLine, Qt.RoundCap))
                    p.setBrush(Qt.NoBrush)
                    p.drawPath(path)
                elif emotion == 'sad':
                    outer_y = ey + er * 0.4
                    inner_y = ey - er * 0.4
                    path = QPainterPath()
                    if side == -1:
                        path.moveTo(ex - er, outer_y)
                        path.quadTo(ex, ey - er, ex + er, inner_y)
                    else:
                        path.moveTo(ex - er, inner_y)
                        path.quadTo(ex, ey - er, ex + er, outer_y)
                    p.setPen(QPen(QColor(255, 255, 255, 235), 2.0, Qt.SolidLine, Qt.RoundCap))
                    p.setBrush(Qt.NoBrush)
                    p.drawPath(path)
                elif emotion == 'thinking':
                    eh = max(0.5, er * 0.8 * (1 - self.blink))
                    p.setBrush(QColor(255, 255, 255, 235))
                    p.setPen(Qt.NoPen)
                    p.drawEllipse(QRectF(ex - er, ey - eh/2, er*2, eh))
                else:
                    eh = max(0.5, er * 2 * (1 - self.blink))
                    p.setBrush(QColor(255, 255, 255, 235))
                    p.setPen(Qt.NoPen)
                    p.drawEllipse(QRectF(ex - er, ey - eh/2, er*2, eh))

        # Mouth
        my = cy + R * 0.35
        mw = R * 0.32
        mh = R * 0.38 * self.mouth
        if self.mouth > 0.04:
            p.setBrush(QColor(255, 255, 255, 235))
            p.setPen(Qt.NoPen)
            p.drawEllipse(QRectF(cx - mw, my - mh/2, mw*2, max(1.5, mh)))
        else:
            p.setPen(QPen(QColor(255, 255, 255, 155), 1.5, Qt.SolidLine, Qt.RoundCap))
            p.setBrush(Qt.NoBrush)
            if emotion == 'happy':
                m_path = QPainterPath()
                m_path.moveTo(cx - mw*0.6, my)
                m_path.quadTo(cx, my + mw*0.6, cx + mw*0.6, my)
                p.drawPath(m_path)
            elif emotion == 'sad':
                m_path = QPainterPath()
                m_path.moveTo(cx - mw*0.6, my + mw*0.3)
                m_path.quadTo(cx, my - mw*0.3, cx + mw*0.6, my + mw*0.3)
                p.drawPath(m_path)
            else:
                p.drawLine(int(cx - mw*0.6), int(my), int(cx + mw*0.6), int(my))
            p.setPen(Qt.NoPen)

        # Listening: mic level ring
        if self.state == 'listening' and self.mic_level > 0.05:
            lv = self.mic_level
            ring_r = R + 2 + lv * 6
            pen_col = QColor(50, 215, 75, int(180 * lv))
            p.setPen(QPen(pen_col, 1.5))
            p.setBrush(Qt.NoBrush)
            p.drawEllipse(QRectF(cx - ring_r, cy - ring_r, ring_r*2, ring_r*2))
            p.setPen(Qt.NoPen)

        # Mute badge on orb
        if getattr(self, 'mic_muted', False):
            badge_r = 6
            badge_x = cx + R * 0.7
            badge_y = cy - R * 0.7
            # Red circle badge
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(255, 59, 48, 230))
            p.drawEllipse(QRectF(badge_x - badge_r, badge_y - badge_r, badge_r * 2, badge_r * 2))
            # Slash line
            p.setPen(QPen(QColor(255, 255, 255, 240), 1.8, Qt.SolidLine, Qt.RoundCap))
            p.drawLine(QPointF(badge_x - 3, badge_y + 3), QPointF(badge_x + 3, badge_y - 3))
            p.setPen(Qt.NoPen)

        # State transition ripple
        if self.ripple_alpha > 0.01:
            rr = self.ripple_radius
            rc = self.ripple_color
            ripple_pen = QPen(QColor(rc[0], rc[1], rc[2], int(180 * self.ripple_alpha)), 2.0)
            p.setPen(ripple_pen)
            p.setBrush(Qt.NoBrush)
            p.drawEllipse(QRectF(cx - rr, cy - rr, rr * 2, rr * 2))
            # Secondary fainter ring
            if rr > 10:
                rr2 = rr * 0.65
                ripple_pen2 = QPen(QColor(rc[0], rc[1], rc[2], int(80 * self.ripple_alpha)), 1.2)
                p.setPen(ripple_pen2)
                p.drawEllipse(QRectF(cx - rr2, cy - rr2, rr2 * 2, rr2 * 2))
            p.setPen(Qt.NoPen)

        # Thinking particles (Phase 4: orbiting dots with trails)
        for pt in self.particles:
            if pt['alpha'] < 0.02:
                continue
            px = cx + math.cos(pt['angle']) * pt['radius']
            py = cy + math.sin(pt['angle']) * pt['radius']
            pa = int(200 * pt['alpha'])
            ps = pt['size'] * pt['alpha']

            # Draw trail (afterglow)
            trail = list(pt.get('trail', []))
            for ti, (tx_t, ty_t) in enumerate(trail):
                trail_frac = (ti + 1) / (len(trail) + 1)
                trail_alpha = int(pa * trail_frac * 0.35)
                trail_size = ps * trail_frac * 0.6
                if trail_alpha > 2 and trail_size > 0.3:
                    tg = QRadialGradient(tx_t, ty_t, trail_size * 2)
                    tg.setColorAt(0, QColor(255, 180, 50, trail_alpha))
                    tg.setColorAt(1, QColor(255, 100, 0, 0))
                    p.setBrush(tg)
                    p.setPen(Qt.NoPen)
                    p.drawEllipse(QRectF(tx_t - trail_size*2, ty_t - trail_size*2, trail_size*4, trail_size*4))

            # Main particle
            pg = QRadialGradient(px, py, ps * 2)
            pg.setColorAt(0, QColor(255, 180, 50, pa))
            pg.setColorAt(0.5, QColor(255, 140, 30, int(pa * 0.5)))
            pg.setColorAt(1, QColor(255, 100, 0, 0))
            p.setBrush(pg)
            p.setPen(Qt.NoPen)
            p.drawEllipse(QRectF(px - ps*2, py - ps*2, ps*4, ps*4))

        # Spark particles (Phase 4: shooting sparks)
        for sp in self.sparks:
            if sp['alpha'] < 0.02:
                continue
            sc = sp['color']
            sa = int(255 * sp['alpha'])
            ss = sp['size'] * sp['alpha']
            sg = QRadialGradient(sp['x'], sp['y'], ss * 2.5)
            sg.setColorAt(0, QColor(sc[0], sc[1], sc[2], sa))
            sg.setColorAt(0.6, QColor(sc[0], sc[1], sc[2], int(sa * 0.3)))
            sg.setColorAt(1, QColor(sc[0], sc[1], sc[2], 0))
            p.setBrush(sg)
            p.setPen(Qt.NoPen)
            p.drawEllipse(QRectF(sp['x'] - ss*2.5, sp['y'] - ss*2.5, ss*5, ss*5))

    # ─────────────────────────────────────────────
    #  Compact
    # ─────────────────────────────────────────────
    def _draw_compact(self, p, tx, w, h):
        font = QFont("Segoe UI", 11, QFont.DemiBold)
        font.setLetterSpacing(QFont.AbsoluteSpacing, 0.2)
        p.setFont(font)

        if self.state == 'idle':
            label = self._get_carousel_text()
            col = QColor(230, 230, 240, 210)
        elif self.state == 'speaking':
            label = "Speaking..."
            col = QColor(255, 255, 255, 225)
        elif self.state == 'listening':
            label = "Listening..."
            col = QColor(180, 255, 200, 210)
        elif self.state == 'thinking':
            # Show tool name + elapsed timer
            tool_label = self.tool_name[:18] if self.tool_name else "Processing"
            elapsed = time.time() - self.progress_start if self.progress_start else 0
            if elapsed > 0.5:
                label = f"{tool_label} · {elapsed:.0f}s"
            else:
                label = f"{tool_label}..."
            col = QColor(255, 210, 130, 225)
        elif self.state == 'input':
            label = ""
            col = QColor(0, 0, 0, 0)
        else:
            label = "JARVIS"
            col = QColor(200, 200, 215, 185)

        # ── Smooth text cross-fade ──
        if label != self.current_label:
            self.prev_label = self.current_label
            self.prev_label_alpha = self.label_alpha  # carry over current alpha
            self.current_label = label
            self.label_alpha = 0.0  # start fading in

        text_rect = QRectF(tx, 0, w - tx - 52, h)

        # Draw fading-out previous label
        if self.prev_label and self.prev_label_alpha > 0.01:
            prev_col = QColor(col)
            prev_col.setAlpha(int(prev_col.alpha() * self.prev_label_alpha * 0.6))
            p.setPen(prev_col)
            p.drawText(text_rect, Qt.AlignLeft | Qt.AlignVCenter, self.prev_label)

        # Draw fading-in current label
        if col.alpha() > 0:
            cur_col = QColor(col)
            cur_col.setAlpha(int(col.alpha() * self.label_alpha))
            p.setPen(cur_col)
            p.drawText(text_rect, Qt.AlignLeft | Qt.AlignVCenter, label)

        # Draw right side indicator / stats
        if self.state == 'idle':
            # System stats micro-bars
            bar_x = w - 50
            bar_w = 28
            bar_h = 3
            gap = 6
            cpu_y = h/2 - gap/2 - bar_h
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(255, 255, 255, 15))
            p.drawRoundedRect(QRectF(bar_x, cpu_y, bar_w, bar_h), 1.5, 1.5)
            cpu_fill = bar_w * min(self.cpu_percent / 100.0, 1.0)
            cpu_col = QColor(50, 215, 75) if self.cpu_percent < 60 else QColor(255, 180, 50) if self.cpu_percent < 85 else QColor(255, 59, 48)
            cpu_col.setAlpha(180)
            p.setBrush(cpu_col)
            if cpu_fill > 0: p.drawRoundedRect(QRectF(bar_x, cpu_y, max(2, cpu_fill), bar_h), 1.5, 1.5)
            
            ram_y = h/2 + gap/2
            p.setBrush(QColor(255, 255, 255, 15))
            p.drawRoundedRect(QRectF(bar_x, ram_y, bar_w, bar_h), 1.5, 1.5)
            ram_fill = bar_w * min(self.ram_percent / 100.0, 1.0)
            p.setBrush(QColor(0, 122, 255, 180))
            if ram_fill > 0: p.drawRoundedRect(QRectF(bar_x, ram_y, max(2, ram_fill), bar_h), 1.5, 1.5)
            
            if getattr(self, 'mic_muted', False):
                p.setFont(QFont("Segoe UI Emoji", 10))
                p.setPen(QColor(255, 69, 58, 220))
                p.drawText(QRectF(bar_x - 20, 0, 18, h), Qt.AlignCenter, "🔇")
            elif self.source:
                p.setFont(QFont("Segoe UI Emoji", 10))
                p.setPen(QColor(180, 180, 195, 120))
                p.drawText(QRectF(bar_x - 20, 0, 18, h), Qt.AlignCenter, "📱" if self.source == 'telegram' else "🎤")
        else:
            indicator_x = w - 50
            
            # If muted, shift the visualizers to the left and draw the mute icon on the far right
            if getattr(self, 'mic_muted', False):
                p.setFont(QFont("Segoe UI Emoji", 12))
                p.setPen(QColor(255, 69, 58, 220))
                p.drawText(QRectF(indicator_x, 0, 36, h), Qt.AlignCenter, "🔇")
                indicator_x -= 30  # shift visualizers

            if self.state == 'speaking':
                self._draw_waveform(p, indicator_x, h/2, 36, h * 0.34)
            elif self.state == 'listening':
                self._draw_mic_bars(p, indicator_x, h/2, 36, h * 0.30)
            elif self.state == 'thinking':
                self._draw_spinner(p, indicator_x + 22, h/2, 9)

    # ─────────────────────────────────────────────
    #  Expanded
    # ─────────────────────────────────────────────
    def _draw_expanded(self, p, tx, w, h):
        cat   = self.tool_cat.upper() if self.tool_cat else ''
        style = CATEGORY_STYLE.get(cat, DEFAULT_STYLE)
        accent = QColor(*style['color'])
        top_y  = 10

        # ── Accent stripe ──
        p.setPen(Qt.NoPen)
        stripe = QPainterPath()
        stripe.addRoundedRect(QRectF(tx, 4, 28, 3), 1.5, 1.5)
        p.fillPath(stripe, accent)

        # ── Category label ──
        font_sm = QFont("Segoe UI", 8, QFont.Medium)
        font_sm.setLetterSpacing(QFont.AbsoluteSpacing, 1.6)
        p.setFont(font_sm)
        if self.context == 'tool' and self.tool_cat:
            p.setPen(accent)
            header_text = f"{style['icon']}  {style['label'].upper()}"
        elif self.context == 'response':
            p.setPen(QColor(0, 212, 255, 210))
            header_text = "✦  JARVIS RESPONSE"
        else:
            p.setPen(QColor(200, 200, 210, 150))
            header_text = "◆  JARVIS"
        p.drawText(QRectF(tx, top_y, w - tx - 50, 18), Qt.AlignLeft | Qt.AlignVCenter, header_text)

        # ── State badge (right) ──
        self._draw_state_badge(p, w - 52, top_y, 44, 18)

        # ── Title ──
        font_title = QFont("Segoe UI", 13, QFont.Bold)
        p.setFont(font_title)
        p.setPen(QColor(255, 255, 255, 245))
        if self.context == 'tool' and self.tool_name:
            title = self.tool_name.replace('_', ' ').title()
        elif self.context == 'response':
            title = "Response"
        else:
            title = self.state.title()
        p.drawText(QRectF(tx, top_y + 20, w - tx - 20, 24), Qt.AlignLeft | Qt.AlignVCenter, title)

        # ── Body ──
        body_text = ''
        if self.context == 'tool' and self.tool_desc:
            body_text = self.tool_desc
        elif self.context == 'response' and self.last_response:
            body_text = self.last_response[:130]
            if len(self.last_response) > 130: body_text += '...'

        if cat == 'MEDIA' and body_text:
            self._draw_media_card(p, tx, top_y + 46, w, h, body_text, accent)
        elif cat == 'WEATHER' and body_text:
            self._draw_weather_card(p, tx, top_y + 46, w, h, body_text, accent)
        elif cat == 'SYSTEM' and body_text:
            self._draw_system_card(p, tx, top_y + 46, w, h, body_text, accent)
        elif cat == 'FINANCE' and body_text:
            self._draw_finance_card(p, tx, top_y + 46, w, h, body_text, accent)
        else:
            if body_text:
                font_body = QFont("Segoe UI", 10)
                p.setFont(font_body)
                p.setPen(QColor(195, 195, 210, 185))
                
                body_rect = QRectF(tx, top_y + 48, w - tx - 20, 55)
                # Calculate full text height
                fm = QFontMetrics(font_body)
                bounding_rect = fm.boundingRect(QRectF(0, 0, body_rect.width(), 10000), Qt.AlignLeft | Qt.TextWordWrap, body_text)
                self.max_response_scroll = max(0.0, bounding_rect.height() - body_rect.height())
                
                # Clip and draw
                p.setClipRect(body_rect)
                p.drawText(QRectF(tx, top_y + 48 - self.response_scroll, body_rect.width(), bounding_rect.height()), Qt.AlignLeft | Qt.TextWordWrap, body_text)
                p.setClipping(False)
                
                # Draw scrollbar if needed
                if self.max_response_scroll > 0:
                    sb_h = max(10, body_rect.height() * (body_rect.height() / bounding_rect.height()))
                    sb_y = body_rect.top() + (self.response_scroll / self.max_response_scroll) * (body_rect.height() - sb_h)
                    sb_path = QPainterPath()
                    sb_path.addRoundedRect(QRectF(w - 14, sb_y, 4, sb_h), 2, 2)
                    p.fillPath(sb_path, QColor(255, 255, 255, 40))

            # Progress bar / Segmented Progress / Quick Actions
            if self.context == 'tool' and self.progress > 0:
                if self.steps_total > 1:
                    self._draw_segmented_progress(p, tx, h - 38, w - tx - 18, accent)
                else:
                    self._draw_progress(p, tx, h - 30, w - tx - 18, accent)
            else:
                self._draw_quick_actions(p, tx, w, h)

        # ── Right side indicator ──
        indicator_x = w - 44
        if getattr(self, 'mic_muted', False):
            p.setFont(QFont("Segoe UI Emoji", 12))
            p.setPen(QColor(255, 69, 58, 220))
            p.drawText(QRectF(indicator_x - 10, 14, 36, 28), Qt.AlignCenter, "🔇")
            indicator_x -= 30

        if self.state == 'speaking':
            self._draw_waveform(p, indicator_x, 28, 28, 14)
        elif self.state == 'thinking':
            self._draw_spinner(p, indicator_x + 20, 28, 8)
        elif self.state == 'listening':
            self._draw_mic_bars(p, indicator_x, 28, 28, 12)

    # ─────────────────────────────────────────────
    #  History Drawer
    # ─────────────────────────────────────────────
    def _draw_history(self, p, tx, w, h):
        font_hdr = QFont("Segoe UI", 8, QFont.Medium)
        font_hdr.setLetterSpacing(QFont.AbsoluteSpacing, 1.6)
        p.setFont(font_hdr)
        p.setPen(QColor(0, 212, 255, 180))
        p.drawText(QRectF(tx, 8, w - tx - 20, 18), Qt.AlignLeft | Qt.AlignVCenter, "◫  RECENT ACTIVITY")

        # Divider
        p.setPen(QPen(QColor(255,255,255,18), 1))
        p.drawLine(int(tx), 28, int(w - 12), 28)
        p.setPen(Qt.NoPen)

        items = list(self.history)
        if not items:
            p.setPen(QColor(150,150,160,120))
            p.setFont(QFont("Segoe UI", 10))
            p.drawText(QRectF(tx, 35, w - tx - 20, 40), Qt.AlignLeft | Qt.AlignVCenter, "No activity yet")
            return

        row_h = 42.0
        for i, item in enumerate(items[:6]):
            y = 32 + i * row_h
            if y + row_h > h - 10: break

            cat = item.cat.upper() if item.cat else ''
            style = CATEGORY_STYLE.get(cat, DEFAULT_STYLE)
            ac = QColor(*style['color'])

            # Row hover bg
            is_hover = self.mouse_pos and QRectF(tx - 2, y, w - tx - 10, row_h - 2).contains(self.mouse_pos)
            row_bg = QPainterPath()
            row_bg.addRoundedRect(QRectF(tx - 2, y, w - tx - 10, row_h - 2), 5, 5)
            bg_alpha = 15 if is_hover else (6 if i % 2 == 0 else 0)
            p.fillPath(row_bg, QColor(255,255,255, bg_alpha))

            # Icon dot
            if getattr(item, 'status', 'success') == 'error':
                p.setBrush(QColor(255, 69, 58, 200))
            else:
                p.setBrush(QColor(ac.red(), ac.green(), ac.blue(), 200))
            p.drawEllipse(QRectF(tx, y + 8, 7, 7))

            # Tool name
            name_font = QFont("Segoe UI", 10, QFont.DemiBold)
            p.setFont(name_font)
            p.setPen(QColor(230, 230, 240, 210))
            name = item.tool_name.replace('_', ' ').title()
            p.drawText(QRectF(tx + 13, y + 2, w * 0.55, 18), Qt.AlignLeft | Qt.AlignVCenter, name[:22])

            # Description
            desc_font = QFont("Segoe UI", 8)
            p.setFont(desc_font)
            p.setPen(QColor(160, 160, 175, 140))
            desc_str = item.desc.replace('\n', ' ') if item.desc else "Executed"
            p.drawText(QRectF(tx + 13, y + 20, w * 0.7, 16), Qt.AlignLeft | Qt.AlignVCenter, desc_str[:40] + ("..." if len(desc_str) > 40 else ""))

            # Time ago
            age  = time.time() - item.ts
            t_str = f"{int(age)}s" if age < 60 else f"{int(age/60)}m"
            time_font = QFont("Segoe UI", 8)
            p.setFont(time_font)
            p.setPen(QColor(160, 160, 175, 140))
            p.drawText(QRectF(w - 38, y + 2, 30, 18), Qt.AlignRight | Qt.AlignVCenter, t_str)

        # Footer hint
        p.setFont(QFont("Segoe UI", 8))
        p.setPen(QColor(120, 120, 135, 100))
        p.drawText(QRectF(tx, h - 18, w - tx - 10, 16), Qt.AlignCenter, "double-click to close")

    # ─────────────────────────────────────────────
    #  Media Card
    # ─────────────────────────────────────────────
    def _draw_media_card(self, p, tx, y0, w, h, body_text, accent):
        art_size = 68
        art_rect = QRectF(tx, y0, art_size, art_size)

        if self.album_art:
            path = QPainterPath()
            path.addRoundedRect(art_rect, 8, 8)
            p.setClipPath(path)
            p.drawImage(art_rect, self.album_art)
            p.setClipping(False)
        else:
            p.setPen(Qt.NoPen)
            art_bg = QPainterPath()
            art_bg.addRoundedRect(art_rect, 8, 8)
            g = QLinearGradient(art_rect.left(), art_rect.top(), art_rect.right(), art_rect.bottom())
            g.setColorAt(0, QColor(40, 40, 50, 200))
            g.setColorAt(1, QColor(25, 25, 35, 200))
            p.fillPath(art_bg, g)
            # Music note
            p.setFont(QFont("Segoe UI Emoji", 20))
            p.setPen(QColor(255,255,255,80))
            p.drawText(art_rect, Qt.AlignCenter, "♫")
            p.setPen(Qt.NoPen)

        # Track info
        info_x = tx + art_size + 12
        if '\nBy ' in body_text:
            lines = body_text.split('\nBy ', 1)
        elif ' - ' in body_text:
            lines = body_text.split(' - ', 1)
        else:
            lines = [body_text, '']
        track  = lines[0][:28]
        artist = lines[1][:28] if len(lines) > 1 else ''

        font_track = QFont("Segoe UI", 11, QFont.Bold)
        p.setFont(font_track); p.setPen(QColor(255,255,255,240))
        p.drawText(QRectF(info_x, y0 + 4, w - info_x - 12, 22), Qt.AlignLeft | Qt.AlignVCenter, track)

        if artist:
            font_art = QFont("Segoe UI", 9)
            p.setFont(font_art); p.setPen(QColor(200,200,215,160))
            p.drawText(QRectF(info_x, y0 + 26, w - info_x - 12, 18), Qt.AlignLeft | Qt.AlignVCenter, artist)

        # Mini waveform (equalizer bars)
        eq_y = y0 + 48
        n = 12
        bar_w = 3; gap = 2
        total = n * (bar_w + gap)
        eq_x = info_x
        p.setPen(Qt.NoPen)
        for i in range(n):
            bar_h2 = (math.sin(self.frame * 0.15 + i * 0.8) * 0.5 + 0.5) * 10 + 3
            bx = eq_x + i * (bar_w + gap)
            bar = QPainterPath()
            bar.addRoundedRect(QRectF(bx, eq_y - bar_h2/2, bar_w, bar_h2), 1.5, 1.5)
            alpha = int(180 + 50 * math.sin(self.frame * 0.1 + i * 0.5))
            p.fillPath(bar, QColor(accent.red(), accent.green(), accent.blue(), alpha))

        # Control buttons
        ctrl_y = h - 36
        cx = info_x + (w - 12 - info_x) / 2
        btn_start_x = cx - 54

        self.btn_prev_rect = QRectF(btn_start_x, ctrl_y + 2, 28, 26)
        self.btn_play_rect = QRectF(btn_start_x + 36, ctrl_y - 2, 36, 32)
        self.btn_stop_rect = QRectF(btn_start_x + 80, ctrl_y + 2, 28, 26)

        # Scrubber
        scrub_y = ctrl_y - 12
        scrub_w = w - info_x - 12
        p.setPen(Qt.NoPen)
        sc_path = QPainterPath()
        sc_path.addRoundedRect(QRectF(info_x, scrub_y, scrub_w, 4), 2, 2)
        p.fillPath(sc_path, QColor(255,255,255,20))
        
        prog_w = scrub_w * ((self.frame % 3600) / 3600.0) # Indeterminate animated scrubber
        sc_fill = QPainterPath()
        sc_fill.addRoundedRect(QRectF(info_x, scrub_y, prog_w, 4), 2, 2)
        p.fillPath(sc_fill, accent)

        for btn_r, lbl, sz in [
            (self.btn_prev_rect, "⏮", 14),
            (self.btn_play_rect, "⏯", 18),
            (self.btn_stop_rect, "⏹", 14),
        ]:
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(255,255,255,12))
            btn_path = QPainterPath()
            btn_path.addRoundedRect(btn_r, 6, 6)
            
            is_hover = self.mouse_pos and btn_r.contains(self.mouse_pos)
            if is_hover:
                p.fillPath(btn_path, QColor(255,255,255,30))
                
                # Tooltip
                tt_text = {"⏮": "Previous", "⏯": "Play/Pause", "⏹": "Stop"}[lbl]
                p.setFont(QFont("Segoe UI", 8))
                fm = QFontMetrics(p.font())
                tw = fm.horizontalAdvance(tt_text) + 12
                tx_tt = btn_r.center().x() - tw/2
                ty_tt = btn_r.top() - 24
                
                tt_path = QPainterPath()
                tt_path.addRoundedRect(QRectF(tx_tt, ty_tt, tw, 18), 4, 4)
                p.fillPath(tt_path, QColor(20,20,24,230))
                p.setPen(QColor(200,200,210))
                p.drawText(QRectF(tx_tt, ty_tt, tw, 18), Qt.AlignCenter, tt_text)
                p.setPen(Qt.NoPen)
            else:
                p.fillPath(btn_path, QColor(255,255,255,12))
                
            p.setFont(QFont("Segoe UI Emoji", sz))
            p.setPen(QColor(255,255,255,225))
            p.drawText(btn_r, Qt.AlignCenter, lbl)
            p.setPen(Qt.NoPen)

    # ─────────────────────────────────────────────
    #  State Badge
    # ─────────────────────────────────────────────
    def _draw_state_badge(self, p, x, y, bw, bh):
        if self.state == 'thinking':
            col = QColor(255, 180, 50, 200)
            text = "Thinking"
        elif self.state == 'speaking':
            col = QColor(0, 212, 255, 200)
            text = "Speaking"
        elif self.state == 'listening':
            if getattr(self, 'mic_muted', False):
                col = QColor(255, 69, 58, 200)
                text = "Muted"
            else:
                col = QColor(50, 215, 75, 200)
                text = "Listening"
        else:
            return

        p.setPen(Qt.NoPen)
        badge = QPainterPath()
        badge.addRoundedRect(QRectF(x, y, bw, bh), bh/2, bh/2)
        bg_col = QColor(col.red(), col.green(), col.blue(), 28)
        p.fillPath(badge, bg_col)
        p.setPen(QPen(col, 0.8))
        p.drawPath(badge)

        font_b = QFont("Segoe UI", 7, QFont.Medium)
        p.setFont(font_b)
        p.setPen(col)
        p.drawText(QRectF(x, y, bw, bh), Qt.AlignCenter, text)
        p.setPen(Qt.NoPen)

    # ─────────────────────────────────────────────
    #  Progress Bar
    # ─────────────────────────────────────────────
    def _draw_progress(self, p, bx, by, bw, accent):
        bh = 3
        p.setPen(Qt.NoPen)
        track = QPainterPath()
        track.addRoundedRect(QRectF(bx, by, bw, bh), 1.5, 1.5)
        p.fillPath(track, QColor(255,255,255,18))

        fw = bw * min(self.progress, 1.0)
        fill = QPainterPath()
        fill.addRoundedRect(QRectF(bx, by, fw, bh), 1.5, 1.5)
        fg = QLinearGradient(bx, 0, bx+fw, 0)
        fg.setColorAt(0, accent)
        fg.setColorAt(1, QColor(accent.red(), accent.green(), accent.blue(), 160))
        p.fillPath(fill, fg)

        # Moving shimmer on bar
        sx = bx + (self.frame * 2.5) % (fw + 40) - 20
        shim = QRadialGradient(sx, by + bh/2, 18)
        shim.setColorAt(0, QColor(255,255,255,55))
        shim.setColorAt(1, QColor(0,0,0,0))
        p.fillPath(fill, shim)

        # Elapsed label
        elapsed = time.time() - self.progress_start if self.progress_start else 0
        t_str = f"{elapsed:.0f}s"
        p.setFont(QFont("Segoe UI", 8))
        p.setPen(QColor(200,200,200,100))
        p.drawText(QRectF(bx, by + 5, bw, 14), Qt.AlignRight, t_str)

    # ─────────────────────────────────────────────
    #  Segmented Progress (Phase 4: Multi-Step)
    # ─────────────────────────────────────────────
    def _draw_segmented_progress(self, p, bx, by, bw, accent):
        """Draw a segmented progress bar for multi-step tool execution."""
        n = max(1, self.steps_total)
        gap = 4
        seg_w = (bw - gap * (n - 1)) / n
        bh = 4
        p.setPen(Qt.NoPen)

        for i in range(n):
            sx = bx + i * (seg_w + gap)
            seg_path = QPainterPath()
            seg_path.addRoundedRect(QRectF(sx, by, seg_w, bh), 2, 2)

            if i < self.step_current - 1:
                # Completed segment — full accent fill
                p.fillPath(seg_path, accent)
            elif i == self.step_current - 1:
                # Current segment — pulsing animation
                pulse = 0.6 + 0.4 * abs(math.sin(self.frame * 0.08))
                pulse_color = QColor(accent.red(), accent.green(), accent.blue(), int(255 * pulse))
                p.fillPath(seg_path, pulse_color)
                # Shimmer on active segment
                shimmer_x = sx + (self.frame * 1.8) % (seg_w + 30) - 15
                shim = QRadialGradient(shimmer_x, by + bh / 2, 12)
                shim.setColorAt(0, QColor(255, 255, 255, int(60 * pulse)))
                shim.setColorAt(1, QColor(0, 0, 0, 0))
                p.fillPath(seg_path, shim)
            else:
                # Future segment — dim track
                p.fillPath(seg_path, QColor(255, 255, 255, 18))

        # Step label below
        label = f"Step {self.step_current}/{self.steps_total}"
        if self.step_name:
            label += f" · {self.step_name}"
        p.setFont(QFont("Segoe UI", 8))
        p.setPen(QColor(200, 200, 210, 150))
        p.drawText(QRectF(bx, by + 7, bw * 0.7, 16), Qt.AlignLeft | Qt.AlignVCenter, label)

        # Elapsed timer on right
        elapsed = time.time() - self.progress_start if self.progress_start else 0
        p.setPen(QColor(200, 200, 200, 100))
        p.drawText(QRectF(bx, by + 7, bw, 16), Qt.AlignRight, f"{elapsed:.0f}s")

    # ─────────────────────────────────────────────
    #  Quick Actions Bar (Phase 4)
    # ─────────────────────────────────────────────
    def _draw_quick_actions(self, p, tx, w, h):
        """Draw 5 sleek quick action buttons at the bottom of expanded view."""
        btn_count = len(self.quick_action_buttons)
        btn_size = 28
        btn_gap = 14
        total_w = btn_count * btn_size + (btn_count - 1) * btn_gap
        start_x = tx + (w - tx - 20 - total_w) / 2
        btn_y = h - 38

        # Subtle separator line
        p.setPen(QPen(QColor(255, 255, 255, 12), 0.5))
        p.drawLine(int(tx), int(btn_y - 8), int(w - 18), int(btn_y - 8))
        p.setPen(Qt.NoPen)

        self.qa_hover_index = -1
        for i, btn in enumerate(self.quick_action_buttons):
            bx = start_x + i * (btn_size + btn_gap)
            br = QRectF(bx, btn_y, btn_size, btn_size)
            btn['rect'] = br

            is_hover = self.mouse_pos and br.contains(QPointF(self.mouse_pos))
            if is_hover:
                self.qa_hover_index = i

            # Button background
            btn_path = QPainterPath()
            btn_path.addRoundedRect(br, btn_size / 2, btn_size / 2)

            if is_hover:
                # Hovered — brighter with accent glow
                p.fillPath(btn_path, QColor(255, 255, 255, 35))
                # Accent ring
                ring_pen = QPen(QColor(0, 212, 255, 100), 1.2)
                p.setPen(ring_pen)
                p.setBrush(Qt.NoBrush)
                p.drawPath(btn_path)
                p.setPen(Qt.NoPen)
            else:
                p.fillPath(btn_path, QColor(255, 255, 255, 12))

            # Special button states (mute & pin)
            icon = btn['icon']
            if btn['action'] == 'mute' and getattr(self, 'mic_muted', False):
                icon = '🔇'
                p.fillPath(btn_path, QColor(255, 59, 48, 30))
            elif btn['action'] == 'pin' and getattr(self, 'pinned', False):
                icon = '📍'
                p.fillPath(btn_path, QColor(0, 212, 255, 30))

            # Icon
            p.setFont(QFont("Segoe UI Emoji", 11))
            p.setPen(QColor(220, 220, 230, 220 if is_hover else 160))
            p.drawText(br, Qt.AlignCenter, icon)
            p.setPen(Qt.NoPen)

            # Tooltip on hover
            if is_hover:
                label = btn['label']
                if btn['action'] == 'mute' and getattr(self, 'mic_muted', False):
                    label = 'Unmute Mic'
                elif btn['action'] == 'pin' and getattr(self, 'pinned', False):
                    label = 'Unpin HUD'
                tt_font = QFont("Segoe UI", 8)
                p.setFont(tt_font)
                fm = QFontMetrics(tt_font)
                tt_w = fm.horizontalAdvance(label) + 14
                tt_x = br.center().x() - tt_w / 2
                tt_y = br.top() - 24

                tt_path = QPainterPath()
                tt_path.addRoundedRect(QRectF(tt_x, tt_y, tt_w, 18), 5, 5)
                p.fillPath(tt_path, QColor(10, 10, 14, 240))
                # Border
                p.setPen(QPen(QColor(255, 255, 255, 25), 0.5))
                p.drawPath(tt_path)
                p.setPen(QColor(215, 215, 225, 230))
                p.drawText(QRectF(tt_x, tt_y, tt_w, 18), Qt.AlignCenter, label)
                p.setPen(Qt.NoPen)

    # ─────────────────────────────────────────────
    #  Toasts
    # ─────────────────────────────────────────────
    def _draw_toasts(self, p, w, total_h):
        base_y = total_h + 8
        toast_w = min(w, 340)
        toast_h = 52
        tx_off = (w - toast_w) / 2
        for i, toast in enumerate(self.toasts):
            y = base_y + i * (toast_h + 6) + toast.offset_y
            alpha = int(toast.alpha * 255)
            # Background
            t_path = QPainterPath()
            t_path.addRoundedRect(QRectF(tx_off, y, toast_w, toast_h), 12, 12)
            bg_c = QColor(22, 22, 28, int(230 * toast.alpha))
            p.setPen(Qt.NoPen)
            p.fillPath(t_path, bg_c)
            # Border
            bc = QColor(*toast.color)
            bc.setAlpha(int(80 * toast.alpha))
            p.setPen(QPen(bc, 0.8))
            p.drawPath(t_path)
            p.setPen(Qt.NoPen)

            # Icon dot
            dot_col = QColor(*toast.color)
            dot_col.setAlpha(alpha)
            p.setBrush(dot_col)
            p.drawEllipse(QRectF(tx_off + 14, y + 14, 8, 8))

            # Title
            p.setFont(QFont("Segoe UI", 10, QFont.DemiBold))
            tc = QColor(240, 240, 250, alpha)
            p.setPen(tc)
            
            # Action Button
            if toast.action_label:
                # Draw button
                btn_w = 60
                btn_h = 24
                btn_x = tx_off + toast_w - btn_w - 10
                btn_y = y + (toast_h - btn_h) / 2
                br = QRectF(btn_x, btn_y, btn_w, btn_h)
                toast.action_rect = br
                
                is_hover = self.mouse_pos and br.contains(self.mouse_pos)
                
                btn_path = QPainterPath()
                btn_path.addRoundedRect(br, 4, 4)
                
                if is_hover:
                    p.fillPath(btn_path, QColor(255, 255, 255, int(45 * toast.alpha)))
                else:
                    p.fillPath(btn_path, QColor(255, 255, 255, int(20 * toast.alpha)))
                
                # Button label
                p.setFont(QFont("Segoe UI", 8, QFont.Medium))
                p.setPen(QColor(230, 230, 240, int(255 * toast.alpha)))
                p.drawText(br, Qt.AlignCenter, toast.action_label)
                
                text_max_w = toast_w - 40 - btn_w - 10
            else:
                toast.action_rect = QRectF()
                text_max_w = toast_w - 40

            # Title text
            p.setFont(QFont("Segoe UI", 10, QFont.DemiBold))
            p.setPen(tc)
            p.drawText(QRectF(tx_off + 28, y + 6, text_max_w, 20), Qt.AlignLeft | Qt.AlignVCenter, toast.title)

            # Body
            p.setFont(QFont("Segoe UI", 8))
            p.setPen(QColor(180, 180, 195, int(160 * toast.alpha)))
            p.drawText(QRectF(tx_off + 28, y + 26, text_max_w, 18), Qt.AlignLeft | Qt.AlignVCenter, toast.body[:55])
            p.setPen(Qt.NoPen)

    # ─────────────────────────────────────────────
    #  Micro-Visualizations
    # ─────────────────────────────────────────────
    def _draw_waveform(self, p, x, cy, w, amp):
        p.setPen(Qt.NoPen)
        n = 6; spacing = w / n
        c1, _ = self._state_colors()

        # Phase 4: Reactive radial back-glow when AI is speaking
        if self.ai_level > 0.1:
            glow_r = 20 + 15 * self.ai_level
            glow_cx = x + w / 2
            glow_alpha = int(50 * self.ai_level)
            glow = QRadialGradient(glow_cx, cy, glow_r)
            glow.setColorAt(0, QColor(c1[0], c1[1], c1[2], glow_alpha))
            glow.setColorAt(0.6, QColor(c1[0], c1[1], c1[2], int(glow_alpha * 0.3)))
            glow.setColorAt(1, QColor(0, 0, 0, 0))
            p.setBrush(glow)
            p.drawEllipse(QRectF(glow_cx - glow_r, cy - glow_r, glow_r * 2, glow_r * 2))
            p.setBrush(Qt.NoBrush)

        # Phase 4: Frequency-band analyzer with bass/mid/treble modulation
        freq_weights = [1.2, 0.9, 1.1, 0.7, 1.0, 0.85]  # bass → treble profile
        for i in range(n):
            base_h = amp * 0.1
            freq_mod = freq_weights[i] * (0.8 + 0.5 * abs(math.sin(self.frame * 0.3 + i * 1.2)))
            lv_h   = amp * self.ai_level * freq_mod
            bh = base_h + lv_h + 3
            bx = x + i * spacing
            bar = QPainterPath()
            bar.addRoundedRect(QRectF(bx, cy - bh/2, 3, bh), 1.5, 1.5)
            a = min(255, int(150 + 105 * self.ai_level))
            p.fillPath(bar, QColor(c1[0], c1[1], c1[2], a))

    def _draw_mic_bars(self, p, x, cy, w, amp):
        """Microphone level bars — height driven by mic_level."""
        p.setPen(Qt.NoPen)
        n = 6; spacing = w / n
        for i in range(n):
            base_h = amp * 0.3
            lv_h   = amp * self.mic_level * (0.5 + 0.5 * abs(math.sin(self.frame*0.2 + i)))
            bh = base_h + lv_h + 2
            bx = x + i * spacing
            bar = QPainterPath()
            bar.addRoundedRect(QRectF(bx, cy - bh/2, 3, bh), 1.5, 1.5)
            a = int(140 + 100 * self.mic_level)
            p.fillPath(bar, QColor(50, 215, 75, a))

    def _draw_spinner(self, p, cx, cy, r):
        gradient = QConicalGradient(cx, cy, self.frame * -5 % 360)
        gradient.setColorAt(0.0, QColor(255, 180, 50, 220))
        gradient.setColorAt(0.8, QColor(255, 180, 50, 40))
        gradient.setColorAt(1.0, QColor(255, 180, 50, 0))
        pen = QPen(QBrush(gradient), 2.2, Qt.SolidLine, Qt.RoundCap)
        p.setPen(pen)
        start = int(self.frame * 7) % 360
        p.drawArc(QRectF(cx-r, cy-r, r*2, r*2), start*16, 200*16)
        p.setPen(Qt.NoPen)

    # ─────────────────────────────────────────────
    #  Helpers
    # ─────────────────────────────────────────────
    def _state_colors(self):
        if self.state == 'speaking':
            return (0, 212, 255), (130, 60, 220)
        elif self.state == 'listening':
            return (50, 215, 75), (0, 190, 140)
        elif self.state == 'thinking':
            cat = self.tool_cat.upper() if self.tool_cat else ''
            style = CATEGORY_STYLE.get(cat, DEFAULT_STYLE)
            c = style['color']
            return c, (c[0]//2, c[1]//2, c[2]//2)
        else:
            return (80, 130, 180), (40, 80, 120)


# ══════════════════════════════════════════════════════════
#  Native Microphone / LiveKit Client
# ══════════════════════════════════════════════════════════
def start_livekit_client(island_instance):
    import threading
    import asyncio
    
    def run_asyncio_loop():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(livekit_client_task(island_instance))
    
    t = threading.Thread(target=run_asyncio_loop, daemon=True)
    t.start()

async def livekit_client_task(island_instance):
    import asyncio
    try:
        from livekit import rtc, api
        import pyaudio
    except ImportError:
        print("Missing livekit or pyaudio packages. Native mic disabled.")
        return
        
    import os
    from dotenv import load_dotenv
    load_dotenv()
    
    api_key = os.getenv("LIVEKIT_API_KEY")
    api_secret = os.getenv("LIVEKIT_API_SECRET")
    livekit_url = os.getenv("LIVEKIT_URL")
    
    if not (api_key and api_secret and livekit_url):
        print("Missing LiveKit config. Cannot start native mic client.")
        return
        
    room = rtc.Room()
    
    token = api.AccessToken(api_key, api_secret)
    token.with_identity("jarvis-hud-client").with_name("Desktop HUD").with_grants(api.VideoGrants(
        room_join=True,
        room=os.getenv("LIVEKIT_ROOM_NAME", "jarvis-room"),
    ))
    jwt_token = token.to_jwt()
    
    try:
        await room.connect(livekit_url, jwt_token)
        print("HUD Native Mic Connected to LiveKit room!")
    except Exception as e:
        print(f"HUD connection failed: {e}")
        return
        
    @room.on("track_subscribed")
    def on_track_subscribed(track, publication, participant):
        if track.kind == rtc.TrackKind.KIND_AUDIO:
            print("Subscribed to agent audio track!")
            audio_stream = rtc.AudioStream(track)
            asyncio.create_task(play_incoming_audio(audio_stream))

    async def play_incoming_audio(audio_stream):
        p = pyaudio.PyAudio()
        stream = None
        try:
            async for event in audio_stream:
                # In livekit-api < 0.10, the iterator yields an AudioFrameEvent which has a .frame property.
                # In newer versions it might yield AudioFrame directly. Let's handle both.
                frame = getattr(event, 'frame', event)
                if stream is None:
                    stream = p.open(format=pyaudio.paInt16,
                                    channels=frame.num_channels,
                                    rate=frame.sample_rate,
                                    output=True)
                try:
                    raw_data = bytes(frame.data)
                    stream.write(raw_data)
                    
                    # Calculate real-time RMS for AI speaker visualization
                    import struct, math
                    count = len(raw_data) // 2
                    if count > 0:
                        shorts = struct.unpack(f"<{count}h", raw_data)
                        rms = math.sqrt(sum(s*s for s in shorts) / count)
                        island_instance.target_ai_level = min(1.0, rms / 15000.0)
                except Exception as e:
                    print("Error playing audio frame:", e)
        except Exception as e:
            print("Audio playback task error:", e)
        finally:
            if stream:
                stream.stop_stream()
                stream.close()
            p.terminate()
    
    audio_source = rtc.AudioSource(sample_rate=16000, num_channels=1)
    track = rtc.LocalAudioTrack.create_audio_track("microphone", audio_source)
    options = rtc.TrackPublishOptions()
    options.source = rtc.TrackSource.SOURCE_MICROPHONE
    await room.local_participant.publish_track(track, options)
    
    loop = asyncio.get_running_loop()
    
    def capture_mic():
        p = pyaudio.PyAudio()
        try:
            stream = p.open(format=pyaudio.paInt16,
                            channels=1,
                            rate=16000,
                            input=True,
                            frames_per_buffer=160)
            print("PyAudio stream started for HUD.")
        except Exception as e:
            print(f"Failed to open PyAudio stream: {e}")
            return
            
        while True:
            try:
                data = stream.read(160, exception_on_overflow=False)
                if getattr(island_instance, 'mic_muted', False):
                    data = b'\x00' * len(data)
                    island_instance.target_mic_level = 0.0
                else:
                    import struct, math
                    count = len(data) // 2
                    if count > 0:
                        shorts = struct.unpack(f"<{count}h", data)
                        rms = math.sqrt(sum(s*s for s in shorts) / count)
                        island_instance.target_mic_level = min(1.0, rms / 8000.0)
                        
                frame = rtc.AudioFrame(data=data, sample_rate=16000, num_channels=1, samples_per_channel=160)
                asyncio.run_coroutine_threadsafe(audio_source.capture_frame(frame), loop)
            except Exception:
                pass

    import threading
    threading.Thread(target=capture_mic, daemon=True).start()
    
    while True:
        await asyncio.sleep(1)

# ══════════════════════════════════════════════════════════
#  Entry
# ══════════════════════════════════════════════════════════
def main():
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    island = PremiumDynamicIsland()
    start_livekit_client(island)
    island.show()
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()
