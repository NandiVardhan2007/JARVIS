import 'dart:async';
import 'dart:convert';
import 'dart:math' as math;

import 'package:flutter/foundation.dart';
import 'package:web_socket_channel/web_socket_channel.dart';
import 'package:web_socket_channel/status.dart' as ws_status;

import '../models/jarvis_state.dart';

/// Owns the live link to the JARVIS backend (via the Python `jarvis_bridge.py`
/// WebSocket) and exposes a single [snapshot] that the whole UI renders from.
///
/// When [demoMode] is on (or the socket is down), a built-in driver animates a
/// believable JARVIS so the face, mouth, weather and player all come alive with
/// no backend running.
class JarvisConnection extends ChangeNotifier {
  JarvisConnection({this.url = 'ws://127.0.0.1:8765'});

  String url;
  JarvisSnapshot snapshot = const JarvisSnapshot();

  bool _demo = true;
  bool get demoMode => _demo;
  bool get connected => snapshot.connected;

  WebSocketChannel? _channel;
  StreamSubscription? _sub;
  Timer? _reconnectTimer;
  Timer? _demoTimer;
  int _reconnectAttempts = 0;

  void start() {
    _connect();
    _startDemo(); // demo runs until a real socket takes over
  }

  // ── WebSocket ───────────────────────────────────────────────────────────
  void _connect() {
    _reconnectTimer?.cancel();
    try {
      final ch = WebSocketChannel.connect(Uri.parse(url));
      _channel = ch;
      _sub = ch.stream.listen(
        _onData,
        onError: (_) => _scheduleReconnect(),
        onDone: _scheduleReconnect,
        cancelOnError: true,
      );
    } catch (_) {
      _scheduleReconnect();
    }
  }

  void _onData(dynamic data) {
    _reconnectAttempts = 0;
    if (_demo) _stopDemo();
    try {
      final decoded = jsonDecode(data as String);
      if (decoded is Map<String, dynamic>) {
        _apply(snapshot.merge(decoded).copyWith(connected: true));
      }
    } catch (_) {
      // Ignore malformed frames.
    }
  }

  void _scheduleReconnect() {
    _sub?.cancel();
    _sub = null;
    _channel = null;
    if (snapshot.connected) {
      _apply(snapshot.copyWith(connected: false));
    }
    if (!_demo) _startDemo(); // fall back to demo while offline
    _reconnectAttempts = math.min(_reconnectAttempts + 1, 6);
    final delay = Duration(seconds: math.min(1 << _reconnectAttempts, 15));
    _reconnectTimer = Timer(delay, _connect);
  }

  // ── Outbound commands ─────────────────────────────────────────────────
  void _send(Map<String, dynamic> msg) {
    final ch = _channel;
    if (ch != null) {
      try {
        ch.sink.add(jsonEncode(msg));
      } catch (_) {}
    }
  }

  void sendText(String text) {
    final t = text.trim();
    if (t.isEmpty) return;
    _send({'type': 'text_input', 'text': t});
    if (_demo) {
      // Echo into the demo so it feels responsive offline.
      _demoInject(t);
    }
  }

  void sendMedia(String cmd) => _send({'type': 'media', 'cmd': cmd});

  void screenshot() => _send({'type': 'action', 'action': 'screenshot'});

  void toggleMute() {
    _send({'type': 'mute'});
    if (_demo) _apply(snapshot.copyWith(micMuted: !snapshot.micMuted));
  }

  // ── Demo mode ─────────────────────────────────────────────────────────
  void setDemo(bool on) {
    if (on) {
      _startDemo();
    } else {
      _stopDemo();
      // Show "connecting" until the socket delivers a frame.
      _apply(snapshot.copyWith(connected: false));
    }
  }

  void _startDemo() {
    if (_demoTimer != null) return;
    _demo = true;
    _demoClock = 0;
    _demoTimer = Timer.periodic(const Duration(milliseconds: 16), _demoTick);
  }

  void _stopDemo() {
    _demo = false;
    _demoTimer?.cancel();
    _demoTimer = null;
  }

  // Scripted timeline (seconds): idle → listening → thinking → speaking → …
  double _demoClock = 0;
  final _rng = math.Random();
  String? _injected;
  double _injectedAt = -100;

  void _demoInject(String text) {
    _injected = text;
    _injectedAt = _demoClock;
  }

  void _demoTick(Timer _) {
    _demoClock += 0.016;
    final t = _demoClock;
    // 16-second loop.
    final phase = t % 16.0;

    AssistantState state;
    double ai = 0, mic = 0;
    String transcript = snapshot.transcript;
    String response = snapshot.response;
    String category = '';
    String desc = '';

    if (_injected != null && (t - _injectedAt) < 6) {
      // Respond to a typed command: think then speak.
      final dt = t - _injectedAt;
      transcript = _injected!;
      if (dt < 1.5) {
        state = AssistantState.thinking;
        category = 'AI';
        desc = 'Understanding your request';
      } else {
        state = AssistantState.speaking;
        ai = _voice(t);
        response = 'Sure — working on “$_injected” right now.';
      }
    } else if (phase < 3.5) {
      state = AssistantState.idle;
    } else if (phase < 6.5) {
      state = AssistantState.listening;
      mic = (0.35 + 0.45 * (0.5 + 0.5 * math.sin(t * 7)) +
              _rng.nextDouble() * 0.15)
          .clamp(0.0, 1.0);
      transcript = "What's the weather and play some music";
    } else if (phase < 9) {
      state = AssistantState.thinking;
      category = 'WEATHER';
      desc = 'Checking the forecast';
    } else {
      state = AssistantState.speaking;
      ai = _voice(t);
      response = "It's clear and pleasant. Now playing your mix.";
      category = 'MEDIA';
    }

    var snap = snapshot.copyWith(
      state: state,
      aiLevel: ai,
      micLevel: mic,
      transcript: transcript,
      response: response,
      category: category.isEmpty ? null : category,
      description: desc,
      connected: false,
    );

    // Demo now-playing appears once we hit the media phase.
    if (phase >= 9 || category == 'MEDIA') {
      snap = snap.copyWith(
        nowPlaying: const NowPlaying(
          title: 'Neon Skyline',
          artist: 'The Arc Reactors',
          imageUrl: null,
          playing: true,
        ),
      );
    }

    _apply(snap);
  }

  double _voice(double t) {
    // Layered sines → natural speech envelope, gated by pseudo-syllables.
    final env = 0.5 + 0.5 * math.sin(t * 3.1);
    final syl = (math.sin(t * 17) * 0.5 + 0.5);
    return (0.15 + 0.85 * env * syl).clamp(0.0, 1.0);
  }

  // ── plumbing ──────────────────────────────────────────────────────────
  void _apply(JarvisSnapshot s) {
    snapshot = s;
    notifyListeners();
  }

  @override
  void dispose() {
    _reconnectTimer?.cancel();
    _demoTimer?.cancel();
    _sub?.cancel();
    _channel?.sink.close(ws_status.normalClosure);
    super.dispose();
  }
}
