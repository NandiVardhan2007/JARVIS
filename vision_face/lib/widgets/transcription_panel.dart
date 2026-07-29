import 'package:flutter/material.dart';

import '../models/vision_state.dart';
import '../theme.dart';

/// An upgraded live-transcription panel:
/// - State chip with glowing active indicator & animated audio waveform bars
/// - Active Tool & Category badge when VISION executes background tools
/// - Glowing glassmorphism panel with smooth accent color transitions
/// - Typewriter reveal for VISION replies with terminal caret
class TranscriptionPanel extends StatefulWidget {
  final VisionSnapshot snapshot;
  const TranscriptionPanel({super.key, required this.snapshot});

  @override
  State<TranscriptionPanel> createState() => _TranscriptionPanelState();
}

class _TranscriptionPanelState extends State<TranscriptionPanel>
    with SingleTickerProviderStateMixin {
  late final AnimationController _anim;

  @override
  void initState() {
    super.initState();
    _anim = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 1000),
    )..repeat(reverse: true);
  }

  @override
  void dispose() {
    _anim.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final s = widget.snapshot;
    final accent = s.colors.primary;
    final you = s.transcript.trim();
    final reply = s.response.trim();
    final showCaret = s.state == AssistantState.speaking;
    final tool = s.toolName.trim();
    final cat = (s.category ?? '').trim();
    final activeTool = tool.isNotEmpty ? tool : (cat.isNotEmpty ? cat : '');






    return ConstrainedBox(
      constraints: const BoxConstraints(maxWidth: 680),
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 350),
        padding: const EdgeInsets.fromLTRB(22, 16, 22, 18),
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(22),
          gradient: LinearGradient(
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
            colors: [
              accent.op(0.08),
              Colors.white.op(0.02),
            ],
          ),
          border: Border.all(color: accent.op(0.35), width: 1.2),
          boxShadow: [
            BoxShadow(
              color: accent.op(0.15),
              blurRadius: 28,
              spreadRadius: -4,
            ),
          ],
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.center,
          children: [
            Row(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                _chip(s, accent),
                if (activeTool.isNotEmpty) ...[
                  const SizedBox(width: 10),
                  _toolBadge(activeTool, accent),
                ],
              ],
            ),
            const SizedBox(height: 14),

            // Live Audio Waveform visualizer bars when active
            if (s.state != AssistantState.idle) ...[
              _WaveformBars(color: accent, active: true),
              const SizedBox(height: 12),
            ],

            if (you.isNotEmpty) ...[
              _line(
                label: 'YOU',
                text: you,
                color: VisionTheme.textDim,
                labelColor: accent,
                dim: true,
              ),
              const SizedBox(height: 12),
            ],
            _replyLine(reply, reply, showCaret, accent, s),
          ],
        ),
      ),
    );
  }

  Widget _toolBadge(String toolName, Color accent) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 3),
      decoration: BoxDecoration(
        color: accent.op(0.15),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: accent.op(0.4), width: 1),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(Icons.build_circle_outlined, size: 12, color: accent),
          const SizedBox(width: 4),
          Text(
            toolName.toUpperCase(),
            style: TextStyle(
              color: accent,
              fontSize: 9.5,
              fontWeight: FontWeight.w700,
              letterSpacing: 1.5,
            ),
          ),
        ],
      ),
    );
  }

  Widget _chip(VisionSnapshot s, Color accent) {
    final label = switch (s.state) {
      AssistantState.listening => 'LISTENING',
      AssistantState.thinking => 'THINKING',
      AssistantState.speaking => 'SPEAKING',
      AssistantState.input => 'COMMAND',
      AssistantState.alert => 'ALERT',
      AssistantState.idle => s.connected ? 'ONLINE' : 'DEMO',
    };

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
      decoration: BoxDecoration(
        color: accent.op(0.12),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: accent.op(0.3), width: 1),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          _PulseDot(color: accent, active: s.state != AssistantState.idle),
          const SizedBox(width: 8),
          Text(
            label,
            style: TextStyle(
              color: accent,
              fontSize: 11,
              fontWeight: FontWeight.w800,
              letterSpacing: 2.2,
            ),
          ),
        ],
      ),
    );
  }

  Widget _replyLine(
      String revealed, String full, bool caret, Color accent, VisionSnapshot s) {
    if (full.isEmpty) {
      final placeholder = switch (s.state) {
        AssistantState.listening => 'Listening…',
        AssistantState.thinking => (s.description.isNotEmpty ? s.description : 'Thinking…'),
        AssistantState.idle => s.connected ? 'Ready when you are.' : 'Offline · demo mode',
        _ => '…',
      };
      return Text(
        placeholder,
        textAlign: TextAlign.center,
        style: const TextStyle(
          color: VisionTheme.textDim,
          fontSize: 15,
          height: 1.4,
          fontStyle: FontStyle.italic,
        ),
      );
    }
    return _line(
      label: 'VISION',
      text: revealed,
      caret: caret,
      color: VisionTheme.textPrimary,
      labelColor: accent,
    );
  }

  Widget _line({
    required String label,
    required String text,
    required Color color,
    required Color labelColor,
    bool caret = false,
    bool dim = false,
  }) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.center,
      children: [
        Text(
          label,
          style: TextStyle(
            color: labelColor.op(dim ? 0.6 : 0.9),
            fontSize: 10,
            fontWeight: FontWeight.w800,
            letterSpacing: 2.0,
          ),
        ),
        const SizedBox(height: 5),
        RichText(
          textAlign: TextAlign.center,
          text: TextSpan(
            style: TextStyle(
              color: color,
              fontSize: dim ? 15 : 18.5,
              height: 1.45,
              fontWeight: dim ? FontWeight.w400 : FontWeight.w500,
            ),
            children: [
              TextSpan(text: text),
              if (caret)
                TextSpan(
                  text: ' ▌',
                  style: TextStyle(color: labelColor, fontWeight: FontWeight.bold),
                ),
            ],
          ),
        ),
      ],
    );
  }
}

/// Animated live audio waveform bars.
class _WaveformBars extends StatefulWidget {
  final Color color;
  final bool active;
  const _WaveformBars({required this.color, required this.active});

  @override
  State<_WaveformBars> createState() => _WaveformBarsState();
}

class _WaveformBarsState extends State<_WaveformBars> with SingleTickerProviderStateMixin {
  late final AnimationController _ctrl;

  @override
  void initState() {
    super.initState();
    _ctrl = AnimationController(vsync: this, duration: const Duration(milliseconds: 600))
      ..repeat(reverse: true);
  }

  @override
  void dispose() {
    _ctrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    if (!widget.active) return const SizedBox.shrink();
    return AnimatedBuilder(
      animation: _ctrl,
      builder: (context, _) {
        final val = _ctrl.value;
        return Row(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.center,
          children: [
            _bar(12 + 10 * val),
            const SizedBox(width: 4),
            _bar(18 - 8 * val),
            const SizedBox(width: 4),
            _bar(8 + 14 * val),
            const SizedBox(width: 4),
            _bar(16 - 10 * val),
            const SizedBox(width: 4),
            _bar(10 + 12 * val),
          ],
        );
      },
    );
  }

  Widget _bar(double height) {
    return Container(
      width: 3.5,
      height: height,
      decoration: BoxDecoration(
        color: widget.color.op(0.85),
        borderRadius: BorderRadius.circular(3),
        boxShadow: [
          BoxShadow(
            color: widget.color.op(0.4),
            blurRadius: 4,
          ),
        ],
      ),
    );
  }
}

/// A soft pulsing status dot.
class _PulseDot extends StatefulWidget {
  final Color color;
  final bool active;
  const _PulseDot({required this.color, required this.active});

  @override
  State<_PulseDot> createState() => _PulseDotState();
}

class _PulseDotState extends State<_PulseDot> with SingleTickerProviderStateMixin {
  late final AnimationController _c;

  @override
  void initState() {
    super.initState();
    _c = AnimationController(vsync: this, duration: const Duration(milliseconds: 1200))
      ..repeat(reverse: true);
  }

  @override
  void dispose() {
    _c.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: _c,
      builder: (_, __) {
        final glow = widget.active ? (0.4 + 0.6 * _c.value) : 0.6;
        return Container(
          width: 8,
          height: 8,
          decoration: BoxDecoration(
            shape: BoxShape.circle,
            color: widget.color,
            boxShadow: [
              BoxShadow(color: widget.color.op(glow), blurRadius: 8, spreadRadius: 1),
            ],
          ),
        );
      },
    );
  }
}
