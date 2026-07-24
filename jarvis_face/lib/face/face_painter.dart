import 'dart:math' as math;

import 'package:flutter/material.dart';

import '../models/jarvis_state.dart';
import '../theme.dart';
import 'face_params.dart';

/// Renders the JARVIS face: a glowing energy orb wrapped in a rotating
/// holographic HUD, with a realistic expressive face — almond eyes with iris,
/// pupils, catchlights and eyelids, eyebrows, heart-eyes, cheeks, and a
/// lip-syncing mouth.
class FacePainter extends CustomPainter {
  final FaceParams p;
  FacePainter(this.p);

  static const Color _ink = Color(0xFF07121F); // dark face plate
  static const Color _eyeWhite = Color(0xFFF4FBFF);

  @override
  void paint(Canvas canvas, Size size) {
    final r = math.min(size.width, size.height) * 0.30;
    final c = Offset(size.width / 2, size.height / 2 + p.floatY);

    canvas.save();

    _aura(canvas, c, r);
    _hudRings(canvas, c, r);
    _orbBody(canvas, c, r);
    _glassSheen(canvas, c, r);

    if (p.state == AssistantState.speaking) _waveform(canvas, c, r);

    _blush(canvas, c, r);
    _brows(canvas, c, r);
    _eyes(canvas, c, r);
    _mouth(canvas, c, r);

    if (p.state == AssistantState.listening) _micRing(canvas, c, r);
    _particles(canvas, c, r);
    _ripple(canvas, c, r);
    if (p.micMuted) _muteBadge(canvas, c, r);

    canvas.restore();
  }

  // ── Aura / bloom ────────────────────────────────────────────────────────
  void _aura(Canvas canvas, Offset c, double r) {
    final breath = 0.6 + 0.4 * (0.5 + 0.5 * math.sin(p.breath));
    final scale = 1.0 + 0.06 * math.sin(p.breath) + 0.12 * p.core;
    final ar = r * 2.8 * scale;
    canvas.drawCircle(
      c,
      ar,
      Paint()
        ..shader = RadialGradient(
          colors: [
            p.primary.op(0.32 * breath),
            p.primary.op(0.12 * breath),
            p.primary.op(0.0),
          ],
          stops: const [0.0, 0.42, 1.0],
        ).createShader(Rect.fromCircle(center: c, radius: ar)),
    );
  }

  // ── Holographic HUD reticle ─────────────────────────────────────────────
  void _hudRings(Canvas canvas, Offset c, double r) {
    final col = p.primary;

    // Ring A: three glowing arc segments, rotating.
    final rA = r * 1.20;
    final rectA = Rect.fromCircle(center: c, radius: rA);
    final penA = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = 2.2
      ..strokeCap = StrokeCap.round
      ..color = col.op(0.55);
    for (var i = 0; i < 3; i++) {
      final start = p.hudA + i * (2 * math.pi / 3);
      canvas.drawArc(rectA, start, 0.7, false, penA);
    }
    // Tick marks just inside ring A.
    final tickPen = Paint()
      ..strokeWidth = 1.2
      ..color = col.op(0.28);
    const ticks = 48;
    for (var i = 0; i < ticks; i++) {
      final a = p.hudA * 0.5 + i * (2 * math.pi / ticks);
      final inner = rA * 0.965;
      final outer = rA * (i % 4 == 0 ? 0.995 : 0.982);
      canvas.drawLine(
        Offset(c.dx + math.cos(a) * inner, c.dy + math.sin(a) * inner),
        Offset(c.dx + math.cos(a) * outer, c.dy + math.sin(a) * outer),
        tickPen,
      );
    }

    // Ring B: dotted ring, counter-rotating.
    final rB = r * 1.42;
    const dots = 60;
    for (var i = 0; i < dots; i++) {
      final a = p.hudB + i * (2 * math.pi / dots);
      final pos = Offset(c.dx + math.cos(a) * rB, c.dy + math.sin(a) * rB);
      canvas.drawCircle(pos, i % 5 == 0 ? 1.6 : 0.8, Paint()..color = col.op(0.30));
    }

    // Orbiting energy nodes on ring A.
    for (var i = 0; i < 3; i++) {
      final a = p.hudA + i * (2 * math.pi / 3) + 0.35;
      final pos = Offset(c.dx + math.cos(a) * rA, c.dy + math.sin(a) * rA);
      canvas.drawCircle(
        pos,
        3.2,
        Paint()
          ..shader = RadialGradient(colors: [col.op(0.9), col.op(0)])
              .createShader(Rect.fromCircle(center: pos, radius: 5)),
      );
    }

    // Corner reticle brackets (targeting feel), slow drift.
    _brackets(canvas, c, r * 1.55, col.op(0.34), p.hudB * 0.3);
  }

  void _brackets(Canvas canvas, Offset c, double rad, Color col, double rot) {
    final pen = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = 2.0
      ..strokeCap = StrokeCap.round
      ..color = col;
    const len = 0.18; // radians of the corner arc
    for (var i = 0; i < 4; i++) {
      final base = rot + i * (math.pi / 2) + math.pi / 4;
      final rect = Rect.fromCircle(center: c, radius: rad);
      canvas.drawArc(rect, base - len, len * 2, false, pen);
    }
  }

  // ── Orb body + energy core ──────────────────────────────────────────────
  void _orbBody(Canvas canvas, Offset c, double r) {
    // Fluid blobs give the orb life.
    final deform = p.state == AssistantState.speaking
        ? 4.0 + p.aiLevel * 6
        : p.state == AssistantState.thinking
            ? 3.0
            : 1.6;
    final t = p.t * 1.3;
    for (var i = 0; i < 3; i++) {
      final a = t + i * 2.094;
      final bc = Offset(c.dx + math.cos(a) * deform, c.dy + math.sin(a) * deform);
      final br = r + math.sin(t * 2 + i) * deform * 0.6;
      final col = i.isEven ? p.primary : p.secondary;
      canvas.drawCircle(
        bc,
        br * 1.12,
        Paint()
          ..blendMode = BlendMode.plus
          ..shader = RadialGradient(
            colors: [col.op(0.55), col.op(0.16), col.op(0)],
            stops: const [0.0, 0.6, 1.0],
          ).createShader(Rect.fromCircle(center: bc, radius: br * 1.12)),
      );
    }

    // Dark glassy face plate for feature contrast.
    canvas.drawCircle(
      c,
      r,
      Paint()
        ..shader = RadialGradient(
          center: const Alignment(-0.3, -0.4),
          colors: [
            Color.lerp(p.primary, _ink, 0.45)!.op(0.75),
            _ink.op(0.82),
          ],
        ).createShader(Rect.fromCircle(center: c, radius: r)),
    );

    // Pulsing energy-core rim.
    final rimGlow = 0.25 + 0.6 * p.core;
    canvas.drawCircle(
      c,
      r * 0.62,
      Paint()
        ..style = PaintingStyle.stroke
        ..strokeWidth = 1.5 + 2.5 * p.core
        ..color = p.primary.op(rimGlow)
        ..maskFilter = const MaskFilter.blur(BlurStyle.normal, 3),
    );

    // Rotating sweep rim-light.
    canvas.drawCircle(
      c,
      r,
      Paint()
        ..style = PaintingStyle.stroke
        ..strokeWidth = 1.6
        ..shader = SweepGradient(
          transform: GradientRotation(p.t * 0.6),
          colors: [
            p.primary.op(0),
            p.primary.op(0.6),
            p.secondary.op(0.5),
            p.primary.op(0),
          ],
        ).createShader(Rect.fromCircle(center: c, radius: r)),
    );
  }

  void _glassSheen(Canvas canvas, Offset c, double r) {
    final rect = Rect.fromCenter(
      center: Offset(c.dx - r * 0.32, c.dy - r * 0.44),
      width: r * 1.1,
      height: r * 0.7,
    );
    canvas.drawOval(
      rect,
      Paint()
        ..shader = RadialGradient(colors: [Colors.white.op(0.16), Colors.white.op(0)])
            .createShader(rect)
        ..maskFilter = const MaskFilter.blur(BlurStyle.normal, 6),
    );
  }

  // ── Circular speaking waveform ──────────────────────────────────────────
  void _waveform(Canvas canvas, Offset c, double r) {
    final n = p.wave.length;
    final baseR = r * 1.06;
    final pen = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = 2.0
      ..strokeCap = StrokeCap.round
      ..color = p.primary.op(0.8);
    for (var i = 0; i < n; i++) {
      final ang = (i / n) * math.pi * 2 - math.pi / 2;
      final outer = baseR + 3 + p.wave[i] * r * 0.5;
      canvas.drawLine(
        Offset(c.dx + math.cos(ang) * baseR, c.dy + math.sin(ang) * baseR),
        Offset(c.dx + math.cos(ang) * outer, c.dy + math.sin(ang) * outer),
        pen,
      );
    }
  }

  // ── Cheeks ──────────────────────────────────────────────────────────────
  void _blush(Canvas canvas, Offset c, double r) {
    if (p.blush < 0.03) return;
    for (final side in [-1, 1]) {
      final pos = Offset(c.dx + side * r * 0.44, c.dy + r * 0.20);
      final rect = Rect.fromCenter(center: pos, width: r * 0.5, height: r * 0.34);
      canvas.drawOval(
        rect,
        Paint()
          ..shader = RadialGradient(
            colors: [const Color(0xFFFF6B9D).op(0.5 * p.blush), const Color(0x00FF6B9D)],
          ).createShader(rect)
          ..maskFilter = const MaskFilter.blur(BlurStyle.normal, 4),
      );
    }
  }

  // ── Eyebrows ────────────────────────────────────────────────────────────
  void _brows(Canvas canvas, Offset c, double r) {
    final eo = r * 0.40;
    final eyeTop = c.dy - r * 0.08 - r * 0.16;
    final hw = r * 0.20;
    final pen = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = math.max(2.4, r * 0.055)
      ..strokeCap = StrokeCap.round
      ..color = _eyeWhite.op(0.9);
    for (final side in [-1, 1]) {
      final ex = c.dx + side * eo;
      // Bigger vertical travel so mood reads clearly.
      final browY = eyeTop - r * 0.10 - p.browRaise * r * 0.12;
      final innerX = ex - side * hw * 0.65;
      final outerX = ex + side * hw * 1.05;
      // Stronger inner-tilt for sad(+)/angry(-) expressions.
      final innerY = browY - p.browTilt * r * 0.10;
      final outerY = browY + p.browTilt * r * 0.04;
      final path = Path()
        ..moveTo(innerX, innerY)
        ..quadraticBezierTo(ex, browY - r * 0.04, outerX, outerY);
      canvas.drawPath(path, pen);
    }
  }

  // ── Eyes ────────────────────────────────────────────────────────────────
  void _eyes(Canvas canvas, Offset c, double r) {
    final ey = c.dy - r * 0.08;
    final eo = r * 0.40;
    final hw = r * 0.205; // eye half width
    final hhBase = r * 0.17; // eye half height when fully open

    for (final side in [-1, 1]) {
      final ex = c.dx + side * eo;
      // Per-eye openness (left eye = side -1 also winks).
      var open = (p.eyeOpen * (1 - p.blink)).clamp(0.0, 1.0);
      if (side == -1) open *= (1 - p.wink);
      final center = Offset(ex, ey);

      if (open < 0.10) {
        // Closed → gentle lash curve.
        final pen = Paint()
          ..style = PaintingStyle.stroke
          ..strokeWidth = math.max(2.2, r * 0.05)
          ..strokeCap = StrokeCap.round
          ..color = _eyeWhite.op(0.92);
        final path = Path()
          ..moveTo(ex - hw, ey)
          ..quadraticBezierTo(ex, ey + hhBase * 0.5, ex + hw, ey);
        canvas.drawPath(path, pen);
        continue;
      }

      final hh = hhBase * open;
      final botH = hh * (1 - p.lowerLid * 0.7);
      final eyePath = _lens(center, hw, hh, botH);

      canvas.save();
      canvas.clipPath(eyePath);

      // Eye interior faint glow.
      canvas.drawRect(
        Rect.fromCircle(center: center, radius: hw * 1.4),
        Paint()..color = const Color(0xFF0A1622),
      );

      // Iris follows gaze (kept inside the eye).
      final gaze = Offset(
        p.pupilX * hw * 0.4,
        p.pupilY * hh * 0.4,
      );
      final iris = center + gaze;
      final ir = hw * 0.62;

      if (p.heart > 0.5) {
        _heartEye(canvas, iris, ir * 1.15);
      } else {
        // Iris gradient.
        canvas.drawCircle(
          iris,
          ir,
          Paint()
            ..shader = RadialGradient(
              colors: [
                Color.lerp(p.primary, Colors.white, 0.55)!,
                p.primary,
                Color.lerp(p.primary, _ink, 0.5)!,
              ],
              stops: const [0.0, 0.55, 1.0],
            ).createShader(Rect.fromCircle(center: iris, radius: ir)),
        );
        // Pupil (dilates with state/emotion) — wider range = more expressive.
        final pr = ir * (0.30 + 0.46 * p.pupilDilate);
        canvas.drawCircle(iris, pr, Paint()..color = const Color(0xFF05090F));
        // Catchlights.
        canvas.drawCircle(
          iris + Offset(-ir * 0.35, -ir * 0.4),
          ir * 0.22,
          Paint()..color = Colors.white.op(0.95),
        );
        canvas.drawCircle(
          iris + Offset(ir * 0.28, ir * 0.25),
          ir * 0.11,
          Paint()..color = Colors.white.op(0.6),
        );
      }

      canvas.restore();

      // Upper-lid shadow line (definition).
      final lidPen = Paint()
        ..style = PaintingStyle.stroke
        ..strokeWidth = math.max(1.4, r * 0.03)
        ..strokeCap = StrokeCap.round
        ..color = _eyeWhite.op(0.85);
      final lid = Path()
        ..moveTo(ex - hw, ey)
        ..quadraticBezierTo(ex, ey - hh * 1.9, ex + hw, ey);
      canvas.drawPath(lid, lidPen);
    }
  }

  /// Almond "lens" path: upper arc of height [topH], lower arc of height [botH].
  Path _lens(Offset c, double hw, double topH, double botH) {
    return Path()
      ..moveTo(c.dx - hw, c.dy)
      ..quadraticBezierTo(c.dx, c.dy - topH * 1.9, c.dx + hw, c.dy)
      ..quadraticBezierTo(c.dx, c.dy + botH * 1.9, c.dx - hw, c.dy)
      ..close();
  }

  void _heartEye(Canvas canvas, Offset c, double s) {
    final path = Path();
    final top = c.dy - s * 0.2;
    path.moveTo(c.dx, c.dy + s * 0.75);
    path.cubicTo(c.dx - s * 1.2, c.dy - s * 0.2, c.dx - s * 0.5, top - s * 0.7, c.dx, top);
    path.cubicTo(c.dx + s * 0.5, top - s * 0.7, c.dx + s * 1.2, c.dy - s * 0.2, c.dx, c.dy + s * 0.75);
    path.close();
    canvas.drawPath(
      path,
      Paint()
        ..shader = const RadialGradient(colors: [Color(0xFFFF7EB0), Color(0xFFFF2D6B)])
            .createShader(Rect.fromCircle(center: c, radius: s)),
    );
  }

  // ── Mouth (lip-sync viseme) ─────────────────────────────────────────────
  void _mouth(Canvas canvas, Offset c, double r) {
    final my = c.dy + r * 0.36;
    final mw = r * 0.30;
    final open = p.mouth.clamp(0.0, 1.0);
    final curve = p.mouthCurve;

    final midOffset = curve * mw * 0.68; // smile/frown depth (more expressive)
    final openH = open * r * 0.44;
    final widthFactor = 1 - 0.34 * open; // rounder when very open
    // A smile also widens the mouth a touch; a frown narrows it.
    final halfW = mw * (0.62 + curve.clamp(-1.0, 1.0) * 0.06) * widthFactor;

    if (open <= 0.06) {
      // Closed lips → expressive curve.
      final pen = Paint()
        ..style = PaintingStyle.stroke
        ..strokeWidth = math.max(2.0, r * 0.05)
        ..strokeCap = StrokeCap.round
        ..color = _eyeWhite.op(0.85);
      final path = Path()
        ..moveTo(c.dx - halfW, my)
        ..quadraticBezierTo(c.dx, my + midOffset + openH, c.dx + halfW, my);
      canvas.drawPath(path, pen);
      return;
    }

    // Open mouth: filled cavity between upper and lower lips.
    final cavity = Path()
      ..moveTo(c.dx - halfW, my)
      ..quadraticBezierTo(c.dx, my + midOffset - openH * 0.12, c.dx + halfW, my)
      ..quadraticBezierTo(c.dx, my + midOffset + openH, c.dx - halfW, my)
      ..close();
    final rect = Rect.fromCenter(center: Offset(c.dx, my + midOffset + openH * 0.4),
        width: halfW * 2, height: openH * 1.6);
    canvas.drawPath(
      cavity,
      Paint()
        ..shader = const RadialGradient(
          colors: [Color(0xFF3A1420), Color(0xFF14060B)],
        ).createShader(rect),
    );

    // Lower-lip gloss.
    final gloss = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = math.max(1.6, r * 0.03)
      ..strokeCap = StrokeCap.round
      ..color = _eyeWhite.op(0.55);
    canvas.drawPath(
      Path()
        ..moveTo(c.dx - halfW * 0.8, my + midOffset + openH * 0.55)
        ..quadraticBezierTo(
            c.dx, my + midOffset + openH * 0.95, c.dx + halfW * 0.8, my + midOffset + openH * 0.55),
      gloss,
    );
  }

  // ── Listening ring ──────────────────────────────────────────────────────
  void _micRing(Canvas canvas, Offset c, double r) {
    final lv = p.micLevel;
    if (lv < 0.03) return;
    for (var i = 0; i < 2; i++) {
      final ringR = r * 1.05 + i * 8 + lv * (14 + i * 10);
      canvas.drawCircle(
        c,
        ringR,
        Paint()
          ..style = PaintingStyle.stroke
          ..strokeWidth = 2.0 - i * 0.6
          ..color = const Color(0xFF32D74B).op((0.55 - i * 0.25) * lv.clamp(0.0, 1.0)),
      );
    }
  }

  // ── Thinking particles ──────────────────────────────────────────────────
  void _particles(Canvas canvas, Offset c, double r) {
    for (final pt in p.particles) {
      if (pt.alpha < 0.02) continue;
      for (var ti = 0; ti < pt.trail.length; ti++) {
        final frac = (ti + 1) / (pt.trail.length + 1);
        final a = pt.alpha * frac * 0.35;
        final sz = pt.size * frac * 0.6;
        if (a < 0.02 || sz < 0.3) continue;
        canvas.drawCircle(
          pt.trail[ti],
          sz * 1.8,
          Paint()
            ..color = const Color(0xFFFFB432).op(a)
            ..maskFilter = const MaskFilter.blur(BlurStyle.normal, 2),
        );
      }
      final pos = Offset(
        c.dx + math.cos(pt.angle) * pt.radius,
        c.dy + math.sin(pt.angle) * pt.radius,
      );
      canvas.drawCircle(
        pos,
        pt.size * 2,
        Paint()
          ..shader = RadialGradient(
            colors: [
              const Color(0xFFFFC864).op(pt.alpha),
              const Color(0xFFFF8C1E).op(pt.alpha * 0.4),
              const Color(0x00FF8C1E),
            ],
          ).createShader(Rect.fromCircle(center: pos, radius: pt.size * 2)),
      );
    }
  }

  void _ripple(Canvas canvas, Offset c, double r) {
    if (p.rippleAlpha < 0.01) return;
    final rr = p.rippleRadius;
    canvas.drawCircle(
      c,
      rr,
      Paint()
        ..style = PaintingStyle.stroke
        ..strokeWidth = 2.0
        ..color = p.primary.op(0.7 * p.rippleAlpha),
    );
    if (rr > 12) {
      canvas.drawCircle(
        c,
        rr * 0.65,
        Paint()
          ..style = PaintingStyle.stroke
          ..strokeWidth = 1.2
          ..color = p.primary.op(0.32 * p.rippleAlpha),
      );
    }
  }

  void _muteBadge(Canvas canvas, Offset c, double r) {
    final b = Offset(c.dx + r * 0.72, c.dy - r * 0.72);
    final br = r * 0.16;
    canvas.drawCircle(b, br, Paint()..color = const Color(0xFFFF3B30));
    final slash = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = 2.0
      ..strokeCap = StrokeCap.round
      ..color = Colors.white;
    canvas.drawLine(
      b + Offset(-br * 0.5, br * 0.5),
      b + Offset(br * 0.5, -br * 0.5),
      slash,
    );
  }

  @override
  bool shouldRepaint(covariant FacePainter oldDelegate) => true;
}
