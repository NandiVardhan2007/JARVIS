// Central settings for the VISION React frontend
export const VisionConfig = {
  // WebSocket bridge (vision_bridge.py)
  bridgeUrl: 'ws://127.0.0.1:8765',

  // Camera snapshot URL
  cameraUrl: 'http://127.0.0.1:5055/snapshot.jpg',

  // Weather location override (empty string = IP auto-locate)
  weatherCity: '',

  // Optional country hint for geocoding
  weatherCountry: 'IN',
};
