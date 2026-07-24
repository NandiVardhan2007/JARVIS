import 'package:flutter/material.dart';

import 'config.dart';
import 'face/jarvis_face.dart';
import 'models/jarvis_state.dart';
import 'services/jarvis_connection.dart';
import 'theme.dart';
import 'splash_screen.dart';
import 'auth_screen.dart';
import 'widgets/music_player_card.dart';
import 'widgets/system_monitor_card.dart';
import 'widgets/transcription_panel.dart';
import 'widgets/weather_card.dart';
import 'widgets/camera_card.dart';
import 'widgets/agent_activity_card.dart';


void main() {
  runApp(const JarvisApp());
}

class JarvisApp extends StatelessWidget {
  const JarvisApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'JARVIS',
      debugShowCheckedModeBanner: false,
      theme: JarvisTheme.build(),
      home: const JarvisBootWrapper(),
    );
  }
}

class JarvisBootWrapper extends StatefulWidget {
  const JarvisBootWrapper({super.key});

  @override
  State<JarvisBootWrapper> createState() => _JarvisBootWrapperState();
}

class _JarvisBootWrapperState extends State<JarvisBootWrapper> {
  bool _booted = false;

  @override
  Widget build(BuildContext context) {
    return _booted
        ? const JarvisHome()
        : JarvisSplashScreen(onComplete: () => setState(() => _booted = true));
  }
}

class JarvisHome extends StatefulWidget {
  const JarvisHome({super.key});

  @override
  State<JarvisHome> createState() => _JarvisHomeState();
}

class _JarvisHomeState extends State<JarvisHome> {
  final JarvisConnection _conn = JarvisConnection(url: JarvisConfig.bridgeUrl);
  final TextEditingController _cmd = TextEditingController();
  final FocusNode _cmdFocus = FocusNode();

  @override
  void initState() {
    super.initState();
    _conn.start();
  }

  @override
  void dispose() {
    _conn.dispose();
    _cmd.dispose();
    _cmdFocus.dispose();
    super.dispose();
  }

  void _submit() {
    _conn.sendText(_cmd.text);
    _cmd.clear();
    _cmdFocus.requestFocus();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: AnimatedBuilder(
        animation: _conn,
        builder: (context, _) {
          final snap = _conn.snapshot;

          // Show the secure voice auth lock screen if JARVIS requests it
          if (snap.stateString.contains('auth_') && snap.stateString != 'auth_success') {
            return JarvisAuthScreen(
              stateString: snap.stateString,
              description: snap.description,
              onAuthenticated: () {}, // Handled by state string reverting to idle
            );
          }

          final glow = snap.colors.primary;
          return AnimatedContainer(
            duration: const Duration(milliseconds: 600),
            decoration: JarvisTheme.backgroundDecoration(glow),
            child: SafeArea(
              child: Column(
                children: [
                  _topBar(snap),
                  Expanded(
                    child: LayoutBuilder(
                      builder: (context, constraints) {
                        final width = constraints.maxWidth;
                        final height = constraints.maxHeight;

                        // Calculate dynamic JarvisFace size based on available viewport
                        final faceSize = (height * 0.42).clamp(220.0, 380.0);

                        if (width >= 1100) {
                          // ── 3-COLUMN DESKTOP / ULTRA-WIDE LAYOUT ─────────────
                          return Padding(
                            padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 8),
                            child: Row(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                // Left Panel: Monitor, Weather, Agent Activity
                                SizedBox(
                                  width: 320,
                                  child: SingleChildScrollView(
                                    physics: const BouncingScrollPhysics(),
                                    child: Column(
                                      children: [
                                        const SystemMonitorCard(),
                                        const SizedBox(height: 12),
                                        WeatherCard(city: JarvisConfig.weatherCity.isEmpty ? null : JarvisConfig.weatherCity),
                                        const SizedBox(height: 12),
                                        AgentActivityCard(snapshot: snap),
                                        const SizedBox(height: 12),
                                      ],
                                    ),
                                  ),
                                ),
                                // Center Panel: Jarvis Face & Live Speech Transcript
                                Expanded(
                                  child: Padding(
                                    padding: const EdgeInsets.symmetric(horizontal: 16),
                                    child: Center(
                                      child: SingleChildScrollView(
                                        physics: const BouncingScrollPhysics(),
                                        child: Column(
                                          mainAxisAlignment: MainAxisAlignment.center,
                                          children: [
                                            JarvisFace(
                                              snapshot: snap,
                                              size: faceSize,
                                            ),
                                            const SizedBox(height: 16),
                                            TranscriptionPanel(snapshot: snap),
                                          ],
                                        ),
                                      ),
                                    ),
                                  ),
                                ),
                                // Right Panel: Camera & Music Player
                                SizedBox(
                                  width: 320,
                                  child: SingleChildScrollView(
                                    physics: const BouncingScrollPhysics(),
                                    child: Column(
                                      children: [
                                        CameraCard(
                                          onStartWebcam: () => _conn.sendText('start webcam'),
                                          onStopWebcam: () => _conn.sendText('stop webcam'),
                                        ),
                                        const SizedBox(height: 12),
                                        _musicCard(snap),
                                        const SizedBox(height: 12),
                                      ],
                                    ),
                                  ),
                                ),
                              ],
                            ),
                          );
                        } else if (width >= 740) {
                          // ── 2-COLUMN TABLET / MEDIUM LAYOUT ───────────────────
                          return Padding(
                            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                            child: Row(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                // Main Left Column: Face, Transcript & Activity
                                Expanded(
                                  child: SingleChildScrollView(
                                    physics: const BouncingScrollPhysics(),
                                    child: Column(
                                      children: [
                                        JarvisFace(
                                          snapshot: snap,
                                          size: faceSize.clamp(200.0, 320.0),
                                        ),
                                        const SizedBox(height: 14),
                                        TranscriptionPanel(snapshot: snap),
                                        const SizedBox(height: 14),
                                        AgentActivityCard(snapshot: snap),
                                        const SizedBox(height: 12),
                                      ],
                                    ),
                                  ),
                                ),
                                const SizedBox(width: 14),
                                // Right Utility Column: Camera, System, Weather, Music
                                SizedBox(
                                  width: 310,
                                  child: SingleChildScrollView(
                                    physics: const BouncingScrollPhysics(),
                                    child: Column(
                                      children: [
                                        CameraCard(
                                          onStartWebcam: () => _conn.sendText('start webcam'),
                                          onStopWebcam: () => _conn.sendText('stop webcam'),
                                        ),
                                        const SizedBox(height: 12),
                                        const SystemMonitorCard(),
                                        const SizedBox(height: 12),
                                        WeatherCard(city: JarvisConfig.weatherCity.isEmpty ? null : JarvisConfig.weatherCity),
                                        const SizedBox(height: 12),
                                        _musicCard(snap),
                                        const SizedBox(height: 12),
                                      ],
                                    ),
                                  ),
                                ),
                              ],
                            ),
                          );
                        } else {
                          // ── 1-COLUMN COMPACT / MOBILE LAYOUT ─────────────────
                          return SingleChildScrollView(
                            physics: const BouncingScrollPhysics(),
                            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                            child: Column(
                              children: [
                                JarvisFace(
                                  snapshot: snap,
                                  size: 240,
                                ),
                                const SizedBox(height: 12),
                                TranscriptionPanel(snapshot: snap),
                                const SizedBox(height: 14),
                                AgentActivityCard(snapshot: snap),
                                const SizedBox(height: 14),
                                CameraCard(
                                  onStartWebcam: () => _conn.sendText('start webcam'),
                                  onStopWebcam: () => _conn.sendText('stop webcam'),
                                ),
                                const SizedBox(height: 14),
                                const SystemMonitorCard(),
                                const SizedBox(height: 14),
                                WeatherCard(city: JarvisConfig.weatherCity.isEmpty ? null : JarvisConfig.weatherCity),
                                const SizedBox(height: 14),
                                _musicCard(snap),
                                const SizedBox(height: 14),
                              ],
                            ),
                          );
                        }
                      },
                    ),
                  ),
                  _quickChips(),
                  const SizedBox(height: 6),
                  _commandBar(snap),
                ],
              ),
            ),
          );

        },
      ),
    );
  }

  Widget _musicCard(JarvisSnapshot snap) {
    // While JARVIS speaks the media is ducked; use its voice level otherwise
    // fall back to a gentle idle shimmer so the bars still move.
    final level = snap.nowPlaying?.playing == true
        ? (snap.state == AssistantState.speaking ? 0.25 : 0.7)
        : 0.0;
    return MusicPlayerCard(
      nowPlaying: snap.nowPlaying,
      level: level,
      onPlayPause: () => _conn.sendMedia('playpause'),
      onStop: () => _conn.sendMedia('stop'),
    );
  }

  Widget _topBar(JarvisSnapshot snap) {
    final live = snap.connected;
    return Padding(
      padding: const EdgeInsets.fromLTRB(24, 16, 24, 4),
      child: Row(
        children: [
          const Text(
            'J.A.R.V.I.S',
            style: TextStyle(
              color: JarvisTheme.textPrimary,
              fontSize: 18,
              fontWeight: FontWeight.w700,
              letterSpacing: 4,
            ),
          ),
          const SizedBox(width: 12),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
            decoration: BoxDecoration(
              color: (live ? const Color(0xFF32D74B) : const Color(0xFFFF9F0A))
                  .op(0.15),
              borderRadius: BorderRadius.circular(12),
            ),
            child: Text(
              live ? 'LIVE' : 'DEMO',
              style: TextStyle(
                color: live ? const Color(0xFF32D74B) : const Color(0xFFFF9F0A),
                fontSize: 10,
                fontWeight: FontWeight.w700,
                letterSpacing: 1.5,
              ),
            ),
          ),
          const Spacer(),
          _iconButton(
            icon: Icons.edit_note_rounded,
            tooltip: 'Open Text Editor',
            onTap: () => _conn.sendText('open text editor'),
          ),
          const SizedBox(width: 8),
          _iconButton(
            icon: Icons.screenshot_monitor_outlined,
            tooltip: 'Take Screenshot',
            onTap: _conn.screenshot,
          ),
          const SizedBox(width: 8),
          _iconButton(
            icon: _conn.demoMode ? Icons.play_circle_outline : Icons.science_outlined,
            tooltip: _conn.demoMode ? 'Demo mode on' : 'Try demo mode',
            active: _conn.demoMode,
            onTap: () => _conn.setDemo(!_conn.demoMode),
          ),
          const SizedBox(width: 8),
          _iconButton(
            icon: snap.micMuted ? Icons.mic_off_rounded : Icons.mic_rounded,
            tooltip: snap.micMuted ? 'Unmute mic' : 'Mute mic',
            active: !snap.micMuted,
            onTap: _conn.toggleMute,
          ),
        ],
      ),
    );
  }

  Widget _iconButton({
    required IconData icon,
    required VoidCallback onTap,
    String? tooltip,
    bool active = false,
  }) {
    final btn = GestureDetector(
      onTap: onTap,
      child: Container(
        width: 40,
        height: 40,
        decoration: BoxDecoration(
          shape: BoxShape.circle,
          color: active
              ? JarvisTheme.accent.op(0.18)
              : Colors.white.op(0.05),
          border: Border.all(
            color: active
                ? JarvisTheme.accent.op(0.5)
                : Colors.white.op(0.08),
          ),
        ),
        child: Icon(icon,
            size: 20,
            color: active ? JarvisTheme.accent : JarvisTheme.textDim),
      ),
    );
    return tooltip == null ? btn : Tooltip(message: tooltip, child: btn);
  }

  Widget _commandBar(JarvisSnapshot snap) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(24, 8, 24, 20),
      child: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 640),
          child: Container(
            decoration: BoxDecoration(
              color: Colors.white.op(0.04),
              borderRadius: BorderRadius.circular(28),
              border: Border.all(color: JarvisTheme.cardBorder),
            ),
            padding: const EdgeInsets.only(left: 20, right: 6),
            child: Row(
              children: [
                Expanded(
                  child: TextField(
                    controller: _cmd,
                    focusNode: _cmdFocus,
                    onSubmitted: (_) => _submit(),
                    style: const TextStyle(color: JarvisTheme.textPrimary),
                    cursorColor: JarvisTheme.accent,
                    decoration: const InputDecoration(
                      isDense: true,
                      border: InputBorder.none,
                      hintText: 'Type a command for JARVIS…',
                      hintStyle: TextStyle(color: JarvisTheme.textDim),
                    ),
                  ),
                ),
                Material(
                  color: Colors.transparent,
                  child: IconButton(
                    onPressed: _submit,
                    icon: const Icon(Icons.send_rounded, color: JarvisTheme.accent),
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  Widget _quickChips() {
    final chips = [
      ('🧠 Knowledge RAG', 'search the knowledge base'),
      ('📝 Text Editor', 'open text editor'),
      ('📸 Screenshot', 'take screenshot'),
      ('👁️ What\'s on screen?', 'what is on my screen'),
      ('💻 System Info', 'show system info'),
      ('☀️ Weather', 'what is the weather'),
    ];
    return SingleChildScrollView(
      scrollDirection: Axis.horizontal,
      child: Row(
        mainAxisAlignment: MainAxisAlignment.center,
        children: chips.map((c) {
          return Padding(
            padding: const EdgeInsets.symmetric(horizontal: 4),
            child: ActionChip(
              label: Text(c.$1, style: const TextStyle(fontSize: 11.5, color: JarvisTheme.textPrimary)),
              backgroundColor: Colors.white.op(0.04),
              side: const BorderSide(color: JarvisTheme.cardBorder),
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
              onPressed: () => _conn.sendText(c.$2),
            ),
          );
        }).toList(),
      ),
    );
  }
}
