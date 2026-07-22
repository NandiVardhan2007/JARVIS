import 'dart:async';

import 'package:flutter/material.dart';

import '../services/weather_service.dart';
import '../theme.dart';

/// Live weather panel. Auto-locates by IP (or a fixed [city]) and refreshes
/// every 10 minutes. Keyless via Open-Meteo.
class WeatherCard extends StatefulWidget {
  final String? city;
  const WeatherCard({super.key, this.city});

  @override
  State<WeatherCard> createState() => _WeatherCardState();
}

class _WeatherCardState extends State<WeatherCard> {
  final _service = WeatherService();
  Weather? _weather;
  String? _error;
  Timer? _timer;

  @override
  void initState() {
    super.initState();
    _load();
    _timer = Timer.periodic(const Duration(minutes: 10), (_) => _load());
  }

  @override
  void dispose() {
    _timer?.cancel();
    _service.dispose();
    super.dispose();
  }

  Future<void> _load() async {
    try {
      final w = await _service.fetch(city: widget.city);
      if (mounted) setState(() { _weather = w; _error = null; });
    } catch (e) {
      if (mounted) setState(() => _error = 'Weather unavailable');
    }
  }

  @override
  Widget build(BuildContext context) {
    const accent = Color(0xFF00B4FF);
    return Container(
      width: 280,
      padding: const EdgeInsets.all(18),
      decoration: JarvisTheme.glassCard(accent),
      child: _weather == null ? _placeholder() : _content(_weather!),
    );
  }

  Widget _placeholder() {
    return SizedBox(
      height: 150,
      child: Center(
        child: _error != null
            ? Text(_error!, style: const TextStyle(color: JarvisTheme.textDim))
            : const CircularProgressIndicator(strokeWidth: 2, color: Color(0xFF00B4FF)),
      ),
    );
  }

  Widget _content(Weather w) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      mainAxisSize: MainAxisSize.min,
      children: [
        Row(
          children: [
            const Icon(Icons.place_outlined, size: 15, color: JarvisTheme.textDim),
            const SizedBox(width: 4),
            Expanded(
              child: Text(
                w.city,
                overflow: TextOverflow.ellipsis,
                style: const TextStyle(
                  color: JarvisTheme.textPrimary,
                  fontWeight: FontWeight.w600,
                  fontSize: 14,
                ),
              ),
            ),
          ],
        ),
        const SizedBox(height: 10),
        Row(
          crossAxisAlignment: CrossAxisAlignment.center,
          children: [
            Text(w.icon, style: const TextStyle(fontSize: 46)),
            const SizedBox(width: 12),
            Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  '${w.temp.round()}°',
                  style: const TextStyle(
                    color: JarvisTheme.textPrimary,
                    fontSize: 42,
                    fontWeight: FontWeight.w300,
                    height: 1.0,
                  ),
                ),
                Text(
                  w.description,
                  style: const TextStyle(color: JarvisTheme.textDim, fontSize: 13),
                ),
              ],
            ),
          ],
        ),
        const SizedBox(height: 6),
        Text(
          'Feels ${w.feelsLike.round()}°   ·   💧 ${w.humidity}%   ·   🌬 ${w.wind.round()} km/h',
          style: const TextStyle(color: JarvisTheme.textDim, fontSize: 11.5),
        ),
        const SizedBox(height: 14),
        const Divider(color: Color(0x22394B6E), height: 1),
        const SizedBox(height: 12),
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            for (final d in w.daily.skip(1).take(3)) _dayCell(d),
          ],
        ),
      ],
    );
  }

  Widget _dayCell(WeatherDay d) {
    return Column(
      children: [
        Text(d.label,
            style: const TextStyle(color: JarvisTheme.textDim, fontSize: 11)),
        const SizedBox(height: 4),
        Text(wmoIcon(d.code, true), style: const TextStyle(fontSize: 20)),
        const SizedBox(height: 4),
        Text(
          '${d.tMax.round()}° / ${d.tMin.round()}°',
          style: const TextStyle(
              color: JarvisTheme.textPrimary, fontSize: 11.5, fontWeight: FontWeight.w500),
        ),
      ],
    );
  }
}
