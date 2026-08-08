import React, { useState, useEffect, useRef } from 'react';

export function SplashScreen({ onComplete }) {
  const canvasRef = useRef(null);
  const onCompleteRef = useRef(onComplete);
  onCompleteRef.current = onComplete;

  const [visibleLines, setVisibleLines] = useState(0);
  const [glitching, setGlitching] = useState(false);
  const [fadeOut, setFadeOut] = useState(1);
  const dismissedRef = useRef(false);

  const bootLines = [
    'INITIALIZING CORE SYSTEMS...',
    'LOADING NEURAL PATHWAYS........OK',
    'VOICE SYNTHESIS ENGINE.......OK',
    'SPEAKER VERIFICATION MODULE..OK',
    'RAG KNOWLEDGE BASE...........OK',
    'DESKTOP CONTROL STACK........OK',
    'ALL SYSTEMS NOMINAL.',
    '',
    'WELCOME BACK, SIR.',
  ];

  const handleFinish = () => {
    if (dismissedRef.current) return;
    dismissedRef.current = true;

    let alpha = 1;
    const interval = setInterval(() => {
      alpha -= 0.08;
      if (alpha <= 0) {
        clearInterval(interval);
        if (onCompleteRef.current) onCompleteRef.current();
      } else {
        setFadeOut(alpha);
      }
    }, 16);
  };

  // Progressive terminal line reveal
  useEffect(() => {
    let timer;
    const revealNext = (index) => {
      if (index <= bootLines.length) {
        setVisibleLines(index);
        timer = setTimeout(() => revealNext(index + 1), 220);
      }
    };
    const initialDelay = setTimeout(() => revealNext(1), 300);

    return () => {
      clearTimeout(initialDelay);
      clearTimeout(timer);
    };
  }, []);

  // Glitch effect on logo
  useEffect(() => {
    let glitchTimer;
    const triggerGlitch = () => {
      setGlitching(true);
      setTimeout(() => {
        setGlitching(false);
        glitchTimer = setTimeout(triggerGlitch, 1200 + Math.random() * 2000);
      }, 80);
    };
    glitchTimer = setTimeout(triggerGlitch, 800);
    return () => clearTimeout(glitchTimer);
  }, []);

  // Auto-dismiss after 3.2s
  useEffect(() => {
    const dismissTimer = setTimeout(() => {
      handleFinish();
    }, 3200);

    return () => clearTimeout(dismissTimer);
  }, []);

  // Reactor Canvas background & core
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

      // Hex background grid
      ctx.strokeStyle = 'rgba(0, 212, 255, 0.04)';
      ctx.lineWidth = 1;
      const hexSize = 24;
      for (let y = 0; y < canvas.height + hexSize; y += hexSize * 1.5) {
        for (let x = 0; x < canvas.width + hexSize; x += hexSize * Math.sqrt(3)) {
          ctx.beginPath();
          for (let i = 0; i < 6; i++) {
            const angle = (Math.PI / 3) * i;
            const hx = x + hexSize * Math.cos(angle);
            const hy = y + hexSize * Math.sin(angle);
            if (i === 0) ctx.moveTo(hx, hy);
            else ctx.lineTo(hx, hy);
          }
          ctx.closePath();
          ctx.stroke();
        }
      }

      // Reactor core rings
      const r = 90;
      const coreGrad = ctx.createRadialGradient(cx, cy, 0, cx, cy, r * 1.2);
      coreGrad.addColorStop(0, 'rgba(0, 212, 255, 0.6)');
      coreGrad.addColorStop(0.5, 'rgba(0, 212, 255, 0.15)');
      coreGrad.addColorStop(1, 'rgba(0, 212, 255, 0)');
      ctx.fillStyle = coreGrad;
      ctx.beginPath();
      ctx.arc(cx, cy, r * 1.2, 0, Math.PI * 2);
      ctx.fill();

      ctx.strokeStyle = 'rgba(0, 212, 255, 0.6)';
      ctx.lineWidth = 2;
      for (let i = 0; i < 3; i++) {
        const start = t * 0.8 + i * ((2 * Math.PI) / 3);
        ctx.beginPath();
        ctx.arc(cx, cy, r, start, start + 0.8);
        ctx.stroke();
      }

      ctx.strokeStyle = 'rgba(130, 60, 220, 0.5)';
      ctx.lineWidth = 1.5;
      for (let i = 0; i < 4; i++) {
        const start = -t * 1.2 + i * (Math.PI / 2);
        ctx.beginPath();
        ctx.arc(cx, cy, r * 0.7, start, start + 0.5);
        ctx.stroke();
      }

      animId = requestAnimationFrame(draw);
    };

    draw();
    return () => cancelAnimationFrame(animId);
  }, []);

  return (
    <div
      onClick={handleFinish}
      style={{
        position: 'fixed',
        inset: 0,
        backgroundColor: '#020509',
        zIndex: 9999,
        opacity: fadeOut,
        transition: 'opacity 0.1s linear',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        cursor: 'pointer',
      }}
    >
      <canvas
        ref={canvasRef}
        width={window.innerWidth}
        height={window.innerHeight}
        style={{ position: 'absolute', inset: 0, pointerEvents: 'none' }}
      />

      <div style={{ zIndex: 10, display: 'flex', flexDirection: 'column', alignItems: 'center', textAlign: 'center' }}>
        {/* Logo with glitch */}
        <div style={{ position: 'relative' }}>
          <h1
            className="font-orbitron glow-text"
            style={{
              color: '#00D4FF',
              fontSize: '44px',
              fontWeight: 900,
              letterSpacing: '14px',
              margin: 0,
            }}
          >
            VISION
          </h1>
          {glitching && (
            <h1
              className="font-orbitron"
              style={{
                position: 'absolute',
                top: 0,
                left: '-3px',
                color: '#FF2D55',
                fontSize: '44px',
                fontWeight: 900,
                letterSpacing: '14px',
                margin: 0,
                opacity: 0.7,
                clipPath: 'inset(10% 0 30% 0)',
              }}
            >
              VISION
            </h1>
          )}
        </div>

        <p
          style={{
            color: 'rgba(175, 194, 224, 0.5)',
            fontSize: '10px',
            letterSpacing: '4px',
            fontWeight: 500,
            marginTop: '8px',
            textTransform: 'uppercase',
          }}
        >
          Virtual Intelligent System &amp; Optimized Network
        </p>

        {/* Boot terminal console */}
        <div
          className="font-mono"
          style={{
            marginTop: '40px',
            width: '380px',
            textAlign: 'left',
            background: 'rgba(5, 7, 13, 0.7)',
            padding: '16px',
            borderRadius: '12px',
            border: '1px solid rgba(0, 212, 255, 0.2)',
            boxShadow: '0 0 20px rgba(0, 212, 255, 0.1)',
          }}
        >
          {bootLines.slice(0, visibleLines).map((line, i) => {
            const isLast = i === bootLines.length - 1;
            return (
              <div
                key={i}
                style={{
                  color: isLast ? '#00D4FF' : 'rgba(0, 212, 255, 0.7)',
                  fontSize: isLast ? '13px' : '11px',
                  fontWeight: isLast ? 'bold' : 'normal',
                  marginBottom: '4px',
                  textShadow: '0 0 8px rgba(0, 212, 255, 0.4)',
                }}
              >
                {line}
              </div>
            );
          })}
        </div>

        <div
          style={{
            marginTop: '20px',
            color: 'rgba(0, 212, 255, 0.4)',
            fontSize: '10px',
            letterSpacing: '2px',
            textTransform: 'uppercase',
          }}
        >
          [ Click anywhere to skip ]
        </div>
      </div>
    </div>
  );
}
