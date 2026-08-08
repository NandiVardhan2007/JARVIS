import React, { useRef, useEffect } from 'react';
import { AssistantState, Emotion } from '../models/visionState';
import { Particle, ExprTargets, exprFor, FaceParams } from './faceParams';
import { op } from '../theme';

export function VisionFace({ snapshot, size = 320 }) {
  const canvasRef = useRef(null);

  // Animation state persistent across frames
  const animRef = useRef({
    t: 0,
    lastElapsed: 0,
    breath: 0,
    aiLevel: 0,
    micLevel: 0,
    mouth: 0,
    core: 0,
    primary: '#5082B4',
    secondary: '#285078',

    // Blink
    blink: 0,
    nextBlink: 2,
    blinkClock: 0,
    blinkPhase: 0,
    blinking: false,

    // Wink
    wink: 0,
    winkPhase: 0,
    nextWink: 12,
    winkClock: 0,
    winking: false,

    // Gaze & Head
    pupilX: 0,
    pupilY: 0,
    pupilTX: 0,
    pupilTY: 0,
    nextSaccade: 1.5,
    saccadeClock: 0,
    headTurn: 0,
    headTilt: 0,

    // Expression pose
    browRaise: 0.15,
    browTilt: 0,
    eyeOpen: 0.85,
    lowerLid: 0.05,
    pupilDilate: 0.5,
    mouthCurve: 0.1,
    mouthOpenBase: 0,
    heart: 0,
    blush: 0,

    idleTime: 0,
    floatY: 0,
    hudA: 0,
    hudB: 0,

    particles: [],
    rippleRadius: 0,
    rippleAlpha: 0,
    lastState: AssistantState.IDLE,
    wave: new Array(56).fill(0),
  });

  const damp = (cur, tgt, rate, dt) => cur + (tgt - cur) * (1 - Math.exp(-rate * dt));

  const hexToRgb = (hex) => {
    let c = hex.replace('#', '');
    if (c.length === 3) c = c.split('').map(x => x + x).join('');
    const num = parseInt(c, 16);
    return { r: (num >> 16) & 255, g: (num >> 8) & 255, b: num & 255 };
  };

  const lerpColor = (c1, c2, t) => {
    const rgb1 = hexToRgb(c1.startsWith('#') ? c1 : '#5082B4');
    const rgb2 = hexToRgb(c2.startsWith('#') ? c2 : '#285078');
    const r = Math.round(rgb1.r + (rgb2.r - rgb1.r) * t);
    const g = Math.round(rgb1.g + (rgb2.g - rgb1.g) * t);
    const b = Math.round(rgb1.b + (rgb2.b - rgb1.b) * t);
    return `rgb(${r}, ${g}, ${b})`;
  };

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');

    let animationFrameId;
    let startTime = null;

    const render = (nowTimestamp) => {
      if (!startTime) startTime = nowTimestamp;
      const now = (nowTimestamp - startTime) / 1000;
      let dt = now - animRef.current.lastElapsed;
      animRef.current.lastElapsed = now;

      if (dt <= 0) {
        animationFrameId = requestAnimationFrame(render);
        return;
      }
      if (dt > 0.05) dt = 0.05;

      const st = animRef.current;
      const s = snapshot;

      st.t += dt;
      st.breath += dt * 1.5;
      st.hudA += dt * 0.35;
      st.hudB -= dt * 0.22;

      if (s.state === AssistantState.IDLE) {
        st.idleTime += dt;
      } else {
        st.idleTime = 0;
      }

      // Smooth color transitions
      st.primary = lerpColor(st.primary, s.colors.primary, 1 - Math.exp(-6 * dt));
      st.secondary = lerpColor(st.secondary, s.colors.secondary, 1 - Math.exp(-6 * dt));

      // Levels & energy core
      st.aiLevel = damp(st.aiLevel, s.aiLevel, 14, dt);
      st.micLevel = damp(st.micLevel, s.micLevel, 16, dt);
      let coreTarget = 0.25 + 0.5 * st.aiLevel;
      if (s.state === AssistantState.THINKING) coreTarget = 0.45 + 0.2 * Math.sin(st.t * 4);
      if (s.state === AssistantState.LISTENING) coreTarget = 0.3 + 0.5 * st.micLevel;
      st.core = damp(st.core, Math.max(0, Math.min(1, coreTarget)), 8, dt);

      // Emotion blend
      let activeEmotion = s.emotion;
      if (s.state === AssistantState.IDLE && st.idleTime > 14) activeEmotion = Emotion.SLEEPY;
      const tgt = exprFor(activeEmotion);
      const r = 7.0;

      st.browRaise = damp(st.browRaise, tgt.browRaise, r, dt);
      st.browTilt = damp(st.browTilt, tgt.browTilt, r, dt);
      st.eyeOpen = damp(st.eyeOpen, tgt.eyeOpen, r, dt);
      st.lowerLid = damp(st.lowerLid, tgt.lowerLid, r, dt);
      st.pupilDilate = damp(st.pupilDilate, tgt.pupil, r, dt);
      st.mouthCurve = damp(st.mouthCurve, tgt.mouthCurve, r, dt);
      st.mouthOpenBase = damp(st.mouthOpenBase, tgt.mouthOpen, r, dt);
      st.heart = damp(st.heart, tgt.heart, 5, dt);
      st.blush = damp(st.blush, tgt.blush, 5, dt);

      // Lip-sync viseme envelope
      let mouthTarget = st.mouthOpenBase;
      if (s.state === AssistantState.SPEAKING) {
        const env = Math.pow(Math.max(0, Math.min(1, s.aiLevel)), 0.6);
        mouthTarget = Math.max(st.mouthOpenBase, env);
      } else if (s.state === AssistantState.LISTENING) {
        mouthTarget = Math.max(st.mouthOpenBase, 0.1 * st.micLevel);
      }
      mouthTarget = Math.max(0, Math.min(1, mouthTarget));
      const mrate = mouthTarget > st.mouth ? 34.0 : 15.0;
      st.mouth = damp(st.mouth, mouthTarget, mrate, dt);

      // Updates
      updateBlink(st, dt);
      updateWink(st, dt, s.state);
      updateGaze(st, dt, s.state);
      updateHead(st, dt, s.state);
      updateFloat(st, dt, s.state, size);
      updateParticles(st, dt, s.state, size);
      updateRipple(st, dt, s.state, size);
      updateWave(st, dt, s.state);

      // Draw Canvas Frame
      drawCanvas(ctx, size, st, s);

      animationFrameId = requestAnimationFrame(render);
    };

    animationFrameId = requestAnimationFrame(render);

    return () => cancelAnimationFrame(animationFrameId);
  }, [snapshot, size]);

  const updateBlink = (st, dt) => {
    if (st.blinking) {
      st.blinkPhase += dt / 0.15;
      if (st.blinkPhase >= 1) {
        st.blinking = false;
        st.blink = 0;
        st.blinkPhase = 0;
      } else {
        st.blink = Math.sin(st.blinkPhase * Math.PI);
      }
    } else {
      st.blinkClock += dt;
      if (st.blinkClock >= st.nextBlink) {
        st.blinking = true;
        st.blinkClock = 0;
        st.blinkPhase = 0;
        st.nextBlink = 2.0 + Math.random() * 4.0;
      }
    }
  };

  const updateWink = (st, dt, state) => {
    if (st.winking) {
      st.winkPhase += dt / 0.5;
      if (st.winkPhase >= 1) {
        st.winking = false;
        st.wink = 0;
        st.winkPhase = 0;
      } else {
        st.wink = Math.sin(st.winkPhase * Math.PI);
      }
    } else if (state === AssistantState.IDLE) {
      st.winkClock += dt;
      if (st.winkClock >= st.nextWink) {
        st.winking = true;
        st.winkClock = 0;
        st.winkPhase = 0;
        st.nextWink = 14 + Math.random() * 16;
      }
    }
  };

  const updateGaze = (st, dt, state) => {
    st.saccadeClock += dt;
    const interval = state === AssistantState.LISTENING ? 1.1 : st.nextSaccade;
    if (st.saccadeClock >= interval) {
      st.saccadeClock = 0;
      st.nextSaccade = 1.4 + Math.random() * 3.0;
      const spread = state === AssistantState.THINKING ? 0.85 : 0.5;
      st.pupilTX = (Math.random() * 2 - 1) * spread;
      st.pupilTY = (Math.random() * 2 - 1) * spread * 0.55;
      if (state === AssistantState.THINKING) {
        st.pupilTY = -0.45 - Math.random() * 0.3;
      }
    }
    st.pupilX = damp(st.pupilX, st.pupilTX, 9, dt);
    st.pupilY = damp(st.pupilY, st.pupilTY, 9, dt);
  };

  const updateHead = (st, dt, state) => {
    const idleSway = Math.sin(st.breath * 0.31) * 0.05;
    const gazeFollow = st.pupilX * 0.1;
    const turnTarget = idleSway + gazeFollow;
    let tiltTarget = st.pupilY * 0.05;
    if (state === AssistantState.THINKING) tiltTarget += 0.06;

    st.headTurn = damp(st.headTurn, turnTarget, 3.5, dt);
    st.headTilt = damp(st.headTilt, tiltTarget, 3.5, dt);
  };

  const updateFloat = (st, dt, state, size) => {
    const amp = state === AssistantState.IDLE ? 1.0 : 0.5;
    st.floatY = Math.sin(st.breath) * size * 0.012 * amp;
  };

  const updateParticles = (st, dt, state, size) => {
    const want = state === AssistantState.THINKING ? 16 : 0;
    while (st.particles.length < want) {
      st.particles.push(
        new Particle({
          angle: Math.random() * Math.PI * 2,
          radius: 1,
          size: 1.6 + Math.random() * 2.2,
          alpha: 0,
          speed: (0.8 + Math.random() * 1.4) * (Math.random() > 0.5 ? 1 : -1),
          life: 0,
        })
      );
    }

    const rBase = size * 0.3;
    for (const pt of st.particles) {
      pt.angle += pt.speed * dt;
      pt.life += dt;
      pt.radius = rBase * (1.3 + 0.1 * Math.sin(pt.life * 2 + pt.angle));
      const target = state === AssistantState.THINKING ? 1.0 : 0.0;
      pt.alpha = damp(pt.alpha, target, 6, dt);
      const px = size / 2 + Math.cos(pt.angle) * pt.radius;
      const py = size / 2 + Math.sin(pt.angle) * pt.radius;
      pt.trail.unshift({ x: px, y: py });
      if (pt.trail.length > 6) pt.trail.pop();
    }

    if (state !== AssistantState.THINKING) {
      st.particles = st.particles.filter((p) => p.alpha >= 0.02);
    }
  };

  const updateRipple = (st, dt, state, size) => {
    if (state !== st.lastState) {
      st.lastState = state;
      st.rippleRadius = size * 0.24;
      st.rippleAlpha = 1.0;
    }
    if (st.rippleAlpha > 0.01) {
      st.rippleRadius += dt * size * 0.9;
      st.rippleAlpha *= Math.exp(-3.5 * dt);
    } else {
      st.rippleAlpha = 0;
    }
  };

  const updateWave = (st, dt, state) => {
    if (state === AssistantState.SPEAKING) {
      for (let i = 0; i < st.wave.length; i++) {
        const target = Math.max(0, Math.sin(st.t * 12 + i * 0.35)) * st.aiLevel;
        st.wave[i] = damp(st.wave[i], target, 18, dt);
      }
    } else {
      for (let i = 0; i < st.wave.length; i++) {
        st.wave[i] = damp(st.wave[i], 0, 10, dt);
      }
    }
  };

  // ── Drawing Engine ────────────────────────────────────────────────────────
  const drawCanvas = (ctx, size, p, snap) => {
    ctx.clearRect(0, 0, size, size);

    const r = size * 0.3;
    const cx = size / 2;
    const cy = size / 2 + p.floatY;

    // 1. Aura
    drawAura(ctx, cx, cy, r, p);

    // 2. HUD Reticle Rings
    drawHudRings(ctx, cx, cy, r, p);

    // 3. Orb Body & Energy Core
    drawOrbBody(ctx, cx, cy, r, p);

    // 4. Glass Sheen
    drawGlassSheen(ctx, cx, cy, r);

    // 5. Waveform
    if (snap.state === AssistantState.SPEAKING) {
      drawWaveform(ctx, cx, cy, r, p);
    }

    // 6. Head Features Matrix (Turn & Tilt)
    ctx.save();
    ctx.translate(cx, cy);
    ctx.rotate(p.headTilt);
    ctx.translate(p.headTurn * r * 0.15, 0);
    ctx.translate(-cx, -cy);

    drawBlush(ctx, cx, cy, r, p);
    drawBrows(ctx, cx, cy, r, p);
    drawEyes(ctx, cx, cy, r, p);
    drawMouth(ctx, cx, cy, r, p);
    ctx.restore();

    // 7. Listening Ring
    if (snap.state === AssistantState.LISTENING) {
      drawMicRing(ctx, cx, cy, r, p);
    }

    // 8. Particles
    drawParticles(ctx, cx, cy, r, p);

    // 9. Ripple
    drawRipple(ctx, cx, cy, r, p);

    // 10. Mute Badge
    if (snap.micMuted) {
      drawMuteBadge(ctx, cx, cy, r);
    }
  };

  const drawAura = (ctx, cx, cy, r, p) => {
    const breath = 0.6 + 0.4 * (0.5 + 0.5 * Math.sin(p.breath));
    const scale = 1.0 + 0.06 * Math.sin(p.breath) + 0.12 * p.core;
    const ar = r * 2.8 * scale;

    const grad = ctx.createRadialGradient(cx, cy, 0, cx, cy, ar);
    grad.addColorStop(0, op(p.primary, 0.32 * breath));
    grad.addColorStop(0.42, op(p.primary, 0.12 * breath));
    grad.addColorStop(1.0, op(p.primary, 0));

    ctx.fillStyle = grad;
    ctx.beginPath();
    ctx.arc(cx, cy, ar, 0, Math.PI * 2);
    ctx.fill();
  };

  const drawHudRings = (ctx, cx, cy, r, p) => {
    const rA = r * 1.2;

    // Ring A arcs
    ctx.strokeStyle = op(p.primary, 0.55);
    ctx.lineWidth = 2.2;
    ctx.lineCap = 'round';
    for (let i = 0; i < 3; i++) {
      const start = p.hudA + i * ((2 * Math.PI) / 3);
      ctx.beginPath();
      ctx.arc(cx, cy, rA, start, start + 0.7);
      ctx.stroke();
    }

    // Ticks
    ctx.strokeStyle = op(p.primary, 0.28);
    ctx.lineWidth = 1.2;
    const ticks = 48;
    for (let i = 0; i < ticks; i++) {
      const a = p.hudA * 0.5 + i * ((2 * Math.PI) / ticks);
      const inner = rA * 0.965;
      const outer = rA * (i % 4 === 0 ? 0.995 : 0.982);
      ctx.beginPath();
      ctx.moveTo(cx + Math.cos(a) * inner, cy + Math.sin(a) * inner);
      ctx.lineTo(cx + Math.cos(a) * outer, cy + Math.sin(a) * outer);
      ctx.stroke();
    }

    // Ring B dots
    const rB = r * 1.42;
    const dots = 60;
    for (let i = 0; i < dots; i++) {
      const a = p.hudB + i * ((2 * Math.PI) / dots);
      const px = cx + Math.cos(a) * rB;
      const py = cy + Math.sin(a) * rB;
      ctx.fillStyle = op(p.primary, 0.3);
      ctx.beginPath();
      ctx.arc(px, py, i % 5 === 0 ? 1.6 : 0.8, 0, Math.PI * 2);
      ctx.fill();
    }

    // Orbiting nodes
    for (let i = 0; i < 3; i++) {
      const a = p.hudA + i * ((2 * Math.PI) / 3) + 0.35;
      const px = cx + Math.cos(a) * rA;
      const py = cy + Math.sin(a) * rA;
      const grad = ctx.createRadialGradient(px, py, 0, px, py, 5);
      grad.addColorStop(0, op(p.primary, 0.9));
      grad.addColorStop(1, op(p.primary, 0));
      ctx.fillStyle = grad;
      ctx.beginPath();
      ctx.arc(px, py, 3.2, 0, Math.PI * 2);
      ctx.fill();
    }

    // Corner brackets
    drawBrackets(ctx, cx, cy, r * 1.55, op(p.primary, 0.34), p.hudB * 0.3);
  };

  const drawBrackets = (ctx, cx, cy, rad, color, rot) => {
    ctx.strokeStyle = color;
    ctx.lineWidth = 2.0;
    ctx.lineCap = 'round';
    const len = 0.18;
    for (let i = 0; i < 4; i++) {
      const base = rot + i * (Math.PI / 2) + Math.PI / 4;
      ctx.beginPath();
      ctx.arc(cx, cy, rad, base - len, base + len);
      ctx.stroke();
    }
  };

  const drawOrbBody = (ctx, cx, cy, r, p) => {
    const deform = p.state === AssistantState.SPEAKING ? 4.0 + p.aiLevel * 6 : p.state === AssistantState.THINKING ? 3.0 : 1.6;
    const t = p.t * 1.3;

    // Fluid blobs
    for (let i = 0; i < 3; i++) {
      const a = t + i * 2.094;
      const bcX = cx + Math.cos(a) * deform;
      const bcY = cy + Math.sin(a) * deform;
      const br = r + Math.sin(t * 2 + i) * deform * 0.6;
      const col = i % 2 === 0 ? p.primary : p.secondary;

      const grad = ctx.createRadialGradient(bcX, bcY, 0, bcX, bcY, br * 1.12);
      grad.addColorStop(0, op(col, 0.55));
      grad.addColorStop(0.6, op(col, 0.16));
      grad.addColorStop(1.0, op(col, 0));

      ctx.fillStyle = grad;
      ctx.beginPath();
      ctx.arc(bcX, bcY, br * 1.12, 0, Math.PI * 2);
      ctx.fill();
    }

    // Dark glassy faceplate
    const plateGrad = ctx.createRadialGradient(cx - r * 0.3, cy - r * 0.4, 0, cx, cy, r);
    plateGrad.addColorStop(0, op(p.primary, 0.45));
    plateGrad.addColorStop(1, '#07121F');

    ctx.fillStyle = plateGrad;
    ctx.beginPath();
    ctx.arc(cx, cy, r, 0, Math.PI * 2);
    ctx.fill();

    // Energy core rim
    const rimGlow = 0.25 + 0.6 * p.core;
    ctx.strokeStyle = op(p.primary, rimGlow);
    ctx.lineWidth = 1.5 + 2.5 * p.core;
    ctx.beginPath();
    ctx.arc(cx, cy, r * 0.62, 0, Math.PI * 2);
    ctx.stroke();

    // Sweep gradient light
    ctx.save();
    ctx.translate(cx, cy);
    ctx.rotate(p.t * 0.6);
    ctx.strokeStyle = op(p.primary, 0.6);
    ctx.lineWidth = 1.6;
    ctx.beginPath();
    ctx.arc(0, 0, r, 0, Math.PI);
    ctx.stroke();
    ctx.restore();
  };

  const drawGlassSheen = (ctx, cx, cy, r) => {
    const sx = cx - r * 0.32;
    const sy = cy - r * 0.44;
    const w = r * 1.1;
    const h = r * 0.7;

    const grad = ctx.createRadialGradient(sx, sy, 0, sx, sy, w / 2);
    grad.addColorStop(0, 'rgba(255, 255, 255, 0.16)');
    grad.addColorStop(1, 'rgba(255, 255, 255, 0)');

    ctx.fillStyle = grad;
    ctx.beginPath();
    ctx.ellipse(sx, sy, w / 2, h / 2, 0, 0, Math.PI * 2);
    ctx.fill();
  };

  const drawWaveform = (ctx, cx, cy, r, p) => {
    const n = p.wave.length;
    const baseR = r * 1.06;
    ctx.strokeStyle = op(p.primary, 0.8);
    ctx.lineWidth = 2.0;
    ctx.lineCap = 'round';

    for (let i = 0; i < n; i++) {
      const ang = (i / n) * Math.PI * 2 - Math.PI / 2;
      const outer = baseR + 3 + p.wave[i] * r * 0.5;
      ctx.beginPath();
      ctx.moveTo(cx + Math.cos(ang) * baseR, cy + Math.sin(ang) * baseR);
      ctx.lineTo(cx + Math.cos(ang) * outer, cy + Math.sin(ang) * outer);
      ctx.stroke();
    }
  };

  const drawBlush = (ctx, cx, cy, r, p) => {
    if (p.blush < 0.03) return;
    for (const side of [-1, 1]) {
      const bx = cx + side * r * 0.44;
      const by = cy + r * 0.2;
      const bw = r * 0.5;
      const bh = r * 0.34;

      const grad = ctx.createRadialGradient(bx, by, 0, bx, by, bw / 2);
      grad.addColorStop(0, `rgba(255, 107, 157, ${0.5 * p.blush})`);
      grad.addColorStop(1, 'rgba(255, 107, 157, 0)');

      ctx.fillStyle = grad;
      ctx.beginPath();
      ctx.ellipse(bx, by, bw / 2, bh / 2, 0, 0, Math.PI * 2);
      ctx.fill();
    }
  };

  const drawBrows = (ctx, cx, cy, r, p) => {
    const eo = r * 0.4;
    const eyeTop = cy - r * 0.08 - r * 0.16;
    const hw = r * 0.2;

    ctx.strokeStyle = 'rgba(244, 251, 255, 0.9)';
    ctx.lineWidth = Math.max(2.4, r * 0.055);
    ctx.lineCap = 'round';

    for (const side of [-1, 1]) {
      const ex = cx + side * eo;
      const browY = eyeTop - r * 0.1 - p.browRaise * r * 0.12;
      const innerX = ex - side * hw * 0.65;
      const outerX = ex + side * hw * 1.05;
      const innerY = browY - p.browTilt * r * 0.1;
      const outerY = browY + p.browTilt * r * 0.04;

      ctx.beginPath();
      ctx.moveTo(innerX, innerY);
      ctx.quadraticCurveTo(ex, browY - r * 0.04, outerX, outerY);
      ctx.stroke();
    }
  };

  const drawEyes = (ctx, cx, cy, r, p) => {
    const ey = cy - r * 0.08;
    const eo = r * 0.4;
    const hw = r * 0.205;
    const hhBase = r * 0.17;

    for (const side of [-1, 1]) {
      const ex = cx + side * eo;
      let open = Math.max(0, Math.min(1, p.eyeOpen * (1 - p.blink)));
      if (side === -1) open *= 1 - p.wink;

      if (open < 0.1) {
        // Closed lash line
        ctx.strokeStyle = 'rgba(244, 251, 255, 0.92)';
        ctx.lineWidth = Math.max(2.2, r * 0.05);
        ctx.lineCap = 'round';
        ctx.beginPath();
        ctx.moveTo(ex - hw, ey);
        ctx.quadraticCurveTo(ex, ey + hhBase * 0.5, ex + hw, ey);
        ctx.stroke();
        continue;
      }

      const hh = hhBase * open;
      const botH = hh * (1 - p.lowerLid * 0.7);

      ctx.save();
      ctx.beginPath();
      ctx.moveTo(ex - hw, ey);
      ctx.quadraticCurveTo(ex, ey - hh * 1.9, ex + hw, ey);
      ctx.quadraticCurveTo(ex, ey + botH * 1.9, ex - hw, ey);
      ctx.closePath();
      ctx.clip();

      // Eye interior
      ctx.fillStyle = '#0A1622';
      ctx.fillRect(ex - hw * 1.4, ey - hh * 1.4, hw * 2.8, hh * 2.8);

      // Gaze offset
      const gazeX = p.pupilX * hw * 0.4;
      const gazeY = p.pupilY * hh * 0.4;
      const irisX = ex + gazeX;
      const irisY = ey + gazeY;
      const ir = hw * 0.62;

      if (p.heart > 0.5) {
        drawHeartEye(ctx, irisX, irisY, ir * 1.15);
      } else {
        // Iris gradient
        const irisGrad = ctx.createRadialGradient(irisX, irisY, 0, irisX, irisY, ir);
        irisGrad.addColorStop(0, '#FFFFFF');
        irisGrad.addColorStop(0.55, p.primary);
        irisGrad.addColorStop(1.0, '#07121F');

        ctx.fillStyle = irisGrad;
        ctx.beginPath();
        ctx.arc(irisX, irisY, ir, 0, Math.PI * 2);
        ctx.fill();

        // Pupil
        const pr = ir * (0.3 + 0.46 * p.pupilDilate);
        ctx.fillStyle = '#05090F';
        ctx.beginPath();
        ctx.arc(irisX, irisY, pr, 0, Math.PI * 2);
        ctx.fill();

        // Catchlights
        ctx.fillStyle = 'rgba(255, 255, 255, 0.95)';
        ctx.beginPath();
        ctx.arc(irisX - ir * 0.35, irisY - ir * 0.4, ir * 0.22, 0, Math.PI * 2);
        ctx.fill();

        ctx.fillStyle = 'rgba(255, 255, 255, 0.6)';
        ctx.beginPath();
        ctx.arc(irisX + ir * 0.28, irisY + ir * 0.25, ir * 0.11, 0, Math.PI * 2);
        ctx.fill();
      }

      ctx.restore();

      // Upper lid shadow definition line
      ctx.strokeStyle = 'rgba(244, 251, 255, 0.85)';
      ctx.lineWidth = Math.max(1.4, r * 0.03);
      ctx.lineCap = 'round';
      ctx.beginPath();
      ctx.moveTo(ex - hw, ey);
      ctx.quadraticCurveTo(ex, ey - hh * 1.9, ex + hw, ey);
      ctx.stroke();
    }
  };

  const drawHeartEye = (ctx, cx, cy, s) => {
    ctx.save();
    const top = cy - s * 0.2;
    ctx.beginPath();
    ctx.moveTo(cx, cy + s * 0.75);
    ctx.bezierCurveTo(cx - s * 1.2, cy - s * 0.2, cx - s * 0.5, top - s * 0.7, cx, top);
    ctx.bezierCurveTo(cx + s * 0.5, top - s * 0.7, cx + s * 1.2, cy - s * 0.2, cx, cy + s * 0.75);
    ctx.closePath();

    const grad = ctx.createRadialGradient(cx, cy, 0, cx, cy, s);
    grad.addColorStop(0, '#FF7EB0');
    grad.addColorStop(1, '#FF2D6B');
    ctx.fillStyle = grad;
    ctx.fill();
    ctx.restore();
  };

  const drawMouth = (ctx, cx, cy, r, p) => {
    const my = cy + r * 0.36;
    const mw = r * 0.3;
    const open = Math.max(0, Math.min(1, p.mouth));
    const curve = p.mouthCurve;

    const midOffset = curve * mw * 0.68;
    const openH = open * r * 0.44;
    const widthFactor = 1 - 0.34 * open;
    const halfW = mw * (0.62 + Math.max(-1, Math.min(1, curve)) * 0.06) * widthFactor;

    if (open <= 0.06) {
      // Closed lips curve
      ctx.strokeStyle = 'rgba(244, 251, 255, 0.85)';
      ctx.lineWidth = Math.max(2.0, r * 0.05);
      ctx.lineCap = 'round';
      ctx.beginPath();
      ctx.moveTo(cx - halfW, my);
      ctx.quadraticCurveTo(cx, my + midOffset + openH, cx + halfW, my);
      ctx.stroke();
      return;
    }

    // Open mouth cavity
    ctx.save();
    ctx.beginPath();
    ctx.moveTo(cx - halfW, my);
    ctx.quadraticCurveTo(cx, my + midOffset - openH * 0.12, cx + halfW, my);
    ctx.quadraticCurveTo(cx, my + midOffset + openH, cx - halfW, my);
    ctx.closePath();

    const grad = ctx.createRadialGradient(cx, my + midOffset + openH * 0.4, 0, cx, my + midOffset + openH * 0.4, halfW * 1.6);
    grad.addColorStop(0, '#3A1420');
    grad.addColorStop(1, '#14060B');

    ctx.fillStyle = grad;
    ctx.fill();

    // Lower lip gloss
    ctx.strokeStyle = 'rgba(244, 251, 255, 0.55)';
    ctx.lineWidth = Math.max(1.6, r * 0.03);
    ctx.lineCap = 'round';
    ctx.beginPath();
    ctx.moveTo(cx - halfW * 0.8, my + midOffset + openH * 0.55);
    ctx.quadraticCurveTo(cx, my + midOffset + openH * 0.95, cx + halfW * 0.8, my + midOffset + openH * 0.55);
    ctx.stroke();

    ctx.restore();
  };

  const drawMicRing = (ctx, cx, cy, r, p) => {
    const lv = p.micLevel;
    if (lv < 0.03) return;
    for (let i = 0; i < 2; i++) {
      const ringR = r * 1.05 + i * 8 + lv * (14 + i * 10);
      ctx.strokeStyle = `rgba(50, 215, 75, ${(0.55 - i * 0.25) * Math.max(0, Math.min(1, lv))})`;
      ctx.lineWidth = 2.0 - i * 0.6;
      ctx.beginPath();
      ctx.arc(cx, cy, ringR, 0, Math.PI * 2);
      ctx.stroke();
    }
  };

  const drawParticles = (ctx, cx, cy, r, p) => {
    for (const pt of p.particles) {
      if (pt.alpha < 0.02) continue;

      for (let ti = 0; ti < pt.trail.length; ti++) {
        const frac = (ti + 1) / (pt.trail.length + 1);
        const a = pt.alpha * frac * 0.35;
        const sz = pt.size * frac * 0.6;
        if (a < 0.02 || sz < 0.3) continue;

        ctx.fillStyle = `rgba(255, 180, 50, ${a})`;
        ctx.beginPath();
        ctx.arc(pt.trail[ti].x, pt.trail[ti].y, sz * 1.8, 0, Math.PI * 2);
        ctx.fill();
      }

      const px = cx + Math.cos(pt.angle) * pt.radius;
      const py = cy + Math.sin(pt.angle) * pt.radius;

      const grad = ctx.createRadialGradient(px, py, 0, px, py, pt.size * 2);
      grad.addColorStop(0, `rgba(255, 200, 100, ${pt.alpha})`);
      grad.addColorStop(0.4, `rgba(255, 140, 30, ${pt.alpha * 0.4})`);
      grad.addColorStop(1, 'rgba(255, 140, 30, 0)');

      ctx.fillStyle = grad;
      ctx.beginPath();
      ctx.arc(px, py, pt.size * 2, 0, Math.PI * 2);
      ctx.fill();
    }
  };

  const drawRipple = (ctx, cx, cy, r, p) => {
    if (p.rippleAlpha < 0.01) return;
    const rr = p.rippleRadius;
    ctx.strokeStyle = op(p.primary, 0.7 * p.rippleAlpha);
    ctx.lineWidth = 2.0;
    ctx.beginPath();
    ctx.arc(cx, cy, rr, 0, Math.PI * 2);
    ctx.stroke();

    if (rr > 12) {
      ctx.strokeStyle = op(p.primary, 0.32 * p.rippleAlpha);
      ctx.lineWidth = 1.2;
      ctx.beginPath();
      ctx.arc(cx, cy, rr * 0.65, 0, Math.PI * 2);
      ctx.stroke();
    }
  };

  const drawMuteBadge = (ctx, cx, cy, r) => {
    const bx = cx + r * 0.72;
    const by = cy - r * 0.72;
    const br = r * 0.16;

    ctx.fillStyle = '#FF3B30';
    ctx.beginPath();
    ctx.arc(bx, by, br, 0, Math.PI * 2);
    ctx.fill();

    ctx.strokeStyle = '#FFFFFF';
    ctx.lineWidth = 2.0;
    ctx.lineCap = 'round';
    ctx.beginPath();
    ctx.moveTo(bx - br * 0.5, by + br * 0.5);
    ctx.lineTo(bx + br * 0.5, by - br * 0.5);
    ctx.stroke();
  };

  return (
    <div style={{ width: size, height: size, position: 'relative', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
      <canvas
        ref={canvasRef}
        width={size}
        height={size}
        style={{ width: size, height: size, display: 'block' }}
      />
    </div>
  );
}
