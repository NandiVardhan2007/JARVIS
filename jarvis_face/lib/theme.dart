import 'package:flutter/material.dart';

/// Opacity helper that works across all Flutter 3.x versions. (`withOpacity` is
/// deprecated on new Flutter and `withValues` is missing on older Flutter, but
/// `withAlpha` is stable on both.)
extension ColorOpacity on Color {
  Color op(double o) => withAlpha((o.clamp(0.0, 1.0) * 255).round());
}

/// Global look-and-feel for the JARVIS frontend. Deep-space dark canvas so the
/// glowing orb and cards read with maximum contrast.
class JarvisTheme {
  static const Color bgTop = Color(0xFF05070D);
  static const Color bgBottom = Color(0xFF0B0F1A);
  static const Color card = Color(0x14202840);
  static const Color cardBorder = Color(0x22394B6E);
  static const Color textPrimary = Color(0xFFEAF2FF);
  static const Color textDim = Color(0x99AFC2E0);
  static const Color accent = Color(0xFF00D4FF);

  static ThemeData build() {
    final base = ThemeData.dark(useMaterial3: true);
    return base.copyWith(
      scaffoldBackgroundColor: bgBottom,
      colorScheme: base.colorScheme.copyWith(
        primary: accent,
        surface: bgBottom,
      ),
      textTheme: base.textTheme.apply(
        bodyColor: textPrimary,
        displayColor: textPrimary,
        fontFamily: 'Roboto',
      ),
    );
  }

  /// Radial vignette background used behind the orb.
  static BoxDecoration backgroundDecoration(Color glow) {
    return BoxDecoration(
      gradient: RadialGradient(
        center: const Alignment(0, -0.25),
        radius: 1.1,
        colors: [
          Color.lerp(bgTop, glow, 0.10)!,
          bgTop,
          bgBottom,
        ],
        stops: const [0.0, 0.55, 1.0],
      ),
    );
  }

  static BoxDecoration glassCard(Color accent) {
    return BoxDecoration(
      borderRadius: BorderRadius.circular(20),
      gradient: LinearGradient(
        begin: Alignment.topLeft,
        end: Alignment.bottomRight,
        colors: [
          accent.op(0.10),
          Colors.white.op(0.02),
        ],
      ),
      border: Border.all(color: accent.op(0.28), width: 1),
      boxShadow: [
        BoxShadow(
          color: accent.op(0.12),
          blurRadius: 24,
          spreadRadius: -6,
        ),
      ],
    );
  }
}
