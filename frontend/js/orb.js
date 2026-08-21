/**
 * VISION AI — 3D Quantum Energy Orb (Three.js)
 * Performance-gated particle sphere with state-reactive animations
 */

const VisionOrb = (() => {
  let scene, camera, renderer;
  let orbGroup, particleSphere, coronaDust, plasmaCore, outerRings = [], satellites = [];
  let noiseVal = 0;
  let agentState = 'idle'; // idle | listening | thinking | executing | speaking | muted
  let audioFrequencyData = new Uint8Array(32);
  let animationFrameId = null;
  let isVisible = true;

  function init() {
    const container = document.getElementById('canvas-container');
    if (!container || typeof THREE === 'undefined') {
      console.warn('[Orb] Three.js or canvas-container not found');
      return;
    }

    const width = window.innerWidth;
    const height = window.innerHeight;

    scene = new THREE.Scene();
    camera = new THREE.PerspectiveCamera(45, width / height, 0.1, 1000);
    camera.position.z = 4.6;

    renderer = new THREE.WebGLRenderer({ canvas: document.getElementById('canvas3d'), alpha: true, antialias: true });
    renderer.setSize(width, height);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));

    orbGroup = new THREE.Group();
    scene.add(orbGroup);

    const pTexture = createParticleTexture();

    // ── 1. Quantum Particle Matrix (2,500 Nodes) ──
    const particleCount = 2500;
    const geometry = new THREE.BufferGeometry();
    const positions = new Float32Array(particleCount * 3);
    const originalPositions = new Float32Array(particleCount * 3);
    const colors = new Float32Array(particleCount * 3);
    const phases = new Float32Array(particleCount);

    const colCyan    = new THREE.Color(0x22d3ee);
    const colBlue    = new THREE.Color(0x6366f1);
    const colPurple  = new THREE.Color(0x8b5cf6);
    const colMagenta = new THREE.Color(0xec4899);
    const colGreen   = new THREE.Color(0x34d399);

    for (let i = 0; i < particleCount; i++) {
      const phi = Math.acos(-1 + (2 * i) / particleCount);
      const theta = Math.sqrt(particleCount * Math.PI) * phi;

      const shell = 0.88 + (i % 5) * 0.05;
      const radius = 0.94 * shell;

      const x = radius * Math.cos(theta) * Math.sin(phi);
      const y = radius * Math.sin(theta) * Math.sin(phi);
      const z = radius * Math.cos(phi);

      positions[i * 3]     = x;
      positions[i * 3 + 1] = y;
      positions[i * 3 + 2] = z;

      originalPositions[i * 3]     = x;
      originalPositions[i * 3 + 1] = y;
      originalPositions[i * 3 + 2] = z;

      phases[i] = Math.random() * Math.PI * 2;

      let mixedColor;
      const norm = i / particleCount;
      if (norm < 0.35) {
        mixedColor = colCyan.clone().lerp(colBlue, norm * 2.85);
      } else if (norm < 0.7) {
        mixedColor = colBlue.clone().lerp(colPurple, (norm - 0.35) * 2.85);
      } else if (norm < 0.9) {
        mixedColor = colPurple.clone().lerp(colMagenta, (norm - 0.7) * 5.0);
      } else {
        mixedColor = colMagenta.clone().lerp(colGreen, (norm - 0.9) * 10.0);
      }

      colors[i * 3]     = mixedColor.r;
      colors[i * 3 + 1] = mixedColor.g;
      colors[i * 3 + 2] = mixedColor.b;
    }

    geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
    geometry.setAttribute('color', new THREE.BufferAttribute(colors, 3));
    geometry.userData = { originalPositions, phases };

    const particleMat = new THREE.PointsMaterial({
      size: 0.048,
      map: pTexture,
      transparent: true,
      vertexColors: true,
      blending: THREE.AdditiveBlending,
      depthWrite: false
    });

    particleSphere = new THREE.Points(geometry, particleMat);
    orbGroup.add(particleSphere);

    // ── 2. Corona Dust (800 Particles) ──
    const dustCount = 800;
    const dustGeo = new THREE.BufferGeometry();
    const dustPos = new Float32Array(dustCount * 3);
    const dustColors = new Float32Array(dustCount * 3);
    const dustOrig = new Float32Array(dustCount * 3);

    for (let i = 0; i < dustCount; i++) {
      const u = Math.random();
      const v = Math.random();
      const theta = u * 2.0 * Math.PI;
      const phi = Math.acos(2.0 * v - 1.0);
      const r = 1.05 + Math.random() * 0.45;

      const x = r * Math.sin(phi) * Math.cos(theta);
      const y = r * Math.sin(phi) * Math.sin(theta);
      const z = r * Math.cos(phi);

      dustPos[i * 3] = x; dustPos[i * 3 + 1] = y; dustPos[i * 3 + 2] = z;
      dustOrig[i * 3] = x; dustOrig[i * 3 + 1] = y; dustOrig[i * 3 + 2] = z;

      const dustCol = Math.random() > 0.5 ? colCyan : colPurple;
      dustColors[i * 3]     = dustCol.r;
      dustColors[i * 3 + 1] = dustCol.g;
      dustColors[i * 3 + 2] = dustCol.b;
    }

    dustGeo.setAttribute('position', new THREE.BufferAttribute(dustPos, 3));
    dustGeo.setAttribute('color', new THREE.BufferAttribute(dustColors, 3));
    dustGeo.userData = { originalPositions: dustOrig };

    const dustMat = new THREE.PointsMaterial({
      size: 0.030,
      map: pTexture,
      transparent: true,
      vertexColors: true,
      blending: THREE.AdditiveBlending,
      opacity: 0.75,
      depthWrite: false
    });
    coronaDust = new THREE.Points(dustGeo, dustMat);
    orbGroup.add(coronaDust);

    // ── 3. Plasma Core ──
    const coreCanvas = document.createElement('canvas');
    coreCanvas.width = 128; coreCanvas.height = 128;
    const cctx = coreCanvas.getContext('2d');
    const cgrad = cctx.createRadialGradient(64, 64, 0, 64, 64, 64);
    cgrad.addColorStop(0, 'rgba(255, 255, 255, 1)');
    cgrad.addColorStop(0.2, 'rgba(34, 211, 238, 0.95)');
    cgrad.addColorStop(0.55, 'rgba(99, 102, 241, 0.45)');
    cgrad.addColorStop(1, 'rgba(0, 0, 0, 0)');
    cctx.fillStyle = cgrad;
    cctx.fillRect(0, 0, 128, 128);
    const coreSpriteTex = new THREE.CanvasTexture(coreCanvas);

    const coreSpriteMat = new THREE.SpriteMaterial({
      map: coreSpriteTex,
      blending: THREE.AdditiveBlending,
      transparent: true,
      opacity: 0.9
    });
    plasmaCore = new THREE.Sprite(coreSpriteMat);
    plasmaCore.scale.set(0.92, 0.92, 0.92);
    orbGroup.add(plasmaCore);

    // ── 4. Gyroscopic Rings ──
    const ringConfigs = [
      { radius: 1.10, color: 0x22d3ee, tiltX: 1.28, tiltY: 0.20, spinSpeed: 0.0035 },
      { radius: 1.22, color: 0x6366f1, tiltX: 0.45, tiltY: 1.15, spinSpeed: -0.0030 },
      { radius: 1.35, color: 0x8b5cf6, tiltX: 0.85, tiltY: -0.75, spinSpeed: 0.0025 }
    ];

    ringConfigs.forEach((cfg, idx) => {
      const ringPivot = new THREE.Group();
      ringPivot.rotation.x = cfg.tiltX;
      ringPivot.rotation.y = cfg.tiltY;
      orbGroup.add(ringPivot);

      const ringGeo = new THREE.RingGeometry(cfg.radius, cfg.radius + 0.010, 64);
      const ringMat = new THREE.MeshBasicMaterial({
        color: cfg.color,
        side: THREE.DoubleSide,
        transparent: true,
        opacity: 0.32,
        blending: THREE.AdditiveBlending
      });
      const ringMesh = new THREE.Mesh(ringGeo, ringMat);
      ringPivot.add(ringMesh);

      const satGeo = new THREE.SphereGeometry(0.024, 16, 16);
      const satMat = new THREE.MeshBasicMaterial({
        color: 0xffffff,
        transparent: true,
        opacity: 0.95,
        blending: THREE.AdditiveBlending
      });
      const sat = new THREE.Mesh(satGeo, satMat);
      ringPivot.add(sat);

      outerRings.push({
        pivot: ringPivot,
        mesh: ringMesh,
        sat: sat,
        radius: cfg.radius + 0.005,
        angle: (idx * Math.PI) / 1.5,
        spinSpeed: cfg.spinSpeed
      });
    });

    window.addEventListener('resize', onWindowResize);

    // Performance gating: pause when tab hidden or orb not visible
    document.addEventListener('visibilitychange', () => {
      isVisible = !document.hidden;
      if (isVisible && !animationFrameId) animate();
    });

    animate();
  }

  function createParticleTexture() {
    const canvas = document.createElement('canvas');
    canvas.width = 64; canvas.height = 64;
    const ctx = canvas.getContext('2d');
    const grad = ctx.createRadialGradient(32, 32, 0, 32, 32, 32);
    grad.addColorStop(0, 'rgba(255,255,255,1)');
    grad.addColorStop(0.2, 'rgba(34,211,238,0.95)');
    grad.addColorStop(0.55, 'rgba(99,102,241,0.45)');
    grad.addColorStop(1, 'rgba(0,0,0,0)');
    ctx.fillStyle = grad;
    ctx.fillRect(0, 0, 64, 64);
    return new THREE.CanvasTexture(canvas);
  }

  function onWindowResize() {
    if (!camera || !renderer) return;
    camera.aspect = window.innerWidth / window.innerHeight;
    camera.updateProjectionMatrix();
    renderer.setSize(window.innerWidth, window.innerHeight);
  }

  function animate() {
    if (!isVisible || document.hidden) {
      animationFrameId = null;
      return;
    }

    animationFrameId = requestAnimationFrame(animate);
    noiseVal += 0.008;

    // ── 1. Particle Sphere Wave Dynamics ──
    if (particleSphere) {
      const pos = particleSphere.geometry.attributes.position.array;
      const orig = particleSphere.geometry.userData.originalPositions;
      const count = pos.length / 3;

      let intensity = 0.045, speed = 0.65, rotSpeed = 0.0012;

      if (agentState === 'muted')        { intensity = 0.015; speed = 0.25; rotSpeed = 0.0004; }
      else if (agentState === 'listening') { intensity = 0.07;  speed = 0.9;  rotSpeed = 0.0018; }
      else if (agentState === 'thinking')  { intensity = 0.09;  speed = 1.4;  rotSpeed = 0.0035; }
      else if (agentState === 'executing') { intensity = 0.10;  speed = 1.6;  rotSpeed = 0.0040; }
      else if (agentState === 'speaking')  { intensity = 0.08;  speed = 1.0;  rotSpeed = 0.0020; }

      let audioBoost = 0;
      if (agentState !== 'muted' && audioFrequencyData && audioFrequencyData.length > 0) {
        let sum = 0;
        for (let i = 0; i < 16; i++) sum += audioFrequencyData[i];
        audioBoost = (sum / 16) / 255;
      }

      const primaryBreathe = Math.sin(noiseVal * speed) * (intensity * 0.5);
      const secondaryHarmonic = Math.cos(noiseVal * (speed * 1.6)) * (intensity * 0.25 + audioBoost * 0.12);
      const phasesArr = particleSphere.geometry.userData.phases;

      for (let i = 0; i < count; i++) {
        const idx = i * 3;
        const shellPhase = (phasesArr && phasesArr[i]) || 0;
        const surfaceShimmer = Math.sin(noiseVal * 2.0 + shellPhase) * 0.02;
        const totalScale = 1.0 + primaryBreathe + secondaryHarmonic + surfaceShimmer;

        pos[idx]     = orig[idx]     * totalScale;
        pos[idx + 1] = orig[idx + 1] * totalScale;
        pos[idx + 2] = orig[idx + 2] * totalScale;
      }
      particleSphere.geometry.attributes.position.needsUpdate = true;
      particleSphere.rotation.y += rotSpeed;
    }

    // ── 2. Corona Dust ──
    if (coronaDust) { coronaDust.rotation.y -= 0.0008; }

    // ── 3. Plasma Core ──
    if (plasmaCore) {
      const baseScale = 0.92;
      let corePulse = baseScale * (1.0 + Math.sin(noiseVal * 1.3) * 0.07);
      if (agentState === 'thinking')  corePulse = baseScale * (1.0 + Math.sin(noiseVal * 3.2) * 0.15);
      else if (agentState === 'listening') corePulse = baseScale * (1.0 + Math.sin(noiseVal * 2.0) * 0.10);
      else if (agentState === 'muted')     corePulse = baseScale * (0.75 + Math.sin(noiseVal * 0.5) * 0.03);

      plasmaCore.scale.set(corePulse, corePulse, 1.0);
      plasmaCore.material.opacity = (agentState === 'thinking' || agentState === 'speaking') ? 0.95 : (agentState === 'muted' ? 0.35 : 0.85);
    }

    // ── 4. Gyroscopic Rings ──
    let mult = (agentState === 'thinking' || agentState === 'executing') ? 2.2 : (agentState === 'muted' ? 0.3 : 1.0);

    outerRings.forEach(r => {
      r.angle += r.spinSpeed * mult;
      r.mesh.rotation.z += r.spinSpeed * 0.5 * mult;
      r.sat.position.set(
        r.radius * Math.cos(r.angle),
        r.radius * Math.sin(r.angle),
        0
      );
    });

    renderer.render(scene, camera);
  }

  function setState(state) {
    agentState = state;
  }

  function getState() {
    return agentState;
  }

  function setAudioData(data) {
    audioFrequencyData = data;
  }

  function getAudioData() {
    return audioFrequencyData;
  }

  return { init, setState, getState, setAudioData, getAudioData };
})();
