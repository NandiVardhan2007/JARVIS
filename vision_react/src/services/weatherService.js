import { VisionConfig } from '../config';

export function wmoDescription(code) {
  if (code === 0) return 'Clear sky';
  if (code === 1) return 'Mainly clear';
  if (code === 2) return 'Partly cloudy';
  if (code === 3) return 'Overcast';
  if (code === 45 || code === 48) return 'Fog';
  if (code >= 51 && code <= 57) return 'Drizzle';
  if (code >= 61 && code <= 67) return 'Rain';
  if (code >= 71 && code <= 77) return 'Snow';
  if (code >= 80 && code <= 82) return 'Rain showers';
  if (code >= 85 && code <= 86) return 'Snow showers';
  if (code >= 95) return 'Thunderstorm';
  return 'Unknown';
}

export function wmoIcon(code, isDay = true) {
  if (code === 0) return isDay ? '☀️' : '🌙';
  if (code === 1 || code === 2) return isDay ? '🌤️' : '☁️';
  if (code === 3) return '☁️';
  if (code === 45 || code === 48) return '🌫️';
  if (code >= 51 && code <= 57) return '🌦️';
  if (code >= 61 && code <= 67) return '🌧️';
  if (code >= 71 && code <= 77) return '❄️';
  if (code >= 80 && code <= 82) return '🌧️';
  if (code >= 85 && code <= 86) return '🌨️';
  if (code >= 95) return '⛈️';
  return '🌡️';
}

export class WeatherDay {
  constructor(date, tMax, tMin, code) {
    this.date = new Date(date);
    this.tMax = tMax;
    this.tMin = tMin;
    this.code = code;
  }

  get label() {
    const days = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
    return days[this.date.getDay()];
  }
}

export class Weather {
  constructor({ city, temp, feelsLike, humidity, wind, code, isDay, daily }) {
    this.city = city;
    this.temp = temp;
    this.feelsLike = feelsLike;
    this.humidity = humidity;
    this.wind = wind;
    this.code = code;
    this.isDay = isDay;
    this.daily = daily;
  }

  get description() {
    return wmoDescription(this.code);
  }

  get icon() {
    return wmoIcon(this.code, this.isDay);
  }
}

export class WeatherService {
  async fetch(cityOverride) {
    let lat, lon, resolvedCity;

    const targetCity = cityOverride || VisionConfig.weatherCity;

    if (targetCity && targetCity.trim()) {
      const geo = await this.geocode(targetCity.trim());
      lat = geo.lat;
      lon = geo.lon;
      resolvedCity = geo.city;
    } else {
      const loc = await this.ipLocate();
      lat = loc.lat;
      lon = loc.lon;
      resolvedCity = loc.city;
    }

    const url =
      `https://api.open-meteo.com/v1/forecast` +
      `?latitude=${lat}&longitude=${lon}` +
      `&current=temperature_2m,apparent_temperature,relative_humidity_2m,weather_code,wind_speed_10m,is_day` +
      `&daily=temperature_2m_max,temperature_2m_min,weather_code` +
      `&timezone=auto&forecast_days=4`;

    const resp = await fetch(url);
    if (!resp.ok) throw new Error(`Weather API returned ${resp.status}`);
    const j = await resp.json();

    const cur = j.current;
    const daily = j.daily;

    const times = daily.time;
    const maxs = daily.temperature_2m_max;
    const mins = daily.temperature_2m_min;
    const codes = daily.weather_code;

    const days = [];
    for (let i = 0; i < times.length; i++) {
      days.push(new WeatherDay(times[i], maxs[i], mins[i], codes[i]));
    }

    return new Weather({
      city: resolvedCity,
      temp: cur.temperature_2m,
      feelsLike: cur.apparent_temperature,
      humidity: cur.relative_humidity_2m,
      wind: cur.wind_speed_10m,
      code: cur.weather_code,
      isDay: cur.is_day === 1,
      daily: days,
    });
  }

  async geocode(name) {
    const url = `https.geocoding-api.open-meteo.com/v1/search?name=${encodeURIComponent(name)}&count=5&language=en&format=json`;
    const resp = await fetch(`https://geocoding-api.open-meteo.com/v1/search?name=${encodeURIComponent(name)}&count=5&language=en&format=json`);
    const j = await resp.json();
    const results = j.results;
    if (!results || results.length === 0) {
      throw new Error(`City not found: ${name}`);
    }

    const hint = (VisionConfig.weatherCountry || '').trim().toLowerCase();
    let match = results[0];
    if (hint) {
      for (const cand of results) {
        const cc = String(cand.country_code || '').toLowerCase();
        const cn = String(cand.country || '').toLowerCase();
        if (cc === hint || cn === hint) {
          match = cand;
          break;
        }
      }
    }
    return {
      lat: match.latitude,
      lon: match.longitude,
      city: match.name || name,
    };
  }

  async ipLocate() {
    const providers = [
      async () => {
        const r = await fetch('https://ipwho.is/');
        const j = await r.json();
        if (j && j.success !== false && j.latitude && j.longitude) {
          return { lat: j.latitude, lon: j.longitude, city: j.city || 'Your Location' };
        }
        return null;
      },
      async () => {
        const r = await fetch('https://get.geojs.io/v1/ip/geo.json');
        const j = await r.json();
        const lat = parseFloat(j.latitude), lon = parseFloat(j.longitude);
        if (!isNaN(lat) && !isNaN(lon)) {
          return { lat, lon, city: j.city || 'Your Location' };
        }
        return null;
      },
      async () => {
        const r = await fetch('https://ipapi.co/json/');
        const j = await r.json();
        if (j && j.latitude && j.longitude) {
          return { lat: j.latitude, lon: j.longitude, city: j.city || 'Your Location' };
        }
        return null;
      },
    ];

    for (const p of providers) {
      try {
        const res = await p();
        if (res) return res;
      } catch (e) {}
    }

    return { lat: 51.5074, lon: -0.1278, city: 'London' };
  }
}
