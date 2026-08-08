import React, { useRef, useEffect } from 'react';
import { Music, Play, Pause, Square, Disc } from 'lucide-react';
import { AssistantState } from '../models/visionState';
import { getGlassCardStyle, op } from '../theme';

export function MusicPlayerCard({ snapshot, onPlayPause, onStop, isDark = true }) {
  const np = snapshot?.nowPlaying;
  const isPlaying = np?.playing === true;
  const level = isPlaying ? (snapshot.state === AssistantState.SPEAKING ? 0.25 : 0.7) : 0.0;
  const accent = '#FF2D55';

  return (
    <div
      style={{
        ...getGlassCardStyle(accent, isDark),
        width: '320px',
        padding: '18px',
      }}
    >
      {!np ? (
        <div style={{ height: '120px', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center' }}>
          <Music size={30} color="rgba(175, 194, 224, 0.6)" style={{ marginBottom: '8px' }} />
          <span style={{ color: 'rgba(175, 194, 224, 0.6)', fontSize: '13px' }}>Nothing playing</span>
        </div>
      ) : (
        <div>
          {/* Header Info */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '14px', marginBottom: '14px' }}>
            <div
              style={{
                width: '60px',
                height: '60px',
                borderRadius: '12px',
                backgroundColor: op(accent, 0.15),
                boxShadow: `0 0 16px ${op(accent, 0.3)}`,
                overflow: 'hidden',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                flexShrink: 0,
              }}
            >
              {np.imageUrl ? (
                <img src={np.imageUrl} alt={np.title} style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
              ) : (
                <Disc size={30} color={op(accent, 0.8)} />
              )}
            </div>

            <div style={{ overflow: 'hidden', flex: 1 }}>
              <div style={{ color: accent, fontSize: '10px', letterSpacing: '1.5px', fontWeight: 700 }}>
                NOW PLAYING
              </div>
              <div
                style={{
                  color: '#EAF2FF',
                  fontSize: '15px',
                  fontWeight: 600,
                  lineHeight: 1.15,
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                  whiteSpace: 'nowrap',
                  marginTop: '4px',
                }}
              >
                {np.title}
              </div>
              <div
                style={{
                  color: 'rgba(175, 194, 224, 0.6)',
                  fontSize: '12.5px',
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                  whiteSpace: 'nowrap',
                  marginTop: '2px',
                }}
              >
                {np.artist}
              </div>
            </div>
          </div>

          {/* Equalizer */}
          <div style={{ marginBottom: '14px' }}>
            <Equalizer level={level} color={accent} />
          </div>

          {/* Controls */}
          <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', gap: '18px' }}>
            <button
              onClick={onPlayPause}
              style={{
                width: '46px',
                height: '46px',
                borderRadius: '50%',
                backgroundColor: accent,
                border: `1px solid ${op(accent, 0.4)}`,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                cursor: 'pointer',
                boxShadow: `0 0 12px ${op(accent, 0.4)}`,
              }}
            >
              {isPlaying ? <Pause size={22} color="#FFFFFF" /> : <Play size={22} color="#FFFFFF" />}
            </button>

            <button
              onClick={onStop}
              style={{
                width: '40px',
                height: '40px',
                borderRadius: '50%',
                backgroundColor: 'rgba(255, 255, 255, 0.06)',
                border: `1px solid ${op(accent, 0.4)}`,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                cursor: 'pointer',
              }}
            >
              <Square size={18} color="#EAF2FF" />
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

function Equalizer({ level, color }) {
  const canvasRef = useRef(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    let animId;
    let t = 0;

    const render = () => {
      t += 0.03;
      ctx.clearRect(0, 0, canvas.width, canvas.height);

      const bars = 28;
      const gap = canvas.width / bars;
      ctx.lineCap = 'round';
      ctx.lineWidth = gap * 0.55;

      for (let i = 0; i < bars; i++) {
        const n = 0.5 + 0.5 * Math.sin(t * 3 + i * 0.6);
        const base = 0.12 + 0.88 * level;
        const h = Math.max(2, Math.min(canvas.height, 2 + base * n * (canvas.height - 2)));
        const x = gap * (i + 0.5);

        ctx.strokeStyle = op(color, 0.35 + 0.5 * n * Math.max(0.05, Math.min(1, level)));
        ctx.beginPath();
        ctx.moveTo(x, canvas.height / 2 - h / 2);
        ctx.lineTo(x, canvas.height / 2 + h / 2);
        ctx.stroke();
      }

      animId = requestAnimationFrame(render);
    };

    render();
    return () => cancelAnimationFrame(animId);
  }, [level, color]);

  return <canvas ref={canvasRef} width={240} height={26} style={{ width: '100%', height: '26px' }} />;
}
