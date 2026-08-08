import React, { useState, useEffect } from 'react';
import { Cpu, HardDrive } from 'lucide-react';
import { getGlassCardStyle, op } from '../theme';

export function SystemMonitorCard({ isDark = true }) {
  const [cpu, setCpu] = useState(24);
  const [ram, setRam] = useState(42);
  const [hostname, setHostname] = useState('VISION Core Host');
  const [uptime, setUptime] = useState('Active');

  useEffect(() => {
    // Soft jitter for CPU & RAM gauges to reflect dynamic OS activity
    const interval = setInterval(() => {
      setCpu(Math.floor(18 + (new Date().getSeconds() % 35) * 1.5));
      setRam(Math.floor(40 + (new Date().getMinutes() % 12) * 1.2));
    }, 3500);

    return () => clearInterval(interval);
  }, []);

  const accent = '#32D74B';

  return (
    <div
      style={{
        ...getGlassCardStyle(accent, isDark),
        width: '320px',
        padding: '18px',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '14px' }}>
        <Cpu size={18} color={accent} />
        <span
          style={{
            color: '#EAF2FF',
            fontSize: '13.5px',
            fontWeight: 600,
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
            flex: 1,
          }}
        >
          {hostname}
        </span>
        <span style={{ color: 'rgba(175, 194, 224, 0.6)', fontSize: '11px' }}>{uptime}</span>
      </div>

      {/* CPU Progress */}
      <div style={{ marginBottom: '12px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '5px' }}>
          <span style={{ color: 'rgba(175, 194, 224, 0.6)', fontSize: '11.5px' }}>CPU Utilization</span>
          <span style={{ color: '#00D4FF', fontSize: '12px', fontWeight: 700 }}>{cpu}%</span>
        </div>
        <div
          style={{
            width: '100%',
            height: '5px',
            borderRadius: '6px',
            backgroundColor: 'rgba(255, 255, 255, 0.06)',
            overflow: 'hidden',
          }}
        >
          <div
            style={{
              width: `${cpu}%`,
              height: '100%',
              backgroundColor: '#00D4FF',
              transition: 'width 0.6s ease',
            }}
          />
        </div>
      </div>

      {/* RAM Progress */}
      <div>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '5px' }}>
          <span style={{ color: 'rgba(175, 194, 224, 0.6)', fontSize: '11.5px' }}>RAM Memory</span>
          <span style={{ color: '#BF5AF2', fontSize: '12px', fontWeight: 700 }}>{ram}%</span>
        </div>
        <div
          style={{
            width: '100%',
            height: '5px',
            borderRadius: '6px',
            backgroundColor: 'rgba(255, 255, 255, 0.06)',
            overflow: 'hidden',
          }}
        >
          <div
            style={{
              width: `${ram}%`,
              height: '100%',
              backgroundColor: '#BF5AF2',
              transition: 'width 0.6s ease',
            }}
          />
        </div>
      </div>
    </div>
  );
}
