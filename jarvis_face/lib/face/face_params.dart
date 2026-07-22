import 'dart:ui';

import '../models/jarvis_state.dart';

/// One orbiting particle used for the "thinking" animation, with a short
/// afterglow trail.
class Particle {
  double angle;
  double radius;
  double size;
  double alpha;
  double speed;
  double life;
  final List<Offset> trail;

  Particle({
    required this.angle,
    required this.radius,
    required this.size,
    required this.alpha,
    required this.speed,
    required this.life,
  }) : trail = <Offset>[];
}

/// A parameterised facial "pose". The widget damps the current pose toward the
/// target pose for the active emotion, so expressions blend smoothly instead of
/// snapping. Every field is a normalised scalar.
class ExprTargets {
  /// Vertical brow position: -1 low/furrowed, +1 raised.
  final double browRaise;

  /// Inner-brow tilt: +1 inner-up (worried/sad), -1 inner-down (angry).
  final double browTilt;

  /// How open the eyes are: 0 shut, 1 wide.
  final double eyeOpen;

  /// Lower-eyelid raise (squint / happy crescent): 0..1.
  final double lowerLid;

  /// Pupil dilation: 0 pinpoint, 1 blown wide.
  final double pupil;

  /// Mouth curvature: -1 frown, +1 big smile.
  final double mouthCurve;

  /// Baseline mouth openness before voice amplitude is added.
  final double mouthOpen;

  /// Heart-eyes amount (love).
  final double heart;

  /// Cheek blush amount.
  final double blush;

  const ExprTargets({
    this.browRaise = 0.15,
    this.browTilt = 0,
    this.eyeOpen = 0.85,
    this.lowerLid = 0.05,
    this.pupil = 0.5,
    this.mouthCurve = 0.1,
    this.mouthOpen = 0,
    this.heart = 0,
    this.blush = 0,
  });
}

/// The target pose for each emotion.
ExprTargets exprFor(Emotion e) {
  switch (e) {
    case Emotion.happy:
      return const ExprTargets(
          browRaise: 0.45,
          browTilt: 0.1,
          eyeOpen: 0.72,
          lowerLid: 0.55,
          pupil: 0.6,
          mouthCurve: 0.85,
          mouthOpen: 0.08,
          blush: 0.3);
    case Emotion.sad:
      return const ExprTargets(
          browRaise: -0.1,
          browTilt: 0.8,
          eyeOpen: 0.7,
          lowerLid: 0.15,
          pupil: 0.55,
          mouthCurve: -0.6);
    case Emotion.thinking:
      return const ExprTargets(
          browRaise: 0.2,
          browTilt: -0.2,
          eyeOpen: 0.66,
          lowerLid: 0.12,
          pupil: 0.45,
          mouthCurve: -0.05);
    case Emotion.alert:
    case Emotion.angry:
      return const ExprTargets(
          browRaise: -0.35,
          browTilt: -0.85,
          eyeOpen: 1.0,
          lowerLid: 0.2,
          pupil: 0.32,
          mouthCurve: -0.35,
          mouthOpen: 0.12);
    case Emotion.surprised:
      return const ExprTargets(
          browRaise: 1.0,
          browTilt: 0.1,
          eyeOpen: 1.0,
          lowerLid: 0.0,
          pupil: 0.85,
          mouthCurve: 0.0,
          mouthOpen: 0.6);
    case Emotion.love:
      return const ExprTargets(
          browRaise: 0.4,
          browTilt: 0.2,
          eyeOpen: 0.62,
          lowerLid: 0.5,
          pupil: 0.75,
          mouthCurve: 0.7,
          mouthOpen: 0.06,
          heart: 1.0,
          blush: 0.65);
    case Emotion.curious:
      return const ExprTargets(
          browRaise: 0.55,
          browTilt: -0.1,
          eyeOpen: 0.92,
          lowerLid: 0.05,
          pupil: 0.62,
          mouthCurve: 0.2,
          mouthOpen: 0.05);
    case Emotion.sleepy:
      return const ExprTargets(
          browRaise: -0.05,
          browTilt: 0.15,
          eyeOpen: 0.3,
          lowerLid: 0.25,
          pupil: 0.55,
          mouthCurve: 0.0,
          mouthOpen: 0.05);
    case Emotion.wink:
    case Emotion.neutral:
      return const ExprTargets();
  }
}

/// Everything the [FacePainter] needs for one frame. Produced each tick by
/// [JarvisFace] and handed to the painter via a [ValueNotifier] so only the
/// CustomPaint repaints.
class FaceParams {
  Color primary;
  Color secondary;
  AssistantState state;

  // ── Resolved (already-blended) expression pose ──
  double browRaise;
  double browTilt;
  double eyeOpen; // baseline lid, before blink
  double lowerLid;
  double pupilDilate;
  double mouthCurve;
  double mouthOpenBase;
  double heart;
  double blush;

  /// Momentary blink 0..1 (1 == fully closed), independent of [eyeOpen].
  double blink;

  /// One-eye wink amount 0..1 (closes the left eye).
  double wink;

  /// Gaze offset, each -1..1.
  double pupilX;
  double pupilY;

  double micLevel;
  double aiLevel;

  /// Live mouth openness from voice amplitude (viseme drive).
  double mouth;

  double breath;
  double t;

  /// Idle vertical float offset (px).
  double floatY;

  /// Rotation phases for the two HUD reticle rings (radians).
  double hudA;
  double hudB;

  /// Bright inner core energy 0..1 (pulses with voice / state).
  double core;

  double rippleRadius;
  double rippleAlpha;
  bool micMuted;

  List<Particle> particles;
  List<double> wave;

  FaceParams({
    required this.primary,
    required this.secondary,
    required this.state,
    this.browRaise = 0.15,
    this.browTilt = 0,
    this.eyeOpen = 0.85,
    this.lowerLid = 0.05,
    this.pupilDilate = 0.5,
    this.mouthCurve = 0.1,
    this.mouthOpenBase = 0,
    this.heart = 0,
    this.blush = 0,
    this.blink = 0,
    this.wink = 0,
    this.pupilX = 0,
    this.pupilY = 0,
    this.micLevel = 0,
    this.aiLevel = 0,
    this.mouth = 0,
    this.breath = 0,
    this.t = 0,
    this.floatY = 0,
    this.hudA = 0,
    this.hudB = 0,
    this.core = 0,
    this.rippleRadius = 0,
    this.rippleAlpha = 0,
    this.micMuted = false,
    List<Particle>? particles,
    List<double>? wave,
  })  : particles = particles ?? <Particle>[],
        wave = wave ?? List<double>.filled(56, 0);
}
