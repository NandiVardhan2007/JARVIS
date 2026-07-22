import 'dart:convert';

import 'package:http/http.dart' as http;

import '../config.dart';

/// A single day in the short forecast.
class WeatherDay {
  final DateTime date;
  final double tMax;
  final double tMin;
  final int code;

  WeatherDay(this.date, this.tMax, this.tMin, this.code);

  String get label {
    const days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
    return days[(date.weekday - 1) % 7];
  }
}

/// Current conditions + a few days ahead. All keyless via Open-Meteo — the same
/// source the JARVIS `Tools/weather.py` already uses.
class Weather {
  final String city;
  final double temp;
  final double feelsLike;
  final int humidity;
  final double wind;
  final int code;
  final bool isDay;
  final List<WeatherDay> daily;

  Weather({
    required this.city,
    required this.temp,
    required this.feelsLike,
    required this.humidity,
    required this.wind,
    required this.code,
    required this.isDay,
    required this.daily,
  });

  String get description => wmoDescription(code);
  String get icon => wmoIcon(code, isDay);
}

class WeatherService {
  final http.Client _client = http.Client();

  /// Fetch weather for [city]; when null, auto-locates via IP.
  Future<Weather> fetch({String? city}) async {
    double lat, lon;
    String resolvedCity;

    if (city != null && city.trim().isNotEmpty) {
      final geo = await _geocode(city.trim());
      lat = geo.$1;
      lon = geo.$2;
      resolvedCity = geo.$3;
    } else {
      final loc = await _ipLocate();
      lat = loc.$1;
      lon = loc.$2;
      resolvedCity = loc.$3;
    }

    final uri = Uri.parse(
      'https://api.open-meteo.com/v1/forecast'
      '?latitude=$lat&longitude=$lon'
      '&current=temperature_2m,apparent_temperature,relative_humidity_2m,'
      'weather_code,wind_speed_10m,is_day'
      '&daily=temperature_2m_max,temperature_2m_min,weather_code'
      '&timezone=auto&forecast_days=4',
    );
    final resp = await _client.get(uri).timeout(const Duration(seconds: 8));
    if (resp.statusCode != 200) {
      throw Exception('Weather API ${resp.statusCode}');
    }
    final j = jsonDecode(resp.body) as Map<String, dynamic>;
    final cur = j['current'] as Map<String, dynamic>;
    final daily = j['daily'] as Map<String, dynamic>;

    final times = (daily['time'] as List).cast<String>();
    final maxs = (daily['temperature_2m_max'] as List).cast<num>();
    final mins = (daily['temperature_2m_min'] as List).cast<num>();
    final codes = (daily['weather_code'] as List).cast<num>();
    final days = <WeatherDay>[];
    for (var i = 0; i < times.length; i++) {
      days.add(WeatherDay(
        DateTime.parse(times[i]),
        maxs[i].toDouble(),
        mins[i].toDouble(),
        codes[i].toInt(),
      ));
    }

    return Weather(
      city: resolvedCity,
      temp: (cur['temperature_2m'] as num).toDouble(),
      feelsLike: (cur['apparent_temperature'] as num).toDouble(),
      humidity: (cur['relative_humidity_2m'] as num).toInt(),
      wind: (cur['wind_speed_10m'] as num).toDouble(),
      code: (cur['weather_code'] as num).toInt(),
      isDay: (cur['is_day'] as num).toInt() == 1,
      daily: days,
    );
  }

  Future<(double, double, String)> _geocode(String name) async {
    final uri = Uri.parse(
      'https://geocoding-api.open-meteo.com/v1/search'
      '?name=${Uri.encodeComponent(name)}&count=5&language=en&format=json',
    );
    final resp = await _client.get(uri).timeout(const Duration(seconds: 8));
    final j = jsonDecode(resp.body) as Map<String, dynamic>;
    final results = (j['results'] as List?)?.cast<Map<String, dynamic>>();
    if (results == null || results.isEmpty) {
      throw Exception('City not found: $name');
    }
    // Prefer a match in the configured country, if one is set.
    final hint = JarvisConfig.weatherCountry.trim().toLowerCase();
    Map<String, dynamic> r = results.first;
    if (hint.isNotEmpty) {
      for (final cand in results) {
        final cc = (cand['country_code'] ?? '').toString().toLowerCase();
        final cn = (cand['country'] ?? '').toString().toLowerCase();
        if (cc == hint || cn == hint) {
          r = cand;
          break;
        }
      }
    }
    return (
      (r['latitude'] as num).toDouble(),
      (r['longitude'] as num).toDouble(),
      (r['name'] ?? name).toString(),
    );
  }

  /// Try several keyless IP-geolocation providers in turn; return the first
  /// that answers. IP geolocation is inherently approximate — if it's wrong,
  /// set [JarvisConfig.weatherCity].
  Future<(double, double, String)> _ipLocate() async {
    // Each entry: url + a parser to (lat, lon, city).
    final providers = <(String, (double, double, String)? Function(dynamic))>[
      ('https://ipwho.is/', (j) {
        if (j is Map && j['success'] == false) return null;
        final lat = j['latitude'], lon = j['longitude'];
        if (lat is num && lon is num) {
          return (lat.toDouble(), lon.toDouble(), (j['city'] ?? '').toString());
        }
        return null;
      }),
      ('https://get.geojs.io/v1/ip/geo.json', (j) {
        final lat = double.tryParse('${j['latitude']}');
        final lon = double.tryParse('${j['longitude']}');
        if (lat != null && lon != null) {
          return (lat, lon, (j['city'] ?? '').toString());
        }
        return null;
      }),
      ('https://ipapi.co/json/', (j) {
        final lat = j['latitude'], lon = j['longitude'];
        if (lat is num && lon is num) {
          return (lat.toDouble(), lon.toDouble(), (j['city'] ?? '').toString());
        }
        return null;
      }),
      ('https://ipinfo.io/json', (j) {
        final loc = (j['loc'] ?? '').toString().split(',');
        if (loc.length == 2) {
          final lat = double.tryParse(loc[0]), lon = double.tryParse(loc[1]);
          if (lat != null && lon != null) {
            return (lat, lon, (j['city'] ?? '').toString());
          }
        }
        return null;
      }),
    ];

    for (final (url, parse) in providers) {
      try {
        final resp =
            await _client.get(Uri.parse(url)).timeout(const Duration(seconds: 5));
        if (resp.statusCode != 200) continue;
        final parsed = parse(jsonDecode(resp.body));
        if (parsed != null) {
          final city = parsed.$3.isEmpty ? 'Your Location' : parsed.$3;
          return (parsed.$1, parsed.$2, city);
        }
      } catch (_) {
        // try the next provider
      }
    }
    // Last resort.
    return (51.5074, -0.1278, 'London');
  }

  void dispose() => _client.close();
}

/// WMO weather code → short human label.
String wmoDescription(int code) {
  if (code == 0) return 'Clear sky';
  if (code == 1) return 'Mainly clear';
  if (code == 2) return 'Partly cloudy';
  if (code == 3) return 'Overcast';
  if (code == 45 || code == 48) return 'Fog';
  if (code >= 51 && code <= 57) return 'Drizzle';
  if (code >= 61 && code <= 67) return 'Rain';
  if (code >= 71 && code <= 77) return 'Snow';
  if (code >= 80 && code <= 82) return 'Rain showers';
  if (code >= 85 && code <= 86) return 'Snow showers';
  if (code >= 95) return 'Thunderstorm';
  return 'Unknown';
}

/// WMO weather code → emoji glyph (day/night aware).
String wmoIcon(int code, bool isDay) {
  if (code == 0) return isDay ? '☀️' : '🌙';
  if (code == 1 || code == 2) return isDay ? '🌤️' : '☁️';
  if (code == 3) return '☁️';
  if (code == 45 || code == 48) return '🌫️';
  if (code >= 51 && code <= 57) return '🌦️';
  if (code >= 61 && code <= 67) return '🌧️';
  if (code >= 71 && code <= 77) return '❄️';
  if (code >= 80 && code <= 82) return '🌧️';
  if (code >= 85 && code <= 86) return '🌨️';
  if (code >= 95) return '⛈️';
  return '🌡️';
}
