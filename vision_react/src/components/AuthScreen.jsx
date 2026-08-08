import React, { useRef, useEffect } from 'react';
import { ShieldCheck, ShieldAlert, Lock, Mic } from 'lucide-react';

export function AuthScreen({ stateString, description, onAuthenticated }) {
  const canvasRef = useRef(null);

  const getAuthStateLabel = (st) => {
    switch ((st || '').toLowerCase()) {
      case 'auth_listening': return 'LISTENING FOR MASTER VOICE…';
      case 'auth_verifying': return 'ANALYSING VOICE PRINT MATCH…';
      case 'auth_success': return 'AUTHENTICATION CONFIRMED';
      case 'auth_failed': return 'ACCESS DENIED — RETRYING';
      case 'auth_lockout': return 'SYSTEM LOCKOUT ENFORCED';
      default: return 'SYSTEM LOCKED — SPEAK SECURITY PASSPHRASE';
    }
  };

  const getAuthStateColor = (st) => {
    switch ((st || '').toLowerCase()) {
      case 'auth_listening': return '#32D74B';
      case 'auth_verifying': return '#00D4FF';
      case 'auth_success': return '#30D158';
      case 'auth_failed':
      case 'auth_lockout': return '#FF453A';
      default: return '#00D4FF';
    }
  };

  useEffect(() => {
    if (stateString === 'auth_success') {
      const timer = setTimeout(() => {
        onAuthenticated();
      }, 1800);
      return () => clearTimeout(timer);
    }
  }, [stateString, onAuthenticated]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    let animId;
    let t = 0;

    const draw = () => {
      t += 0.016;
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      const cx = canvas.width / 2;
      const cy = canvas.height / 2;

      // Hexagon matrix
      ctx.strokeStyle = 'rgba(0, 212, 255, 0.05)';
      ctx.lineWidth = 1;
      const size = 30;
      for (let y = -size; y < canvas.height + size; y += size * 1.5) {
        for (let x = -size; x < canvas.width + size; x += size * Math.sqrt(3)) {
          ctx.beginPath();
          for (let i = 0; i < 6; i++) {
            const angle = (Math.PI / 3) * i;
            const hx = x + size * Math.cos(angle);
            const hy = y + size * Math.sin(angle);
            if (i === 0) ctx.moveTo(hx, hy);
            else ctx.lineTo(hx, hy);
          }
          ctx.closePath();
          ctx.stroke();
        }
      }

      // Security pulse rings
      const col = getAuthStateColor(stateString);
      const rings = 3;
      for (let i = 0; i < rings; i++) {
        const rad = 100 + ((t * 80 + i * 50) % 180);
        const alpha = Math.max(0, 1 - rad / 280);
        ctx.strokeStyle = col;
        ctx.globalAlpha = alpha * 0.4;
        ctx.lineWidth = 1.5;
        ctx.beginPath();
        ctx.arc(cx, cy, rad, 0, Math.PI * 2);
        ctx.stroke();
        ctx.globalAlpha = 1.0;
      }

      animId = requestAnimationFrame(draw);
    };

    draw();
    return () => cancelAnimationFrame(animId);
  }, [stateString]);

  const color = getAuthStateColor(stateString);

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        backgroundColor: '#020509',
        zIndex: 9990,
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
      }}
    >
      <canvas
        ref={canvasRef}
        width={window.innerWidth}
        height={window.innerHeight}
        style={{ position: 'absolute', inset: 0, pointerEvents: 'none' }}
      />

      <div
        style={{
          zIndex: 10,
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          textAlign: 'center',
          padding: '24px',
        }}
      >
        {/* Security Orb Icon */}
        <div
          style={{
            width: '140px',
            height: '140px',
            borderRadius: '50%',
            background: `radial-gradient(circle, ${color}22 0%, rgba(5,7,13,0.8) 70%)`,
            border: `2px solid ${color}88`,
            boxShadow: `0 0 40px ${color}44`,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            marginBottom: '32px',
          }}
        >
          {stateString === 'auth_success' ? (
            <ShieldCheck size={64} color={color} />
          ) : stateString === 'auth_failed' || stateString === 'auth_lockout' ? (
            <ShieldAlert size={64} color={color} />
          ) : stateString === 'auth_listening' ? (
            <Mic size={64} color={color} className="animate-pulse-glow" />
          ) : (
            <Lock size={64} color={color} />
          )}
        </div>

        <h1
          className="font-orbitron glow-text"
          style={{
            color,
            fontSize: '36px',
            fontWeight: 900,
            letterSpacing: '12px',
            margin: 0,
          }}
        >
          VISION
        </h1>

        <div
          style={{
            color: `${color}DD`,
            fontSize: '12px',
            letterSpacing: '3.5px',
            fontWeight: 700,
            marginTop: '12px',
            textTransform: 'uppercase',
          }}
        >
          {getAuthStateLabel(stateString)}
        </div>

        {description && (
          <p
            style={{
              color: 'rgba(175, 194, 224, 0.6)',
              fontSize: '12px',
              letterSpacing: '1.5px',
              marginTop: '16px',
              maxWidth: '480px',
            }}
          >
            {description.toUpperCase()}
          </p>
        )}
      </div>
    </div>
  );
}
