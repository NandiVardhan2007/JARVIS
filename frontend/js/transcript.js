/**
 * VISION AI — Transcript & Waveform Module
 * Live transcription logging, waveform visualization, clipboard export
 */

const VisionTranscript = (() => {
  let wavePhase = 0;
  let currentWaveAmp = 0;

  const transcriptHistory = [
    {
      speaker: 'ai',
      label: 'VISION',
      text: 'VISION is online. Continuous hands-free VAD speech recognition is active.',
      time: 'System',
      timestamp: new Date().toISOString()
    }
  ];

  function init() {
    // Start waveform rendering loop
    requestAnimationFrame(renderLoop);
  }

  function renderLoop() {
    renderVoiceWaveform();
    requestAnimationFrame(renderLoop);
  }

  // ── Log to Transcriptions Stream ──
  function logTranscript(speaker, label, text) {
    const stream = document.getElementById('transcriptions-stream');
    if (!stream) return;

    const entry = document.createElement('div');
    entry.className = `transcript-entry ${speaker}`;

    const now = new Date();
    const time = now.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
    const speakerIcon = speaker === 'user' ? 'user' : 'bot';

    transcriptHistory.push({
      speaker, label, text, time,
      timestamp: now.toISOString()
    });

    entry.innerHTML = `
      <div class="transcript-meta">
        <span class="transcript-speaker">
          <i data-lucide="${speakerIcon}" class="icon-xs"></i>
          <span>${escapeHtml(label)}</span>
        </span>
        <span class="transcript-time">${time}</span>
      </div>
      <div class="transcript-text">${renderMarkdown(text)}</div>
    `;
    stream.prepend(entry);
    while (stream.children.length > 25) stream.lastChild.remove();
    refreshIcons();
  }

  // ── Log to Autonomous Action Monitor ──
  function logAction(type, name, desc) {
    const stream = document.getElementById('actions-stream');
    if (!stream) return;

    const item = document.createElement('div');
    item.className = 'action-item';

    const iconName = type === 'tool' ? getToolIconName(name) : (type === 'ai' ? 'sparkles' : 'zap');

    item.innerHTML = `
      <div class="action-icon-box">
        <i data-lucide="${iconName}" class="icon-sm"></i>
      </div>
      <div class="action-content">
        <div class="action-name">${escapeHtml(name)}</div>
        <div class="action-desc">${escapeHtml(desc.substring(0, 80))}</div>
      </div>
    `;
    stream.prepend(item);
    while (stream.children.length > 15) stream.lastChild.remove();
    refreshIcons();
  }

  // ── Copy Transcripts as JSON ──
  async function copyAsJSON() {
    const copyBtn = document.getElementById('copy-transcripts-btn');

    let exportList = transcriptHistory.map((item, idx) => ({
      index: idx + 1,
      speaker: item.speaker,
      label: item.label,
      text: item.text,
      time: item.time,
      timestamp: item.timestamp || new Date().toISOString()
    }));

    const payload = {
      exported_at: new Date().toISOString(),
      total_messages: exportList.length,
      session_id: 'vision_hud_session',
      transcripts: exportList
    };

    const jsonStr = JSON.stringify(payload, null, 2);

    let copied = false;
    try {
      if (navigator.clipboard && navigator.clipboard.writeText) {
        await navigator.clipboard.writeText(jsonStr);
        copied = true;
      } else {
        throw new Error('Clipboard API unavailable');
      }
    } catch (e) {
      try {
        const tempArea = document.createElement('textarea');
        tempArea.value = jsonStr;
        tempArea.setAttribute('readonly', '');
        tempArea.style.position = 'fixed';
        tempArea.style.left = '-9999px';
        document.body.appendChild(tempArea);
        tempArea.focus();
        tempArea.select();
        copied = document.execCommand('copy');
        document.body.removeChild(tempArea);
      } catch (err) { copied = false; }
    }

    if (copyBtn) {
      if (copied) {
        copyBtn.classList.add('copied');
        copyBtn.innerHTML = `<i data-lucide="check" class="icon-xs"></i><span class="copy-btn-text">COPIED JSON!</span>`;
        refreshIcons();
        setTimeout(() => {
          copyBtn.classList.remove('copied');
          copyBtn.innerHTML = `<i data-lucide="copy" class="icon-xs"></i><span class="copy-btn-text">COPY JSON</span>`;
          refreshIcons();
        }, 2000);
      } else {
        copyBtn.innerHTML = `<i data-lucide="alert-circle" class="icon-xs"></i><span class="copy-btn-text">FAILED</span>`;
        refreshIcons();
        setTimeout(() => {
          copyBtn.innerHTML = `<i data-lucide="copy" class="icon-xs"></i><span class="copy-btn-text">COPY JSON</span>`;
          refreshIcons();
        }, 2000);
      }
    }
  }

  // ── Voice Waveform Renderer ──
  function renderVoiceWaveform() {
    const waveformCanvas = document.getElementById('waveform-canvas');
    if (!waveformCanvas) return;
    const waveCtx = waveformCanvas.getContext('2d');
    if (!waveCtx) return;

    const agentState = VisionOrb.getState();
    const audioFrequencyData = VisionOrb.getAudioData();
    const isSpeaking = (agentState === 'speaking');
    const isListening = (agentState === 'listening');
    const targetAmp = (isSpeaking || isListening) ? 1.0 : 0.0;

    currentWaveAmp += (targetAmp - currentWaveAmp) * 0.09;
    wavePhase += (currentWaveAmp > 0.1) ? 0.08 : 0.03;

    const w = waveformCanvas.width;
    const h = waveformCanvas.height;
    const midY = h / 2;
    waveCtx.clearRect(0, 0, w, h);

    // Baseline
    waveCtx.beginPath();
    waveCtx.moveTo(0, midY);
    for (let x = 0; x <= w; x += 4) {
      const idleRipple = Math.sin(wavePhase * 1.5 + x * 0.04) * 1.2 * (1.0 - currentWaveAmp);
      waveCtx.lineTo(x, midY + idleRipple);
    }
    waveCtx.strokeStyle = isSpeaking
      ? 'rgba(34, 211, 238, 0.7)'
      : (isListening ? 'rgba(52, 211, 153, 0.7)' : 'rgba(34, 211, 238, 0.35)');
    waveCtx.lineWidth = 1.5;
    waveCtx.shadowBlur = (currentWaveAmp > 0.1) ? 8 : 4;
    waveCtx.shadowColor = isSpeaking ? '#22d3ee' : (isListening ? '#34d399' : 'rgba(34, 211, 238, 0.5)');
    waveCtx.stroke();

    // Equalizer Bars
    const numBars = 28;
    const barWidth = 4;
    const gap = (w - (numBars * barWidth)) / (numBars - 1);
    const mid = numBars / 2;

    for (let i = 0; i < numBars; i++) {
      const distFromCenter = Math.abs(i - mid + 0.5) / mid;
      const envelope = Math.cos(distFromCenter * Math.PI * 0.5);

      const wave1 = Math.sin(wavePhase * 2.5 + i * 0.45);
      const wave2 = Math.cos(wavePhase * 1.8 + i * 0.65);
      const wave3 = Math.sin(wavePhase * 3.2 - i * 0.35);
      const rawAmp = Math.abs(wave1 * 0.5 + wave2 * 0.35 + wave3 * 0.15);

      let audioAmp = 0;
      if (audioFrequencyData && audioFrequencyData.length > 0) {
        const freqIdx = i % 16;
        audioAmp = (audioFrequencyData[freqIdx] / 255) * 0.8;
      }

      const activeHeight = (rawAmp * 26 + audioAmp * 18 + 2) * envelope;
      const barHeight = Math.max(2, activeHeight * currentWaveAmp + 2);
      const x = i * (barWidth + gap);
      const y = (h - barHeight) / 2;

      const grad = waveCtx.createLinearGradient(0, y, 0, y + barHeight);
      if (isSpeaking) {
        grad.addColorStop(0, '#22d3ee');
        grad.addColorStop(0.5, '#6366f1');
        grad.addColorStop(1, '#ec4899');
      } else if (isListening) {
        grad.addColorStop(0, '#34d399');
        grad.addColorStop(0.5, '#22d3ee');
        grad.addColorStop(1, '#38bdf8');
      } else {
        grad.addColorStop(0, 'rgba(34, 211, 238, 0.4)');
        grad.addColorStop(1, 'rgba(99, 102, 241, 0.2)');
      }

      waveCtx.fillStyle = grad;
      waveCtx.shadowBlur = (currentWaveAmp > 0.1) ? 8 : 3;
      waveCtx.shadowColor = isSpeaking ? 'rgba(34, 211, 238, 0.7)' : (isListening ? 'rgba(52, 211, 153, 0.7)' : 'rgba(34, 211, 238, 0.3)');

      if (waveCtx.roundRect) {
        waveCtx.beginPath();
        waveCtx.roundRect(x, y, barWidth, barHeight, 2);
        waveCtx.fill();
      } else {
        waveCtx.fillRect(x, y, barWidth, barHeight);
      }
    }
  }

  // ── Helpers ──
  function getToolIconName(toolName) {
    const name = (toolName || '').toLowerCase();
    if (name.includes('whatsapp') || name.includes('message')) return 'message-square';
    if (name.includes('browser') || name.includes('web') || name.includes('search')) return 'globe';
    if (name.includes('file') || name.includes('document') || name.includes('folder')) return 'file-text';
    if (name.includes('terminal') || name.includes('ssh') || name.includes('command') || name.includes('code') || name.includes('python')) return 'terminal';
    if (name.includes('media') || name.includes('youtube') || name.includes('music')) return 'play-circle';
    if (name.includes('battery') || name.includes('hardware') || name.includes('system') || name.includes('cpu')) return 'cpu';
    if (name.includes('memory') || name.includes('remember') || name.includes('recall')) return 'database';
    if (name.includes('reminder') || name.includes('timer') || name.includes('time') || name.includes('date')) return 'clock';
    if (name.includes('phone') || name.includes('mobile')) return 'smartphone';
    if (name.includes('mic') || name.includes('voice') || name.includes('speech')) return 'mic';
    return 'zap';
  }

  function renderMarkdown(text) {
    if (!text) return '';
    let h = text;
    h = h.replace(/```(\w*)\n?([\s\S]*?)```/g, (_, lang, code) => `<pre><code>${escapeHtml(code.trim())}</code></pre>`);
    h = h.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
    h = h.replace(/`([^`]+)`/g, '<code>$1</code>');
    h = h.replace(/^[•\-\*]\s*(.+)$/gm, '<li>$1</li>');
    h = h.replace(/(<li>.+<\/li>)/s, '<ul>$1</ul>');
    h = h.replace(/\n\n+/g, '</p><p>');
    h = h.replace(/\n/g, '<br>');
    return `<p>${h}</p>`;
  }

  function escapeHtml(s) {
    const d = document.createElement('div');
    d.textContent = s; return d.innerHTML;
  }

  function refreshIcons() {
    if (window.lucide && lucide.createIcons) lucide.createIcons();
  }

  return { init, logTranscript, logAction, copyAsJSON };
})();
