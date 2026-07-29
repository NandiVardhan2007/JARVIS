import 'dart:math' as math;
import 'package:flutter/material.dart';
import 'package:flutter/scheduler.dart';
import 'theme.dart';

/// Auth state broadcast by the VISION Python backend via WebSocket.
enum AuthState {
  locked,     // Initial — waiting for master to speak
  listening,  // Recording audio
  verifying,  // Analysing voice print
  success,    // Match confirmed
  failed,     // Mismatch, retrying
  lockout,    // All attempts exhausted
}

AuthState authStateFromString(String? s) {
  switch ((s ?? '').toLowerCase()) {
    case 'auth_listening': return AuthState.listening;
    case 'auth_verifying': return AuthState.verifying;
    case 'auth_success':   return AuthState.success;
    case 'auth_failed':    return AuthState.failed;
    case 'auth_lockout':   return AuthState.lockout;
    default:               return AuthState.locked;
  }
}

/// Full-screen animated authentication lock screen shown before the main UI.
/// Listens to the same state string that `send_hud_state` broadcasts from Python.
class VisionAuthScreen extends StatefulWidget {
  /// Called when the backend confirms auth_success.
  final VoidCallback onAuthenticated;

  /// Current state string from the WebSocket (e.g. "auth_locked").
  final String stateString;

  /// Description line from the backend.
  final String description;

  const VisionAuthScreen({
    super.key,
    required this.onAuthenticated,
    required this.stateString,
    this.description = '',
  });

  @override
  State<VisionAuthScreen> createState() => _VisionAuthScreenState();
}

class _VisionAuthScreenState extends State<VisionAuthScreen>
    with TickerProviderStateMixin {
  late final Ticker _ticker;
  double _t = 0, _lastElapsed = 0;

  // Ripple rings for listening state
  final List<_Ring> _rings = [];
  double _nextRing = 0.0;

  // Success flash
  double _successAlpha = 0;
  bool _successTriggered = false;

  @override
  void initState() {
    super.initState();
    _ticker = createTicker(_onTick)..start();
  }

  @override
  void didUpdateWidget(VisionAuthScreen old) {
    super.didUpdateWidget(old);
    final auth = authStateFromString(widget.stateString);
    if (auth == AuthState.success && !_successTriggered) {
      _successTriggered = true;
      _doSuccessAndDismiss();
    }
  }

  void _doSuccessAndDismiss() async {
    // Let the success animation play for 1.8 s then hand off
    for (int i = 0; i < 18; i++) {
      await Future.delayed(const Duration(milliseconds: 100));
      if (mounted) setState(() => _successAlpha = math.sin(i / 18 * math.pi));
    }
    await Future.delayed(const Duration(milliseconds: 400));
    widget.onAuthenticated();
  }

  void _onTick(Duration elapsed) {
    final now = elapsed.inMicroseconds / 1e6;
    var dt = now - _lastElapsed;
    _lastElapsed = now;
    if (dt <= 0 || dt > 0.05) dt = 0.016;
    if (mounted) setState(() => _t += dt);

    final auth = authStateFromString(widget.stateString);
    if (auth == AuthState.listening || auth == AuthState.verifying) {
      _nextRing -= dt;
      if (_nextRing <= 0) {
        _rings.add(_Ring(t: _t));
        _nextRing = 0.55;
      }
    }
    _rings.removeWhere((r) => _t - r.born > 2.2);
  }

  @override
  void dispose() {
    _ticker.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final auth = authStateFromString(widget.stateString);
    final size = MediaQuery.of(context).size;

    return Scaffold(
      backgroundColor: const Color(0xFF020509),
      body: Stack(
        children: [
          // ── Hex grid bg ──────────────────────────────────────────────────
          CustomPaint(
            painter: _HexBgPainter(t: _t),
            size: size,
          ),

          // ── Ripple rings (listening / verifying) ─────────────────────────
          CustomPaint(
            painter: _RingsPainter(rings: _rings, t: _t, auth: auth),
            size: size,
          ),

          // ── Success flash overlay ─────────────────────────────────────────
          if (_successAlpha > 0.01)
            Opacity(
              opacity: (_successAlpha * 0.35).clamp(0, 1),
              child: Container(color: const Color(0xFF00D4FF)),
            ),

          // ── Corner HUD decorators ─────────────────────────────────────────
          ..._corners(size),

          // ── Central lock UI ───────────────────────────────────────────────
          Center(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                // Lock icon + state ring
                SizedBox(
                  width: 180, height: 180,
                  child: CustomPaint(
                    painter: _LockOrb(t: _t, auth: auth),
                  ),
                ),

                const SizedBox(height: 32),

                // VISION label
                Text(
                  'J.A.R.V.I.S',
                  style: TextStyle(
                    color: _stateColor(auth),
                    fontSize: 36,
                    fontWeight: FontWeight.w900,
                    letterSpacing: 12,
                    shadows: [
                      Shadow(color: _stateColor(auth).withAlpha(160), blurRadius: 24),
                    ],
                  ),
                ),

                const SizedBox(height: 10),

                // State label
                AnimatedSwitcher(
                  duration: const Duration(milliseconds: 350),
                  child: Text(
                    _stateLabel(auth),
                    key: ValueKey(auth),
                    style: TextStyle(
                      color: _stateColor(auth).withAlpha(200),
                      fontSize: 12,
                      letterSpacing: 3.5,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                ),

                const SizedBox(height: 16),

                // Description line from Python backend
                if (widget.description.isNotEmpty)
                  AnimatedSwitcher(
                    duration: const Duration(milliseconds: 300),
                    child: Text(
                      widget.description.toUpperCase(),
                      key: ValueKey(widget.description),
                      style: const TextStyle(
                        color: Color(0x80AFC2E0),
                        fontSize: 10,
                        letterSpacing: 2,
                        fontFamily: 'Courier New',
                      ),
                    ),
                  ),

                const SizedBox(height: 40),

                // Mic waveform bar — pulses during listening
                if (auth == AuthState.listening || auth == AuthState.verifying)
                  SizedBox(
                    width: 200, height: 36,
                    child: CustomPaint(
                      painter: _WaveformPainter(t: _t, auth: auth),
                    ),
                  ),
              ],
            ),
          ),

          // ── Bottom tagline ────────────────────────────────────────────────
          Positioned(
            bottom: 32,
            left: 0, right: 0,
            child: Center(
              child: Text(
                'VOICE BIOMETRIC SECURITY  ·  AUTHORIZED PERSONNEL ONLY',
                style: TextStyle(
                  color: const Color(0xFF00D4FF).withAlpha(60),
                  fontSize: 8,
                  letterSpacing: 2.5,
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }

  Color _stateColor(AuthState auth) {
    switch (auth) {
      case AuthState.locked:    return const Color(0xFF5082B4);
      case AuthState.listening: return const Color(0xFF32D74B);
      case AuthState.verifying: return const Color(0xFF00D4FF);
      case AuthState.success:   return const Color(0xFF32D74B);
      case AuthState.failed:    return const Color(0xFFFF9F0A);
      case AuthState.lockout:   return const Color(0xFFFF453A);
    }
  }

  String _stateLabel(AuthState auth) {
    switch (auth) {
      case AuthState.locked:    return 'VOICE LOCK ACTIVE';
      case AuthState.listening: return 'SPEAK NOW — LISTENING';
      case AuthState.verifying: return 'ANALYSING VOICE PRINT';
      case AuthState.success:   return 'IDENTITY CONFIRMED';
      case AuthState.failed:    return 'VOICE NOT RECOGNISED';
      case AuthState.lockout:   return 'SYSTEM LOCKOUT';
    }
  }

  List<Widget> _corners(Size size) {
    const s = 70.0;
    return [
      Positioned(top: 20, left: 20,
        child: CustomPaint(painter: _CornerPainter(t: _t), size: const Size(s, s))),
      Positioned(top: 20, right: 20,
        child: Transform.flip(flipX: true,
          child: CustomPaint(painter: _CornerPainter(t: _t), size: const Size(s, s)))),
      Positioned(bottom: 20, left: 20,
        child: Transform.flip(flipY: true,
          child: CustomPaint(painter: _CornerPainter(t: _t), size: const Size(s, s)))),
      Positioned(bottom: 20, right: 20,
        child: Transform.flip(flipX: true, flipY: true,
          child: CustomPaint(painter: _CornerPainter(t: _t), size: const Size(s, s)))),
    ];
  }
}

// ── Lock orb painter ──────────────────────────────────────────────────────────
class _LockOrb extends CustomPainter {
  final double t;
  final AuthState auth;
  _LockOrb({required this.t, required this.auth});

  @override
  void paint(Canvas canvas, Size size) {
    final cx = size.width / 2;
    final cy = size.height / 2;

    // Determine color
    final Color col;
    switch (auth) {
      case AuthState.listening: col = const Color(0xFF32D74B); break;
      case AuthState.verifying: col = const Color(0xFF00D4FF); break;
      case AuthState.success:   col = const Color(0xFF32D74B); break;
      case AuthState.failed:    col = const Color(0xFFFF9F0A); break;
      case AuthState.lockout:   col = const Color(0xFFFF453A); break;
      default:                  col = const Color(0xFF5082B4);
    }

    // Rotating ring
    final rRot = t * (auth == AuthState.verifying ? 2.2 : 0.7);
    canvas.save();
    canvas.translate(cx, cy);
    canvas.rotate(rRot);

    final ringPaint = Paint()
      ..color = col.withAlpha(180)
      ..strokeWidth = 2.0
      ..style = PaintingStyle.stroke
      ..maskFilter = const MaskFilter.blur(BlurStyle.outer, 5);

    // Draw dashed ring
    const dashes = 12;
    const r = 72.0;
    const dashLen = (2 * math.pi * r) / (dashes * 2);

    for (int i = 0; i < dashes; i++) {
      final start = (i * 2) * dashLen / r;
      canvas.drawArc(
        Rect.fromCircle(center: Offset.zero, radius: r),
        start, dashLen / r, false, ringPaint,
      );
    }
    canvas.restore();

    // Core glow
    final pulse = 0.80 + 0.20 * math.sin(t * (auth == AuthState.listening ? 5.0 : 2.0));
    for (final (rad, alpha) in [(42.0, 0.10), (28.0, 0.22), (16.0, 0.50), (8.0, 0.95)]) {
      canvas.drawCircle(
        Offset(cx, cy),
        rad * pulse,
        Paint()
          ..color = col.withAlpha((alpha * 255).round())
          ..maskFilter = MaskFilter.blur(BlurStyle.normal, rad * 0.7),
      );
    }

    // Lock / unlock icon
    _drawIcon(canvas, Offset(cx, cy), auth, col);
  }

  void _drawIcon(Canvas canvas, Offset center, AuthState auth, Color col) {
    final paint = Paint()
      ..color = col
      ..strokeWidth = 2.5
      ..style = PaintingStyle.stroke
      ..strokeCap = StrokeCap.round;

    if (auth == AuthState.success) {
      // Checkmark
      final path = Path()
        ..moveTo(center.dx - 10, center.dy)
        ..lineTo(center.dx - 3, center.dy + 8)
        ..lineTo(center.dx + 12, center.dy - 9);
      canvas.drawPath(path, paint..color = col.withAlpha(230));
    } else if (auth == AuthState.lockout || auth == AuthState.failed) {
      // X mark
      canvas.drawLine(
        Offset(center.dx - 9, center.dy - 9),
        Offset(center.dx + 9, center.dy + 9),
        paint,
      );
      canvas.drawLine(
        Offset(center.dx + 9, center.dy - 9),
        Offset(center.dx - 9, center.dy + 9),
        paint,
      );
    } else {
      // Padlock body
      final rect = RRect.fromRectAndRadius(
        Rect.fromCenter(center: Offset(center.dx, center.dy + 5), width: 20, height: 16),
        const Radius.circular(3),
      );
      canvas.drawRRect(rect, paint..style = PaintingStyle.stroke);

      // Shackle (open slightly when listening)
      final shackleOpen = (auth == AuthState.listening || auth == AuthState.verifying) ? 4.0 : 0.0;
      final shacklePath = Path()
        ..moveTo(center.dx - 7, center.dy - 2 - shackleOpen)
        ..lineTo(center.dx - 7, center.dy - 10)
        ..arcToPoint(
          Offset(center.dx + 7, center.dy - 10),
          radius: const Radius.circular(7),
          clockwise: false,
        )
        ..lineTo(center.dx + 7, center.dy - 2);
      canvas.drawPath(shacklePath, paint);
    }
  }

  @override
  bool shouldRepaint(_LockOrb old) => old.t != t || old.auth != auth;
}

// ── Radial ripple rings ───────────────────────────────────────────────────────
class _Ring {
  final double born;
  _Ring({required double t}) : born = t;
}

class _RingsPainter extends CustomPainter {
  final List<_Ring> rings;
  final double t;
  final AuthState auth;
  _RingsPainter({required this.rings, required this.t, required this.auth});

  @override
  void paint(Canvas canvas, Size size) {
    final cx = size.width / 2;
    final cy = size.height / 2;
    final col = auth == AuthState.verifying
        ? const Color(0xFF00D4FF)
        : const Color(0xFF32D74B);

    for (final ring in rings) {
      final age = t - ring.born;
      final progress = (age / 2.2).clamp(0.0, 1.0);
      final radius = 90.0 + progress * 200.0;
      final alpha = ((1.0 - progress) * 60).round();
      canvas.drawCircle(
        Offset(cx, cy),
        radius,
        Paint()
          ..color = col.withAlpha(alpha)
          ..strokeWidth = 1.5
          ..style = PaintingStyle.stroke,
      );
    }
  }

  @override
  bool shouldRepaint(_RingsPainter old) => old.t != t;
}

// ── Animated waveform bar ─────────────────────────────────────────────────────
class _WaveformPainter extends CustomPainter {
  final double t;
  final AuthState auth;
  _WaveformPainter({required this.t, required this.auth});

  @override
  void paint(Canvas canvas, Size size) {
    const bars = 28;
    final barW = size.width / bars;
    final col = auth == AuthState.verifying
        ? const Color(0xFF00D4FF)
        : const Color(0xFF32D74B);

    for (int i = 0; i < bars; i++) {
      final phase = t * 8 + i * 0.45;
      final h = (0.15 + 0.85 * math.pow((math.sin(phase) + 1) / 2, 1.5)) * size.height;
      final x = i * barW + barW * 0.2;
      final rect = Rect.fromCenter(
        center: Offset(x, size.height / 2),
        width: barW * 0.55,
        height: h,
      );
      canvas.drawRRect(
        RRect.fromRectAndRadius(rect, const Radius.circular(2)),
        Paint()
          ..color = col.withAlpha(180)
          ..maskFilter = const MaskFilter.blur(BlurStyle.normal, 1),
      );
    }
  }

  @override
  bool shouldRepaint(_WaveformPainter old) => old.t != t;
}

// ── Hex grid background ───────────────────────────────────────────────────────
class _HexBgPainter extends CustomPainter {
  final double t;
  _HexBgPainter({required this.t});

  @override
  void paint(Canvas canvas, Size size) {
    const hexR = 30.0;
    final cols = (size.width / (hexR * 1.73)).ceil() + 2;
    final rows = (size.height / (hexR * 1.5)).ceil() + 2;

    for (int row = -1; row < rows; row++) {
      for (int col = -1; col < cols; col++) {
        final ox = col * hexR * 1.73 + (row.isOdd ? hexR * 0.865 : 0);
        final oy = row * hexR * 1.5;
        final dist = math.sqrt(
          math.pow(ox - size.width / 2, 2) + math.pow(oy - size.height / 2, 2),
        );
        final wave = math.sin(t * 1.2 - dist * 0.011);
        final alpha = ((wave * 0.5 + 0.5) * 16).round();
        if (alpha < 2) continue;
        _drawHex(canvas, Offset(ox, oy), hexR * 0.94,
            Paint()
              ..color = const Color(0xFF00D4FF).withAlpha(alpha)
              ..strokeWidth = 0.6
              ..style = PaintingStyle.stroke);
      }
    }
  }

  void _drawHex(Canvas canvas, Offset c, double r, Paint p) {
    final path = Path();
    for (int i = 0; i < 6; i++) {
      final a = math.pi / 3 * i - math.pi / 6;
      final pt = Offset(c.dx + r * math.cos(a), c.dy + r * math.sin(a));
      i == 0 ? path.moveTo(pt.dx, pt.dy) : path.lineTo(pt.dx, pt.dy);
    }
    path.close();
    canvas.drawPath(path, p);
  }

  @override
  bool shouldRepaint(_HexBgPainter old) => old.t != t;
}

// ── Corner HUD ──────────────────────────────────────────────────────────────
class _CornerPainter extends CustomPainter {
  final double t;
  _CornerPainter({required this.t});

  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()
      ..color = const Color(0xFF00D4FF).withAlpha(80)
      ..strokeWidth = 1.2
      ..style = PaintingStyle.stroke;

    canvas.drawLine(Offset.zero, const Offset(36, 0), paint);
    canvas.drawLine(Offset.zero, const Offset(0, 36), paint);

    canvas.drawLine(const Offset(6, 0), const Offset(6, 6), paint..color = const Color(0xFF00D4FF).withAlpha(40));
    canvas.drawLine(const Offset(0, 6), const Offset(6, 6), paint);

    final tick = (t * 20) % 28.0;
    canvas.drawLine(
      Offset(tick, 0), Offset(tick + 5, 0),
      Paint()..color = VisionTheme.accent..strokeWidth = 2,
    );
  }

  @override
  bool shouldRepaint(_CornerPainter old) => old.t != t;
}
