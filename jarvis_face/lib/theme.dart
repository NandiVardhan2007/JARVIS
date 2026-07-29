import 'package:flutter/material.dart';

/// Global runtime theme-mode switch — toggle via the button in the top bar.
/// Defaults to dark since the whole visual language (glowing orb, deep-space
/// gradients) was designed dark-first, but a genuinely adapted light variant
/// is available too, not just Flutter's stock ThemeData.light().
final ValueNotifier<ThemeMode> jarvisThemeMode = ValueNotifier(ThemeMode.dark);

void toggleJarvisTheme() {
  jarvisThemeMode.value =
      jarvisThemeMode.value == ThemeMode.dark ? ThemeMode.light : ThemeMode.dark;
}

/// Opacity helper that works across all Flutter 3.x versions. (`withOpacity` is
/// deprecated on new Flutter and `withValues` is missing on older Flutter, but
/// `withAlpha` is stable on both.)
extension ColorOpacity on Color {
  Color op(double o) => withAlpha((o.clamp(0.0, 1.0) * 255).round());
}

/// Global look-and-feel for the JARVIS frontend. Deep-space dark canvas so the
/// glowing orb and cards read with maximum contrast (default). A light
/// variant is also available for JarvisTheme.buildLight().
class JarvisTheme {
  static const Color bgTop = Color(0xFF05070D);
  static const Color bgBottom = Color(0xFF0B0F1A);
  static const Color card = Color(0x14202840);
  static const Color cardBorder = Color(0x22394B6E);
  static const Color textPrimary = Color(0xFFEAF2FF);
  static const Color textDim = Color(0x99AFC2E0);
  static const Color accent = Color(0xFF00D4FF);

  // Light variant — soft overcast-sky canvas rather than an inverted dark
  // theme, since the glow/aura effects need a backdrop they can still read
  // clearly against.
  static const Color bgTopLight = Color(0xFFEFF3FA);
  static const Color bgBottomLight = Color(0xFFDCE4F2);
  static const Color cardLight = Color(0xCCFFFFFF);
  static const Color cardBorderLight = Color(0x330B3D91);
  static const Color textPrimaryLight = Color(0xFF0B1526);
  static const Color textDimLight = Color(0x991B2A44);
  static const Color accentLight = Color(0xFF0072C6);

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

  static ThemeData buildLight() {
    final base = ThemeData.light(useMaterial3: true);
    return base.copyWith(
      scaffoldBackgroundColor: bgBottomLight,
      colorScheme: base.colorScheme.copyWith(
        primary: accentLight,
        surface: bgBottomLight,
      ),
      textTheme: base.textTheme.apply(
        bodyColor: textPrimaryLight,
        displayColor: textPrimaryLight,
        fontFamily: 'Roboto',
      ),
    );
  }

  /// Radial vignette background used behind the orb. `isDark` picks which
  /// palette to blend the glow against.
  static BoxDecoration backgroundDecoration(Color glow, {bool isDark = true}) {
    final top = isDark ? bgTop : bgTopLight;
    final bottom = isDark ? bgBottom : bgBottomLight;
    return BoxDecoration(
      gradient: RadialGradient(
        center: const Alignment(0, -0.25),
        radius: 1.1,
        colors: [
          Color.lerp(top, glow, isDark ? 0.10 : 0.16)!,
          top,
          bottom,
        ],
        stops: const [0.0, 0.55, 1.0],
      ),
    );
  }

  static BoxDecoration glassCard(Color accent, {bool isDark = true}) {
    final base = isDark ? Colors.white : Colors.black;
    final border = isDark ? accent.op(0.28) : accent.op(0.35);
    return BoxDecoration(
      borderRadius: BorderRadius.circular(20),
      gradient: LinearGradient(
        begin: Alignment.topLeft,
        end: Alignment.bottomRight,
        colors: [
          accent.op(isDark ? 0.10 : 0.14),
          base.op(0.02),
        ],
      ),
      border: Border.all(color: border, width: 1),
      boxShadow: [
        BoxShadow(
          color: accent.op(isDark ? 0.12 : 0.10),
          blurRadius: 24,
          spreadRadius: -6,
        ),
      ],
    );
  }
}
