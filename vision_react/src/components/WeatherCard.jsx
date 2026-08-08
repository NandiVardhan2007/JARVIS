import React, { useState, useEffect } from 'react';
import { MapPin } from 'lucide-react';
import { WeatherService, wmoIcon } from '../services/weatherService';
import { getGlassCardStyle } from '../theme';

export function WeatherCard({ city, isDark = true }) {
  const [weather, setWeather] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    const service = new WeatherService();
    let isMounted = true;

    const loadWeather = async () => {
      try {
        const w = await service.fetch(city);
        if (isMounted) {
          setWeather(w);
          setError(null);
        }
      } catch (e) {
        if (isMounted) {
          setError('Weather unavailable');
        }
      }
    };

    loadWeather();
    const interval = setInterval(loadWeather, 10 * 60 * 1000); // 10 mins

    return () => {
      isMounted = false;
      clearInterval(interval);
    };
  }, [city]);

  const accent = '#00B4FF';

  return (
    <div
      style={{
        ...getGlassCardStyle(accent, isDark),
        width: '320px',
        padding: '18px',
      }}
    >
      {!weather ? (
        <div style={{ height: '150px', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          {error ? (
            <span style={{ color: 'rgba(175, 194, 224, 0.6)', fontSize: '13px' }}>{error}</span>
          ) : (
            <span style={{ color: accent, fontSize: '13px' }}>Loading forecast…</span>
          )}
        </div>
      ) : (
        <div>
          {/* Header Location */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '4px', marginBottom: '10px' }}>
            <MapPin size={15} color="rgba(175, 194, 224, 0.6)" />
            <span
              style={{
                color: '#EAF2FF',
                fontWeight: 600,
                fontSize: '14px',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                whiteSpace: 'nowrap',
              }}
            >
              {weather.city}
            </span>
          </div>

          {/* Current Temp & Icon */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '6px' }}>
            <span style={{ fontSize: '46px', lineHeight: 1 }}>{weather.icon}</span>
            <div>
              <div style={{ color: '#EAF2FF', fontSize: '42px', fontWeight: 300, lineHeight: 1 }}>
                {Math.round(weather.temp)}°
              </div>
              <div style={{ color: 'rgba(175, 194, 224, 0.6)', fontSize: '13px' }}>{weather.description}</div>
            </div>
          </div>

          {/* Details */}
          <div style={{ color: 'rgba(175, 194, 224, 0.6)', fontSize: '11.5px', marginBottom: '14px' }}>
            Feels {Math.round(weather.feelsLike)}°   ·   💧 {weather.humidity}%   ·   🌬 {Math.round(weather.wind)} km/h
          </div>

          <div style={{ height: '1px', backgroundColor: 'rgba(57, 75, 110, 0.22)', marginBottom: '12px' }} />

          {/* 3-Day Forecast */}
          <div style={{ display: 'flex', justifyContent: 'space-between' }}>
            {weather.daily.slice(1, 4).map((d, i) => (
              <div key={i} style={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
                <span style={{ color: 'rgba(175, 194, 224, 0.6)', fontSize: '11px' }}>{d.label}</span>
                <span style={{ fontSize: '20px', margin: '4px 0' }}>{wmoIcon(d.code, true)}</span>
                <span style={{ color: '#EAF2FF', fontSize: '11.5px', fontWeight: 500 }}>
                  {Math.round(d.tMax)}° / {Math.round(d.tMin)}°
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
