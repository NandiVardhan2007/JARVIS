import React, { useState, useEffect } from 'react';
import { Video, VideoOff, Play, Square } from 'lucide-react';
import { VisionConfig } from '../config';
import { getGlassCardStyle, op } from '../theme';

export function CameraCard({ onStartWebcam, onStopWebcam, isDark = true }) {
  const [isOnline, setIsOnline] = useState(false);
  const [imgSrc, setImgSrc] = useState(null);

  useEffect(() => {
    let isMounted = true;
    let timer;

    const fetchSnapshot = async () => {
      try {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 1500);

        const resp = await fetch(`${VisionConfig.cameraUrl}?t=${Date.now()}`, {
          signal: controller.signal,
        });
        clearTimeout(timeoutId);

        if (resp.ok && isMounted) {
          const blob = await resp.blob();
          const url = URL.createObjectURL(blob);
          setImgSrc(url);
          setIsOnline(true);
        } else if (isMounted) {
          setIsOnline(false);
          setImgSrc(null);
        }
      } catch (e) {
        if (isMounted) {
          setIsOnline(false);
          setImgSrc(null);
        }
      }
    };

    fetchSnapshot();
    timer = setInterval(fetchSnapshot, isOnline ? 100 : 2000);

    return () => {
      isMounted = false;
      clearInterval(timer);
    };
  }, [isOnline]);

  const accent = '#00D4FF';

  return (
    <div
      style={{
        ...getGlassCardStyle(accent, isDark),
        width: '320px',
        padding: '14px',
      }}
    >
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '10px' }}>
        <Video size={18} color={accent} />
        <span
          style={{
            color: '#EAF2FF',
            fontSize: '12px',
            fontWeight: 700,
            letterSpacing: '2px',
            flex: 1,
          }}
        >
          VISUAL CORE
        </span>

        <div
          style={{
            width: '8px',
            height: '8px',
            borderRadius: '50%',
            backgroundColor: isOnline ? '#32D74B' : 'orange',
          }}
        />
        <span
          style={{
            color: isOnline ? '#32D74B' : 'orange',
            fontSize: '10px',
            fontWeight: 700,
          }}
        >
          {isOnline ? 'LIVE' : 'STANDBY'}
        </span>
      </div>

      {/* Video Viewport */}
      <div
        style={{
          height: '180px',
          width: '100%',
          borderRadius: '10px',
          backgroundColor: 'rgba(0, 0, 0, 0.45)',
          overflow: 'hidden',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          marginBottom: '10px',
        }}
      >
        {isOnline && imgSrc ? (
          <img
            src={imgSrc}
            alt="Webcam Live Feed"
            style={{ width: '100%', height: '100%', objectFit: 'cover' }}
          />
        ) : (
          <div style={{ textAlign: 'center', padding: '12px' }}>
            <VideoOff size={32} color="rgba(175, 194, 224, 0.6)" style={{ marginBottom: '8px' }} />
            <div style={{ color: '#EAF2FF', fontSize: '12px', fontWeight: 600 }}>Webcam Feed Offline</div>
            <div style={{ color: 'rgba(175, 194, 224, 0.6)', fontSize: '10px', marginTop: '4px' }}>
              Say "start webcam" or tap button below
            </div>
          </div>
        )}
      </div>

      {/* Controls */}
      <div style={{ display: 'flex', gap: '8px' }}>
        <button
          onClick={onStartWebcam}
          style={{
            flex: 1,
            padding: '8px',
            borderRadius: '8px',
            background: 'transparent',
            border: `1px solid ${op(accent, 0.4)}`,
            color: accent,
            fontSize: '11px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: '4px',
            cursor: 'pointer',
          }}
        >
          <Play size={14} color={accent} /> Start Cam
        </button>

        <button
          onClick={onStopWebcam}
          style={{
            flex: 1,
            padding: '8px',
            borderRadius: '8px',
            background: 'transparent',
            border: '1px solid rgba(255, 69, 58, 0.4)',
            color: '#FF453A',
            fontSize: '11px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: '4px',
            cursor: 'pointer',
          }}
        >
          <Square size={14} color="#FF453A" /> Stop Cam
        </button>
      </div>
    </div>
  );
}
