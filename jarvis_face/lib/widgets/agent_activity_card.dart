import 'package:flutter/material.dart';
import '../models/jarvis_state.dart';
import '../theme.dart';

/// Live Agent Activity & Tool Execution Stream Widget.
/// Displays what tool/sub-agent JARVIS is currently running in real-time,
/// along with a scrolling log of recent actions.
class AgentActivityCard extends StatefulWidget {
  final JarvisSnapshot snapshot;
  const AgentActivityCard({super.key, required this.snapshot});

  @override
  State<AgentActivityCard> createState() => _AgentActivityCardState();
}

class _AgentActivityCardState extends State<AgentActivityCard> {
  final List<ActivityItem> _logs = [];
  String _lastToolKey = '';

  @override
  void didUpdateWidget(covariant AgentActivityCard oldWidget) {
    super.didUpdateWidget(oldWidget);
    final s = widget.snapshot;
    final tool = s.toolName.trim();
    final desc = s.description.trim();
    final currentKey = '$tool:$desc';

    if (currentKey.isNotEmpty && currentKey != _lastToolKey && s.state != AssistantState.idle) {
      _lastToolKey = currentKey;
      final nowStr = _formatTime(DateTime.now());
      final cat = categoryStyle(s.category);

      setState(() {
        _logs.insert(
          0,
          ActivityItem(
            time: nowStr,
            icon: cat.icon,
            color: cat.color,
            title: tool.isNotEmpty ? tool.toUpperCase() : cat.label.toUpperCase(),
            description: desc.isNotEmpty ? desc : 'Executing active command...',
          ),
        );
        if (_logs.length > 5) {
          _logs.removeLast();
        }
      });
    }
  }

  String _formatTime(DateTime dt) {
    final h = dt.hour.toString().padLeft(2, '0');
    final m = dt.minute.toString().padLeft(2, '0');
    final s = dt.second.toString().padLeft(2, '0');
    return '$h:$m:$s';
  }

  @override
  Widget build(BuildContext context) {
    final s = widget.snapshot;
    final accent = s.colors.primary;
    final cat = categoryStyle(s.category);
    final isRunning = s.state == AssistantState.thinking ||
        s.toolName.isNotEmpty ||
        (s.category != null && s.category!.isNotEmpty);

    final activeToolName = s.toolName.isNotEmpty
        ? s.toolName.toUpperCase()
        : (s.category != null && s.category!.isNotEmpty
            ? s.category!.toUpperCase()
            : 'AGENT CORE');

    final activeDesc = s.description.isNotEmpty
        ? s.description
        : (s.state == AssistantState.thinking ? 'Processing user request...' : 'Standby / Awaiting input');

    return Container(
      width: 320,
      decoration: JarvisTheme.glassCard(accent),
      padding: const EdgeInsets.all(14),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisSize: MainAxisSize.min,
        children: [
          Row(
            children: [
              Icon(
                Icons.memory_rounded,
                color: accent,
                size: 18,
              ),
              const Expanded(
                child: Text(
                  'AGENT EXECUTION STREAM',
                  overflow: TextOverflow.ellipsis,
                  style: TextStyle(
                    color: JarvisTheme.textPrimary,
                    fontSize: 11,
                    fontWeight: FontWeight.w800,
                    letterSpacing: 1.5,
                  ),
                ),
              ),
              const SizedBox(width: 6),

              Container(
                width: 7,
                height: 7,
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  color: isRunning ? accent : JarvisTheme.textDim,
                  boxShadow: isRunning
                      ? [
                          BoxShadow(
                            color: accent.op(0.8),
                            blurRadius: 6,
                            spreadRadius: 1,
                          )
                        ]
                      : null,
                ),
              ),
              const SizedBox(width: 4),
              Text(
                isRunning ? 'ACTIVE' : 'IDLE',
                style: TextStyle(
                  color: isRunning ? accent : JarvisTheme.textDim,
                  fontSize: 9.5,
                  fontWeight: FontWeight.w700,
                ),
              ),
            ],
          ),
          const SizedBox(height: 10),

          // Active Tool Status Header Box
          AnimatedContainer(
            duration: const Duration(milliseconds: 300),
            padding: const EdgeInsets.all(10),
            decoration: BoxDecoration(
              color: accent.op(0.1),
              borderRadius: BorderRadius.circular(10),
              border: Border.all(color: accent.op(0.3), width: 1),
            ),
            child: Row(
              children: [
                Container(
                  width: 32,
                  height: 32,
                  decoration: BoxDecoration(
                    color: cat.color.op(0.2),
                    shape: BoxShape.circle,
                    border: Border.all(color: cat.color.op(0.5), width: 1),
                  ),
                  child: Center(
                    child: Text(
                      cat.icon,
                      style: TextStyle(
                        color: cat.color,
                        fontSize: 14,
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                  ),
                ),
                const SizedBox(width: 10),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        activeToolName,
                        style: TextStyle(
                          color: accent,
                          fontSize: 10.5,
                          fontWeight: FontWeight.w800,
                          letterSpacing: 1.2,
                        ),
                      ),
                      const SizedBox(height: 2),
                      Text(
                        activeDesc,
                        maxLines: 2,
                        overflow: TextOverflow.ellipsis,
                        style: const TextStyle(
                          color: JarvisTheme.textPrimary,
                          fontSize: 11.5,
                          height: 1.25,
                        ),
                      ),
                    ],
                  ),
                ),
              ],
            ),
          ),

          if (_logs.isNotEmpty) ...[
            const SizedBox(height: 10),
            const Text(
              'RECENT EXECUTION LOG',
              style: TextStyle(
                color: JarvisTheme.textDim,
                fontSize: 9,
                fontWeight: FontWeight.w700,
                letterSpacing: 1.5,
              ),
            ),
            const SizedBox(height: 6),
            Column(
              children: _logs.map((log) => _logTile(log)).toList(),
            ),
          ],
        ],
      ),
    );
  }

  Widget _logTile(ActivityItem item) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 3),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            item.time,
            style: const TextStyle(
              color: JarvisTheme.textDim,
              fontSize: 9.5,
              fontFamily: 'monospace',
            ),
          ),
          const SizedBox(width: 6),
          Text(
            item.icon,
            style: TextStyle(color: item.color, fontSize: 10),
          ),
          const SizedBox(width: 6),
          Expanded(
            child: RichText(
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              text: TextSpan(
                style: const TextStyle(fontSize: 10.5),
                children: [
                  TextSpan(
                    text: '${item.title}: ',
                    style: TextStyle(
                      color: item.color,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                  TextSpan(
                    text: item.description,
                    style: const TextStyle(color: JarvisTheme.textDim),
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class ActivityItem {
  final String time;
  final String icon;
  final Color color;
  final String title;
  final String description;

  const ActivityItem({
    required this.time,
    required this.icon,
    required this.color,
    required this.title,
    required this.description,
  });
}
