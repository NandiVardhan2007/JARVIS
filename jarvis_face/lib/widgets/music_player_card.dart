import 'dart:math' as math;

import 'package:flutter/material.dart';

import '../models/jarvis_state.dart';
import '../theme.dart';

/// Now-playing panel driven by the JARVIS media tool. Controls send real
/// play/pause + stop commands back through the bridge to python-vlc.
class MusicPlayerCard extends StatelessWidget {
  final NowPlaying? nowPlaying;

  /// 0..1 audio activity used for the equalizer shimmer.
  final double level;
  final VoidCallback onPlayPause;
  final VoidCallback onStop;

  const MusicPlayerCard({
    super.key,
    required this.nowPlaying,
    required this.level,
    required this.onPlayPause,
    required this.onStop,
  });

  @override
  Widget build(BuildContext context) {
    const accent = Color(0xFFFF2D55);
    final np = nowPlaying;
    return Container(
      width: 280,
      padding: const EdgeInsets.all(18),
      decoration: JarvisTheme.glassCard(accent),
      child: np == null ? _idle() : _content(np, accent),
    );
  }

  Widget _idle() {
    return const SizedBox(
      height: 120,
      child: Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(Icons.music_note_outlined, color: JarvisTheme.textDim, size: 30),
            SizedBox(height: 8),
            Text('Nothing playing',
                style: TextStyle(color: JarvisTheme.textDim, fontSize: 13)),
          ],
        ),
      ),
    );
  }

  Widget _content(NowPlaying np, Color accent) {
    return Column(
      mainAxisSize: MainAxisSize.min,
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            _artwork(np, accent),
            const SizedBox(width: 14),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text('NOW PLAYING',
                      style: TextStyle(
                          color: Color(0xFFFF2D55),
                          fontSize: 10,
                          letterSpacing: 1.5,
                          fontWeight: FontWeight.w700)),
                  const SizedBox(height: 6),
                  Text(
                    np.title,
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                    style: const TextStyle(
                        color: JarvisTheme.textPrimary,
                        fontSize: 15,
                        fontWeight: FontWeight.w600,
                        height: 1.15),
                  ),
                  const SizedBox(height: 2),
                  Text(
                    np.artist,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: const TextStyle(color: JarvisTheme.textDim, fontSize: 12.5),
                  ),
                ],
              ),
            ),
          ],
        ),
        const SizedBox(height: 14),
        _Equalizer(level: np.playing ? level : 0, color: accent),
        const SizedBox(height: 10),
        Row(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            _controlButton(
              icon: np.playing ? Icons.pause_rounded : Icons.play_arrow_rounded,
              onTap: onPlayPause,
              filled: true,
              accent: accent,
            ),
            const SizedBox(width: 18),
            _controlButton(icon: Icons.stop_rounded, onTap: onStop, accent: accent),
          ],
        ),
      ],
    );
  }

  Widget _artwork(NowPlaying np, Color accent) {
    final img = np.imageUrl;
    return Container(
      width: 60,
      height: 60,
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(12),
        color: accent.op(0.15),
        boxShadow: [
          BoxShadow(color: accent.op(0.3), blurRadius: 16, spreadRadius: -4),
        ],
      ),
      clipBehavior: Clip.antiAlias,
      child: (img != null && img.isNotEmpty)
          ? Image.network(
              img,
              fit: BoxFit.cover,
              errorBuilder: (_, __, ___) => _artFallback(accent),
            )
          : _artFallback(accent),
    );
  }

  Widget _artFallback(Color accent) =>
      Center(child: Icon(Icons.album, color: accent.op(0.8), size: 30));

  Widget _controlButton({
    required IconData icon,
    required VoidCallback onTap,
    required Color accent,
    bool filled = false,
  }) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        width: filled ? 46 : 40,
        height: filled ? 46 : 40,
        decoration: BoxDecoration(
          shape: BoxShape.circle,
          color: filled ? accent : Colors.white.op(0.06),
          border: Border.all(color: accent.op(0.4)),
        ),
        child: Icon(icon,
            color: filled ? Colors.white : JarvisTheme.textPrimary, size: filled ? 26 : 22),
      ),
    );
  }
}

/// Small animated equalizer that shimmers with [level].
class _Equalizer extends StatefulWidget {
  final double level;
  final Color color;
  const _Equalizer({required this.level, required this.color});

  @override
  State<_Equalizer> createState() => _EqualizerState();
}

class _EqualizerState extends State<_Equalizer>
    with SingleTickerProviderStateMixin {
  late final AnimationController _c;

  @override
  void initState() {
    super.initState();
    _c = AnimationController(vsync: this, duration: const Duration(seconds: 2))
      ..repeat();
  }

  @override
  void dispose() {
    _c.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      height: 26,
      child: AnimatedBuilder(
        animation: _c,
        builder: (_, __) => CustomPaint(
          size: const Size(double.infinity, 26),
          painter: _EqPainter(_c.value * math.pi * 2, widget.level, widget.color),
        ),
      ),
    );
  }
}

class _EqPainter extends CustomPainter {
  final double t;
  final double level;
  final Color color;
  _EqPainter(this.t, this.level, this.color);

  @override
  void paint(Canvas canvas, Size size) {
    const bars = 28;
    final gap = size.width / bars;
    final paint = Paint()..strokeCap = StrokeCap.round..strokeWidth = gap * 0.55;
    for (var i = 0; i < bars; i++) {
      final n = 0.5 + 0.5 * math.sin(t * 3 + i * 0.6);
      final base = 0.12 + 0.88 * level;
      final h = (2 + base * n * (size.height - 2)).clamp(2.0, size.height);
      final x = gap * (i + 0.5);
      paint.color = color.op(0.35 + 0.5 * n * level.clamp(0.05, 1.0));
      canvas.drawLine(
        Offset(x, size.height / 2 - h / 2),
        Offset(x, size.height / 2 + h / 2),
        paint,
      );
    }
  }

  @override
  bool shouldRepaint(covariant _EqPainter old) => true;
}
