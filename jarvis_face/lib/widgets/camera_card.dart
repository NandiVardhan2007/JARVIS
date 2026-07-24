import 'dart:async';
import 'package:flutter/material.dart';
import '../theme.dart';

/// Live Visual Feed widget connecting to JARVIS MJPEG video stream (http://127.0.0.1:5005/snapshot.jpg).
class CameraCard extends StatefulWidget {
  final VoidCallback? onStartWebcam;
  final VoidCallback? onStopWebcam;

  const CameraCard({
    super.key,
    this.onStartWebcam,
    this.onStopWebcam,
  });

  @override
  State<CameraCard> createState() => _CameraCardState();
}

class _CameraCardState extends State<CameraCard> {
  bool _isOnline = false;
  Timer? _frameTimer;
  int _seq = 0;

  @override
  void initState() {
    super.initState();
    // Poll snapshot frames at ~25fps (40ms interval) for smooth live video
    _frameTimer = Timer.periodic(const Duration(milliseconds: 40), (_) {
      if (mounted) {
        setState(() {
          _seq++;
        });
      }
    });
  }

  @override
  void dispose() {
    _frameTimer?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      width: 320,
      decoration: JarvisTheme.glassCard(const Color(0xFF00D4FF)),
      padding: const EdgeInsets.all(14),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisSize: MainAxisSize.min,
        children: [
          Row(
            children: [
              const Icon(
                Icons.videocam_rounded,
                color: Color(0xFF00D4FF),
                size: 18,
              ),
              const SizedBox(width: 8),
              const Text(
                'VISUAL CORE',
                style: TextStyle(
                  color: JarvisTheme.textPrimary,
                  fontSize: 12,
                  fontWeight: FontWeight.w700,
                  letterSpacing: 2,
                ),
              ),
              const Spacer(),
              Container(
                width: 8,
                height: 8,
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  color: _isOnline ? const Color(0xFF32D74B) : Colors.orange,
                ),
              ),
              const SizedBox(width: 4),
              Text(
                _isOnline ? 'LIVE' : 'STANDBY',
                style: TextStyle(
                  color: _isOnline ? const Color(0xFF32D74B) : Colors.orange,
                  fontSize: 10,
                  fontWeight: FontWeight.w700,
                ),
              ),
            ],
          ),
          const SizedBox(height: 10),
          ClipRRect(
            borderRadius: BorderRadius.circular(10),
            child: Container(
              height: 180,
              width: double.infinity,
              color: Colors.black45,
              child: Image.network(
                'http://127.0.0.1:5005/snapshot.jpg?seq=$_seq',
                fit: BoxFit.cover,
                gaplessPlayback: true,
                errorBuilder: (context, error, stackTrace) {
                  WidgetsBinding.instance.addPostFrameCallback((_) {
                    if (_isOnline && mounted) {
                      setState(() => _isOnline = false);
                    }
                  });
                  return const Center(
                    child: Padding(
                      padding: EdgeInsets.all(12),
                      child: Column(
                        mainAxisAlignment: MainAxisAlignment.center,
                        children: [
                          Icon(
                            Icons.videocam_off_outlined,
                            color: JarvisTheme.textDim,
                            size: 32,
                          ),
                          SizedBox(height: 8),
                          Text(
                            'Webcam Feed Offline',
                            style: TextStyle(
                              color: JarvisTheme.textPrimary,
                              fontSize: 12,
                              fontWeight: FontWeight.w600,
                            ),
                          ),
                          SizedBox(height: 4),
                          Text(
                            'Say "start webcam" or tap button below',
                            textAlign: TextAlign.center,
                            style: TextStyle(
                              color: JarvisTheme.textDim,
                              fontSize: 10,
                            ),
                          ),
                        ],
                      ),
                    ),
                  );
                },
                loadingBuilder: (context, child, loadingProgress) {
                  if (loadingProgress == null) {
                    WidgetsBinding.instance.addPostFrameCallback((_) {
                      if (!_isOnline && mounted) {
                        setState(() => _isOnline = true);
                      }
                    });
                    return child;
                  }
                  return child;
                },
              ),
            ),
          ),
          const SizedBox(height: 10),
          Row(
            children: [
              Expanded(
                child: OutlinedButton.icon(
                  onPressed: widget.onStartWebcam,
                  style: OutlinedButton.styleFrom(
                    padding: const EdgeInsets.symmetric(vertical: 8),
                    side: BorderSide(
                      color: const Color(0xFF00D4FF).op(0.4),
                    ),
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(8),
                    ),
                  ),
                  icon: const Icon(Icons.play_arrow_rounded, size: 16, color: Color(0xFF00D4FF)),
                  label: const Text(
                    'Start Cam',
                    style: TextStyle(fontSize: 11, color: Color(0xFF00D4FF)),
                  ),
                ),
              ),
              const SizedBox(width: 8),
              Expanded(
                child: OutlinedButton.icon(
                  onPressed: widget.onStopWebcam,
                  style: OutlinedButton.styleFrom(
                    padding: const EdgeInsets.symmetric(vertical: 8),
                    side: BorderSide(
                      color: Colors.redAccent.op(0.4),
                    ),
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(8),
                    ),
                  ),
                  icon: const Icon(Icons.stop_rounded, size: 16, color: Colors.redAccent),
                  label: const Text(
                    'Stop Cam',
                    style: TextStyle(fontSize: 11, color: Colors.redAccent),
                  ),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }
}
