/// Central settings for the JARVIS frontend — change these in one place.
class JarvisConfig {
  /// WebSocket bridge (jarvis_bridge.py). Change if you run it elsewhere.
  static const String bridgeUrl = 'ws://127.0.0.1:8765';

  /// Weather location.
  ///
  /// Leave [weatherCity] empty ('') to auto-detect by IP. If auto-detect is
  /// wrong (common on some networks/VPNs), just set your city here, e.g.
  ///   static const String weatherCity = 'Visakhapatnam';
  static const String weatherCity = '';

  /// Optional country hint to disambiguate city names during geocoding
  /// (ISO code or name, e.g. 'IN' / 'India'). Empty = no hint.
  static const String weatherCountry = 'IN';
}
