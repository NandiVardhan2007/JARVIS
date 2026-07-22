import 'package:flutter/material.dart';

import '../models/jarvis_state.dart';
import '../theme.dart';

/// A clean live-transcription panel: a state chip, the user's last utterance
/// ("You"), and JARVIS's reply revealed with a typewriter effect and a blinking
/// caret. Designed to read clearly at a glance.
class TranscriptionPanel extends StatefulWidget {
  final JarvisSnapshot snapshot;
  const TranscriptionPanel({super.key, required this.snapshot});

  @override
  State<TranscriptionPanel> createState() => _TranscriptionPanelState();
}

class _TranscriptionPanelState extends State<TranscriptionPanel>
    with SingleTickerProviderStateMixin {
  late final AnimationController _caret;

  @override
  void initState() {
    super.initState();
    _caret = AnimationController(vsync: this, duration: const Duration(milliseconds: 700))
      ..repeat(reverse: true);
  }

  @override
  void dispose() {
    _caret.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final s = widget.snapshot;
    final accent = s.colors.primary;
    final you = s.transcript.trim();
    final reply = s.response.trim();
    final showCaret = s.state == AssistantState.speaking;

    return ConstrainedBox(
      constraints: const BoxConstraints(maxWidth: 640),
      child: Container(
        padding: const EdgeInsets.fromLTRB(22, 16, 22, 18),
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(22),
          gradient: LinearGradient(
            begin: Alignment.topCenter,
            end: Alignment.bottomCenter,
            colors: [Colors.white.op(0.05), Colors.white.op(0.015)],
          ),
          border: Border.all(color: accent.op(0.22)),
          boxShadow: [
            BoxShadow(color: accent.op(0.10), blurRadius: 26, spreadRadius: -8),
          ],
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.center,
          children: [
            _chip(s, accent),
            const SizedBox(height: 14),
            if (you.isNotEmpty) ...[
              _line(label: 'YOU', text: you, color: JarvisTheme.textDim, labelColor: accent, dim: true),
              const SizedBox(height: 10),
            ],
            _replyLine(reply, reply, showCaret, accent, s),
          ],
        ),
      ),
    );
  }

  Widget _chip(JarvisSnapshot s, Color accent) {
    final label = switch (s.state) {
      AssistantState.listening => 'LISTENING',
      AssistantState.thinking => 'THINKING',
      AssistantState.speaking => 'SPEAKING',
      AssistantState.input => 'COMMAND',
      AssistantState.alert => 'ALERT',
      AssistantState.idle => s.connected ? 'ONLINE' : 'DEMO',
    };
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        _PulseDot(color: accent, active: s.state != AssistantState.idle),
        const SizedBox(width: 8),
        Text(
          label,
          style: TextStyle(
            color: accent,
            fontSize: 11,
            fontWeight: FontWeight.w700,
            letterSpacing: 2.5,
          ),
        ),
      ],
    );
  }

  Widget _replyLine(
      String revealed, String full, bool caret, Color accent, JarvisSnapshot s) {
    // While thinking/idle with no reply, show a soft status line.
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
        style: const TextStyle(color: JarvisTheme.textDim, fontSize: 16, height: 1.35),
      );
    }
    return _line(
      label: 'JARVIS',
      text: revealed,
      caret: caret,
      color: JarvisTheme.textPrimary,
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
            color: labelColor.op(dim ? 0.5 : 0.85),
            fontSize: 9.5,
            fontWeight: FontWeight.w800,
            letterSpacing: 2.0,
          ),
        ),
        const SizedBox(height: 4),
        RichText(
          textAlign: TextAlign.center,
          text: TextSpan(
            style: TextStyle(
              color: color,
              fontSize: dim ? 15 : 19,
              height: 1.4,
              fontWeight: dim ? FontWeight.w400 : FontWeight.w500,
            ),
            children: [
              TextSpan(text: text),
              if (caret)
                TextSpan(
                  text: '▌',
                  style: TextStyle(color: labelColor),
                ),
            ],
          ),
        ),
      ],
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
