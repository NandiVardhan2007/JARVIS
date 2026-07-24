import 'dart:math' as math;
import 'package:flutter/material.dart';
import 'package:flutter/scheduler.dart';
import 'theme.dart';

/// Enterprise-grade JARVIS boot splash screen with:
/// - HUD data rings rotating around a reactor core
/// - Hex grid particle background
/// - Animated text boot sequence (line by line)
/// - Glitch flicker on the JARVIS logo
/// - Auto-dismisses after ~4 seconds
class JarvisSplashScreen extends StatefulWidget {
  final VoidCallback onComplete;
  const JarvisSplashScreen({super.key, required this.onComplete});

  @override
  State<JarvisSplashScreen> createState() => _JarvisSplashScreenState();
}

class _JarvisSplashScreenState extends State<JarvisSplashScreen>
    with TickerProviderStateMixin {
  late final AnimationController _ctrl;
  late final Ticker _ticker;
  double _t = 0;
  double _lastElapsed = 0;

  // Boot lines revealed progressively
  final List<String> _bootLines = [
    'INITIALIZING CORE SYSTEMS...',
    'LOADING NEURAL PATHWAYS........OK',
    'VOICE SYNTHESIS ENGINE.......OK',
    'SPEAKER VERIFICATION MODULE..OK',
    'RAG KNOWLEDGE BASE...........OK',
    'DESKTOP CONTROL STACK........OK',
    'ALL SYSTEMS NOMINAL.',
    '',
    'WELCOME BACK, SIR.',
  ];
  int _visibleLines = 0;
  bool _dismissed = false;

  // Glitch state
  double _glitchAlpha = 0;
  bool _glitching = false;
  double _nextGlitch = 0.6;

  // Fade-out
  double _fadeOut = 1.0;

  @override
  void initState() {
    super.initState();
    _ctrl = AnimationController(vsync: this, duration: const Duration(seconds: 10))
      ..forward();

    // Reveal boot lines progressively
    Future.delayed(const Duration(milliseconds: 600), _revealLines);

    _ticker = createTicker(_onTick)..start();

    // Auto-dismiss at 4.2s
    Future.delayed(const Duration(milliseconds: 4200), _startDismiss);
  }

  void _revealLines() async {
    for (int i = 0; i < _bootLines.length; i++) {
      await Future.delayed(const Duration(milliseconds: 280));
      if (mounted) setState(() => _visibleLines = i + 1);
    }
  }

  void _startDismiss() async {
    if (_dismissed) return;
    _dismissed = true;
    // Fade out over 400ms
    const steps = 20;
    for (int i = 0; i < steps; i++) {
      await Future.delayed(const Duration(milliseconds: 20));
      if (mounted) setState(() => _fadeOut = 1.0 - ((i + 1) / steps));
    }
    widget.onComplete();
  }

  void _onTick(Duration elapsed) {
    final now = elapsed.inMicroseconds / 1e6;
    var dt = now - _lastElapsed;
    _lastElapsed = now;
    if (dt <= 0 || dt > 0.05) dt = 0.016;
    if (mounted) setState(() => _t += dt);

    // Glitch logic
    _nextGlitch -= dt;
    if (!_glitching && _nextGlitch <= 0) {
      _glitching = true;
      _glitchAlpha = 1.0;
      Future.delayed(const Duration(milliseconds: 80), () {
        if (mounted) setState(() { _glitching = false; _glitchAlpha = 0; });
        _nextGlitch = 1.2 + math.Random().nextDouble() * 2.0;
      });
    }
  }

  @override
  void dispose() {
    _ticker.dispose();
    _ctrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Opacity(
      opacity: _fadeOut.clamp(0.0, 1.0),
      child: Scaffold(
        backgroundColor: const Color(0xFF020509),
        body: Stack(
          children: [
            // Animated background
            CustomPaint(
              painter: _SplashBgPainter(t: _t),
              size: Size.infinite,
            ),
            // Central content
            Center(
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  // Reactor core + rings
                  SizedBox(
                    width: 220, height: 220,
                    child: CustomPaint(
                      painter: _ReactorPainter(t: _t),
                    ),
                  ),
                  const SizedBox(height: 32),
                  // Logo with glitch
                  Stack(
                    alignment: Alignment.center,
                    children: [
                      _logoText(color: JarvisTheme.accent),
                      if (_glitching)
                        Opacity(
                          opacity: _glitchAlpha * 0.6,
                          child: Transform.translate(
                            offset: Offset(3 * math.Random().nextDouble() - 1.5, 0),
                            child: _logoText(color: const Color(0xFFFF2D55)),
                          ),
                        ),
                    ],
                  ),
                  const SizedBox(height: 6),
                  const Text(
                    'JUST A RATHER VERY INTELLIGENT SYSTEM',
                    style: TextStyle(
                      color: Color(0x80AFC2E0),
                      fontSize: 9,
                      letterSpacing: 3.5,
                      fontWeight: FontWeight.w500,
                    ),
                  ),
                  const SizedBox(height: 48),
                  // Boot log terminal
                  SizedBox(
                    width: 360,
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: List.generate(_visibleLines, (i) {
                        final line = _bootLines[i];
                        final isLast = i == _bootLines.length - 1;
                        return Padding(
                          padding: const EdgeInsets.only(bottom: 3),
                          child: Text(
                            line,
                            style: TextStyle(
                              color: isLast
                                  ? JarvisTheme.accent
                                  : const Color(0x9900D4FF),
                              fontSize: isLast ? 13 : 10.5,
                              fontFamily: 'Courier New',
                              fontWeight: isLast ? FontWeight.bold : FontWeight.normal,
                              letterSpacing: 0.5,
                              shadows: [
                                Shadow(
                                  color: JarvisTheme.accent.withAlpha(120),
                                  blurRadius: 8,
                                ),
                              ],
                            ),
                          ),
                        );
                      }),
                    ),
                  ),
                ],
              ),
            ),
            // Corner HUD decorations
            ..._cornerHuds(),
            // Scanline overlay
            IgnorePointer(
              child: Opacity(
                opacity: 0.04,
                child: CustomPaint(
                  painter: _ScanlinePainter(),
                  size: Size.infinite,
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _logoText({required Color color}) {
    return Text(
      'J.A.R.V.I.S',
      style: TextStyle(
        color: color,
        fontSize: 52,
        fontWeight: FontWeight.w900,
        letterSpacing: 14,
        shadows: [
          Shadow(color: color.withAlpha(180), blurRadius: 28),
          Shadow(color: color.withAlpha(80), blurRadius: 60),
        ],
      ),
    );
  }

  List<Widget> _cornerHuds() {
    return [
      Positioned(top: 24, left: 24,
        child: CustomPaint(painter: _CornerHudPainter(t: _t, mirror: false), size: const Size(90, 90))),
      Positioned(top: 24, right: 24,
        child: Transform.flip(flipX: true,
          child: CustomPaint(painter: _CornerHudPainter(t: _t, mirror: true), size: const Size(90, 90)))),
      Positioned(bottom: 24, left: 24,
        child: Transform.flip(flipY: true,
          child: CustomPaint(painter: _CornerHudPainter(t: _t, mirror: false), size: const Size(90, 90)))),
      Positioned(bottom: 24, right: 24,
        child: Transform.flip(flipX: true, flipY: true,
          child: CustomPaint(painter: _CornerHudPainter(t: _t, mirror: true), size: const Size(90, 90)))),
    ];
  }
}

// ─── Reactor core painter ─────────────────────────────────────────────────────
class _ReactorPainter extends CustomPainter {
  final double t;
  _ReactorPainter({required this.t});

  @override
  void paint(Canvas canvas, Size size) {
    final cx = size.width / 2;
    final cy = size.height / 2;

    // Rings
    const rings = [
      (60.0, 0.012, 3, 0xFF00D4FF, 1.8),
      (82.0, -0.018, 6, 0xFF0080FF, 1.2),
      (100.0, 0.008, 12, 0xFF5E5CE6, 0.9),
    ];

    for (final (r, speed, dashes, colorVal, lw) in rings) {
      final angle = t * speed * math.pi * 2;
      canvas.save();
      canvas.translate(cx, cy);
      canvas.rotate(angle);

      final paint = Paint()
        ..color = Color(colorVal).withAlpha(180)
        ..strokeWidth = lw
        ..style = PaintingStyle.stroke
        ..maskFilter = const MaskFilter.blur(BlurStyle.outer, 4);

      // Dashed arc
      final dashLen = (2 * math.pi * r) / (dashes * 2);
      for (int i = 0; i < dashes; i++) {
        final start = (i * 2) * dashLen / r;
        canvas.drawArc(
          Rect.fromCircle(center: Offset.zero, radius: r),
          start, dashLen / r, false, paint,
        );
      }
      // Tick marks
      final tickPaint = Paint()
        ..color = Color(colorVal).withAlpha(120)
        ..strokeWidth = lw * 0.5
        ..style = PaintingStyle.stroke;
      for (int i = 0; i < dashes * 2; i++) {
        final a = (i / (dashes * 2)) * math.pi * 2;
        canvas.drawLine(
          Offset(math.cos(a) * (r - 5), math.sin(a) * (r - 5)),
          Offset(math.cos(a) * (r + 5), math.sin(a) * (r + 5)),
          tickPaint,
        );
      }
      canvas.restore();
    }

    // Core glow
    final pulse = 0.75 + 0.25 * math.sin(t * 3.0);
    for (final (radius, alpha) in [(38.0, 0.15), (24.0, 0.30), (14.0, 0.60), (7.0, 1.0)]) {
      canvas.drawCircle(
        Offset(cx, cy),
        radius * pulse,
        Paint()
          ..color = const Color(0xFF00D4FF).withAlpha((alpha * 255).round())
          ..maskFilter = MaskFilter.blur(BlurStyle.normal, radius * 0.6),
      );
    }

    // Crosshair
    final chPaint = Paint()
      ..color = const Color(0xFF00D4FF).withAlpha(60)
      ..strokeWidth = 0.8;
    canvas.drawLine(Offset(cx - 110, cy), Offset(cx + 110, cy), chPaint);
    canvas.drawLine(Offset(cx, cy - 110), Offset(cx, cy + 110), chPaint);
  }

  @override
  bool shouldRepaint(_ReactorPainter old) => old.t != t;
}

// ─── Hex grid background ──────────────────────────────────────────────────────
class _SplashBgPainter extends CustomPainter {
  final double t;
  _SplashBgPainter({required this.t});

  @override
  void paint(Canvas canvas, Size size) {


    const hexR = 28.0;
    final cols = (size.width / (hexR * 1.73)).ceil() + 2;
    final rows = (size.height / (hexR * 1.5)).ceil() + 2;

    for (int row = -1; row < rows; row++) {
      for (int col = -1; col < cols; col++) {
        final ox = col * hexR * 1.73 + (row.isOdd ? hexR * 0.865 : 0);
        final oy = row * hexR * 1.5;
        // Pulse individual hexes
        final dist = math.sqrt(
          math.pow(ox - size.width / 2, 2) + math.pow(oy - size.height / 2, 2),
        );
        final wave = math.sin(t * 1.4 - dist * 0.012);
        final alpha = ((wave * 0.5 + 0.5) * 18).round();
        if (alpha < 2) continue;
        _drawHex(canvas, Offset(ox, oy), hexR * 0.96,
            Paint()
              ..color = const Color(0xFF00D4FF).withAlpha(alpha)
              ..strokeWidth = 0.5
              ..style = PaintingStyle.stroke);
      }
    }
  }

  void _drawHex(Canvas canvas, Offset center, double r, Paint paint) {
    final path = Path();
    for (int i = 0; i < 6; i++) {
      final a = math.pi / 3 * i - math.pi / 6;
      final p = Offset(center.dx + r * math.cos(a), center.dy + r * math.sin(a));
      i == 0 ? path.moveTo(p.dx, p.dy) : path.lineTo(p.dx, p.dy);
    }
    path.close();
    canvas.drawPath(path, paint);
  }

  @override
  bool shouldRepaint(_SplashBgPainter old) => old.t != t;
}

// ─── Corner HUD decorator ─────────────────────────────────────────────────────
class _CornerHudPainter extends CustomPainter {
  final double t;
  final bool mirror;
  _CornerHudPainter({required this.t, required this.mirror});

  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()
      ..color = const Color(0xFF00D4FF).withAlpha(90)
      ..strokeWidth = 1.2
      ..style = PaintingStyle.stroke;

    // L bracket
    canvas.drawLine(Offset.zero, const Offset(40, 0), paint);
    canvas.drawLine(Offset.zero, const Offset(0, 40), paint);


    // Inner corner detail
    canvas.drawLine(const Offset(8, 0), const Offset(8, 8), paint..color = const Color(0xFF00D4FF).withAlpha(50));
    canvas.drawLine(const Offset(0, 8), const Offset(8, 8), paint);

    // Animated tick
    final tick = (t * 24) % 30.0;
    canvas.drawLine(
      Offset(tick, 0),
      Offset(tick + 6, 0),
      Paint()..color = JarvisTheme.accent..strokeWidth = 2,
    );
  }

  @override
  bool shouldRepaint(_CornerHudPainter old) => old.t != t;
}

// ─── Scanlines ────────────────────────────────────────────────────────────────
class _ScanlinePainter extends CustomPainter {
  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()
      ..color = Colors.black
      ..strokeWidth = 1;
    for (double y = 0; y < size.height; y += 3) {
      canvas.drawLine(Offset(0, y), Offset(size.width, y), paint);
    }
  }

  @override
  bool shouldRepaint(_ScanlinePainter old) => false;
}
