import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:flutter/scheduler.dart';

import '../models/jarvis_state.dart';
import 'face_params.dart';
import 'face_painter.dart';

/// The animated JARVIS face. Give it a [JarvisSnapshot] and it continuously
/// animates a parameterised facial rig: expressions blend smoothly, eyes blink
/// and saccade, pupils dilate, the mouth lip-syncs to voice amplitude, and a
/// holographic HUD rotates around a glowing energy core.
class JarvisFace extends StatefulWidget {
  final JarvisSnapshot snapshot;
  final double size;

  const JarvisFace({super.key, required this.snapshot, this.size = 360});

  @override
  State<JarvisFace> createState() => _JarvisFaceState();
}

class _JarvisFaceState extends State<JarvisFace>
    with SingleTickerProviderStateMixin {
  late final Ticker _ticker;
  final math.Random _rng = math.Random();
  late final ValueNotifier<FaceParams> _params;

  // Time.
  double _t = 0, _lastElapsed = 0, _breath = 0;

  // Smoothed levels.
  double _aiLevel = 0, _micLevel = 0, _mouth = 0, _core = 0;

  // Colours.
  Color _primary = const Color(0xFF5082B4);
  Color _secondary = const Color(0xFF285078);

  // Blink.
  double _blink = 0, _nextBlink = 2, _blinkClock = 0, _blinkPhase = 0;
  bool _blinking = false;

  // Wink (idle easter-egg).
  double _wink = 0, _winkPhase = 0, _nextWink = 12, _winkClock = 0;
  bool _winking = false;

  // Gaze.
  double _pupilX = 0, _pupilY = 0, _pupilTX = 0, _pupilTY = 0;
  double _nextSaccade = 1.5, _saccadeClock = 0;

  // Head movement (turn/tilt) — follows gaze loosely, plus a slow idle sway,
  // so the head reads as accompanying the eyes rather than the dominant motion.
  double _headTurn = 0, _headTilt = 0;

  // Expression pose (damped toward the active emotion's targets).
  double _browRaise = 0.15,
      _browTilt = 0,
      _eyeOpen = 0.85,
      _lowerLid = 0.05,
      _pupilDilate = 0.5,
      _mouthCurve = 0.1,
      _mouthOpenBase = 0,
      _heart = 0,
      _blush = 0;

  // Idle → sleepy.
  double _idleTime = 0;
  double _floatY = 0;

  // HUD ring rotation.
  double _hudA = 0, _hudB = 0;

  // Particles / ripple / wave.
  final List<Particle> _particles = [];
  double _rippleRadius = 0, _rippleAlpha = 0;
  AssistantState _lastState = AssistantState.idle;
  final List<double> _wave = List<double>.filled(56, 0);

  @override
  void initState() {
    super.initState();
    final s = widget.snapshot;
    _primary = s.colors.primary;
    _secondary = s.colors.secondary;
    _lastState = s.state;
    _params = ValueNotifier<FaceParams>(_build());
    _ticker = createTicker(_onTick)..start();
  }

  @override
  void dispose() {
    _ticker.dispose();
    _params.dispose();
    super.dispose();
  }

  double _damp(double cur, double tgt, double rate, double dt) =>
      cur + (tgt - cur) * (1 - math.exp(-rate * dt));

  /// Which emotion to actually display (adds idle-driven sleepy + wink).
  Emotion _displayEmotion(JarvisSnapshot s) {
    if (s.state == AssistantState.idle && _idleTime > 14) return Emotion.sleepy;
    return s.emotion;
  }

  void _onTick(Duration elapsed) {
    final now = elapsed.inMicroseconds / 1e6;
    var dt = now - _lastElapsed;
    _lastElapsed = now;
    if (dt <= 0) return;
    if (dt > 0.05) dt = 0.05;
    _t += dt;
    _breath += dt * 1.5;
    _hudA += dt * 0.35;
    _hudB -= dt * 0.22;

    final s = widget.snapshot;

    // Idle timer (drives sleepy + float).
    if (s.state == AssistantState.idle) {
      _idleTime += dt;
    } else {
      _idleTime = 0;
    }

    // Colours.
    final tc = s.colors;
    _primary = Color.lerp(_primary, tc.primary, 1 - math.exp(-6 * dt))!;
    _secondary = Color.lerp(_secondary, tc.secondary, 1 - math.exp(-6 * dt))!;

    // Levels + core energy.
    _aiLevel = _damp(_aiLevel, s.aiLevel, 14, dt);
    _micLevel = _damp(_micLevel, s.micLevel, 16, dt);
    double coreTarget = 0.25 + 0.5 * _aiLevel;
    if (s.state == AssistantState.thinking) coreTarget = 0.45 + 0.2 * math.sin(_t * 4);
    if (s.state == AssistantState.listening) coreTarget = 0.3 + 0.5 * _micLevel;
    _core = _damp(_core, coreTarget.clamp(0.0, 1.0), 8, dt);

    // Expression blend.
    final e = _displayEmotion(s);
    final tgt = exprFor(e);
    const r = 7.0; // expression blend rate
    _browRaise = _damp(_browRaise, tgt.browRaise, r, dt);
    _browTilt = _damp(_browTilt, tgt.browTilt, r, dt);
    _eyeOpen = _damp(_eyeOpen, tgt.eyeOpen, r, dt);
    _lowerLid = _damp(_lowerLid, tgt.lowerLid, r, dt);
    _pupilDilate = _damp(_pupilDilate, tgt.pupil, r, dt);
    _mouthCurve = _damp(_mouthCurve, tgt.mouthCurve, r, dt);
    _mouthOpenBase = _damp(_mouthOpenBase, tgt.mouthOpen, r, dt);
    _heart = _damp(_heart, tgt.heart, 5, dt);
    _blush = _damp(_blush, tgt.blush, 5, dt);

    // Mouth: REAL lip-sync. Track the live voice-amplitude envelope directly
    // (raw snapshot value, not the smoothed one) with a perceptual curve so
    // quiet speech still opens the mouth, then apply a fast attack + slower
    // release so it snaps open on sound and closes cleanly between words.
    double mouthTarget = _mouthOpenBase;
    if (s.state == AssistantState.speaking) {
      final env = math.pow(s.aiLevel.clamp(0.0, 1.0), 0.6).toDouble();
      mouthTarget = math.max(_mouthOpenBase, env);
    } else if (s.state == AssistantState.listening) {
      mouthTarget = math.max(_mouthOpenBase, 0.1 * _micLevel);
    }
    mouthTarget = mouthTarget.clamp(0.0, 1.0);
    final mrate = mouthTarget > _mouth ? 34.0 : 15.0; // fast open, smooth close
    _mouth = _damp(_mouth, mouthTarget, mrate, dt);

    _updateBlink(dt);
    _updateWink(dt, s.state);
    _updateGaze(dt, s.state);
    _updateHead(dt, s.state);
    _updateFloat(dt, s.state);
    _updateParticles(dt, s.state);
    _updateRipple(dt, s.state);
    _updateWave(dt, s.state);

    _params.value = _build();
  }

  void _updateBlink(double dt) {
    if (_blinking) {
      _blinkPhase += dt / 0.15;
      if (_blinkPhase >= 1) {
        _blinking = false;
        _blink = 0;
        _blinkPhase = 0;
      } else {
        _blink = math.sin(_blinkPhase * math.pi);
      }
    } else {
      _blinkClock += dt;
      if (_blinkClock >= _nextBlink) {
        _blinking = true;
        _blinkClock = 0;
        _blinkPhase = 0;
        // Occasional quick double-blink feel via short interval.
        _nextBlink = 2.0 + _rng.nextDouble() * 4.0;
      }
    }
  }

  void _updateWink(double dt, AssistantState state) {
    // Only wink when relaxed (idle/neutral-ish) so it reads as playful.
    if (_winking) {
      _winkPhase += dt / 0.5;
      if (_winkPhase >= 1) {
        _winking = false;
        _wink = 0;
        _winkPhase = 0;
      } else {
        _wink = math.sin(_winkPhase * math.pi);
      }
    } else if (state == AssistantState.idle) {
      _winkClock += dt;
      if (_winkClock >= _nextWink) {
        _winking = true;
        _winkClock = 0;
        _winkPhase = 0;
        _nextWink = 14 + _rng.nextDouble() * 16;
      }
    }
  }

  void _updateGaze(double dt, AssistantState state) {
    _saccadeClock += dt;
    final interval = state == AssistantState.listening ? 1.1 : _nextSaccade;
    if (_saccadeClock >= interval) {
      _saccadeClock = 0;
      _nextSaccade = 1.4 + _rng.nextDouble() * 3.0;
      final spread = state == AssistantState.thinking ? 0.85 : 0.5;
      _pupilTX = (_rng.nextDouble() * 2 - 1) * spread;
      _pupilTY = (_rng.nextDouble() * 2 - 1) * spread * 0.55;
      if (state == AssistantState.thinking) {
        _pupilTY = -0.45 - _rng.nextDouble() * 0.3; // glance up, pondering
      }
    }
    _pupilX = _damp(_pupilX, _pupilTX, 9, dt);
    _pupilY = _damp(_pupilY, _pupilTY, 9, dt);
  }

  void _updateHead(double dt, AssistantState state) {
    // Turn follows gaze loosely (a head turning to look somewhere reads more
    // alive than eyes darting alone), plus a slow independent idle sway.
    final idleSway = math.sin(_breath * 0.31) * 0.05;
    final gazeFollow = _pupilX * 0.10;
    double turnTarget = idleSway + gazeFollow;

    double tiltTarget = _pupilY * 0.05;
    if (state == AssistantState.thinking) {
      tiltTarget += 0.06; // a slight curious/pondering tilt
    }

    _headTurn = _damp(_headTurn, turnTarget, 3.5, dt);
    _headTilt = _damp(_headTilt, tiltTarget, 3.5, dt);
  }

  void _updateFloat(double dt, AssistantState state) {
    // Gentle vertical bob; a touch more pronounced when idle/sleepy.
    final amp = state == AssistantState.idle ? 1.0 : 0.5;
    _floatY = math.sin(_breath) * widget.size * 0.012 * amp;
  }

  void _updateParticles(double dt, AssistantState state) {
    final want = state == AssistantState.thinking ? 16 : 0;
    while (_particles.length < want) {
      _particles.add(Particle(
        angle: _rng.nextDouble() * math.pi * 2,
        radius: 1,
        size: 1.6 + _rng.nextDouble() * 2.2,
        alpha: 0,
        speed: (0.8 + _rng.nextDouble() * 1.4) * (_rng.nextBool() ? 1 : -1),
        life: 0,
      ));
    }
    final rBase = widget.size * 0.30;
    for (final pt in _particles) {
      pt.angle += pt.speed * dt;
      pt.life += dt;
      pt.radius = rBase * (1.30 + 0.10 * math.sin(pt.life * 2 + pt.angle));
      final target = state == AssistantState.thinking ? 1.0 : 0.0;
      pt.alpha = _damp(pt.alpha, target, 6, dt);
      final px = widget.size / 2 + math.cos(pt.angle) * pt.radius;
      final py = widget.size / 2 + math.sin(pt.angle) * pt.radius;
      pt.trail.insert(0, Offset(px, py));
      if (pt.trail.length > 6) pt.trail.removeLast();
    }
    if (state != AssistantState.thinking) {
      _particles.removeWhere((p) => p.alpha < 0.02);
    }
  }

  void _updateRipple(double dt, AssistantState state) {
    if (state != _lastState) {
      _lastState = state;
      _rippleRadius = widget.size * 0.24;
      _rippleAlpha = 1.0;
    }
    if (_rippleAlpha > 0.01) {
      _rippleRadius += dt * widget.size * 0.9;
      _rippleAlpha = _damp(_rippleAlpha, 0, 4.5, dt);
    }
  }

  void _updateWave(double dt, AssistantState state) {
    final active = state == AssistantState.speaking;
    for (var i = 0; i < _wave.length; i++) {
      double target = 0;
      if (active) {
        final noise = 0.35 + 0.65 * (0.5 + 0.5 * math.sin(_t * 9 + i * 0.6));
        target = (_aiLevel * noise).clamp(0.0, 1.0);
      }
      _wave[i] = _damp(_wave[i], target, 18, dt);
    }
  }

  FaceParams _build() {
    final s = widget.snapshot;
    return FaceParams(
      primary: _primary,
      secondary: _secondary,
      state: s.state,
      browRaise: _browRaise,
      browTilt: _browTilt,
      eyeOpen: _eyeOpen,
      lowerLid: _lowerLid,
      pupilDilate: _pupilDilate,
      mouthCurve: _mouthCurve,
      mouthOpenBase: _mouthOpenBase,
      heart: _heart,
      blush: _blush,
      blink: _blink,
      wink: _wink,
      pupilX: _pupilX,
      pupilY: _pupilY,
      micLevel: _micLevel,
      aiLevel: _aiLevel,
      mouth: _mouth,
      headTurn: _headTurn,
      headTilt: _headTilt,
      breath: _breath,
      t: _t,
      floatY: _floatY,
      hudA: _hudA,
      hudB: _hudB,
      core: _core,
      rippleRadius: _rippleRadius,
      rippleAlpha: _rippleAlpha,
      micMuted: s.micMuted,
      particles: _particles,
      wave: _wave,
    );
  }

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: widget.size,
      height: widget.size,
      child: ValueListenableBuilder<FaceParams>(
        valueListenable: _params,
        builder: (context, params, _) => CustomPaint(
          painter: FacePainter(params),
          size: Size(widget.size, widget.size),
        ),
      ),
    );
  }
}
