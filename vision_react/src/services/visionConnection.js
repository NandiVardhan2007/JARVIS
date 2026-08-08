import { VisionConfig } from '../config';
import { VisionSnapshot, AssistantState, NowPlaying } from '../models/visionState';

export class VisionConnection {
  constructor(url = VisionConfig.bridgeUrl) {
    this.url = url;
    this.snapshot = new VisionSnapshot();
    this.demoMode = true;
    this.listeners = new Set();
    this.ws = null;
    this.reconnectTimer = null;
    this.demoTimer = null;
    this.reconnectAttempts = 0;
    this.demoClock = 0;
    this.injectedText = null;
    this.injectedAt = -100;
  }

  subscribe(listener) {
    this.listeners.add(listener);
    listener(this.snapshot);
    return () => this.listeners.delete(listener);
  }

  notify() {
    this.listeners.forEach((fn) => fn(this.snapshot));
  }

  start() {
    this.connect();
    this.startDemo();
  }

  stop() {
    if (this.reconnectTimer) clearTimeout(this.reconnectTimer);
    if (this.demoTimer) clearInterval(this.demoTimer);
    if (this.ws) {
      try {
        this.ws.close();
      } catch (e) {}
    }
  }

  // WebSocket management
  connect() {
    if (this.reconnectTimer) clearTimeout(this.reconnectTimer);
    try {
      this.ws = new WebSocket(this.url);

      this.ws.onopen = () => {
        this.reconnectAttempts = 0;
        if (this.demoMode) this.stopDemo();
        this.apply(new VisionSnapshot({ ...this.snapshot, connected: true }));
      };

      this.ws.onmessage = (event) => {
        try {
          const decoded = JSON.parse(event.data);
          if (decoded && typeof decoded === 'object') {
            const merged = this.snapshot.merge(decoded);
            merged.connected = true;
            this.apply(merged);
          }
        } catch (e) {
          // ignore malformed JSON
        }
      };

      this.ws.onerror = () => {
        this.scheduleReconnect();
      };

      this.ws.onclose = () => {
        this.scheduleReconnect();
      };
    } catch (e) {
      this.scheduleReconnect();
    }
  }

  scheduleReconnect() {
    this.ws = null;
    if (this.snapshot.connected) {
      this.apply(new VisionSnapshot({ ...this.snapshot, connected: false }));
    }
    if (!this.demoMode) this.startDemo();

    this.reconnectAttempts = Math.min(this.reconnectAttempts + 1, 6);
    const delay = Math.min(1000 * Math.pow(2, this.reconnectAttempts), 15000);
    this.reconnectTimer = setTimeout(() => this.connect(), delay);
  }

  // Outbound messages
  send(obj) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      try {
        this.ws.send(JSON.stringify(obj));
      } catch (e) {}
    }
  }

  sendText(text) {
    const t = String(text || '').trim();
    if (!t) return;
    this.send({ type: 'text_input', text: t });
    if (this.demoMode) {
      this.demoInject(t);
    }
  }

  sendMedia(cmd) {
    this.send({ type: 'media', cmd });
  }

  screenshot() {
    this.send({ type: 'action', action: 'screenshot' });
  }

  toggleMute() {
    this.send({ type: 'mute' });
    if (this.demoMode) {
      this.apply(new VisionSnapshot({ ...this.snapshot, micMuted: !this.snapshot.micMuted }));
    }
  }

  setDemo(on) {
    if (on) {
      this.startDemo();
    } else {
      this.stopDemo();
      this.apply(new VisionSnapshot({ ...this.snapshot, connected: false }));
    }
  }

  // Demo mode simulation
  startDemo() {
    if (this.demoTimer) return;
    this.demoMode = true;
    this.demoClock = 0;
    this.demoTimer = setInterval(() => this.demoTick(), 16);
  }

  stopDemo() {
    this.demoMode = false;
    if (this.demoTimer) {
      clearInterval(this.demoTimer);
      this.demoTimer = null;
    }
  }

  demoInject(text) {
    this.injectedText = text;
    this.injectedAt = this.demoClock;
  }

  demoTick() {
    this.demoClock += 0.016;
    const t = this.demoClock;
    const phase = t % 16.0;

    let state;
    let ai = 0;
    let mic = 0;
    let transcript = this.snapshot.transcript;
    let response = this.snapshot.response;
    let category = '';
    let desc = '';

    if (this.injectedText && t - this.injectedAt < 6) {
      const dt = t - this.injectedAt;
      transcript = this.injectedText;
      if (dt < 1.5) {
        state = AssistantState.THINKING;
        category = 'AI';
        desc = 'Understanding your request';
      } else {
        state = AssistantState.SPEAKING;
        ai = this.voiceEnvelope(t);
        response = `Sure — working on "${this.injectedText}" right now.`;
      }
    } else if (phase < 3.5) {
      state = AssistantState.IDLE;
    } else if (phase < 6.5) {
      state = AssistantState.LISTENING;
      mic = Math.max(0, Math.min(1, 0.35 + 0.45 * (0.5 + 0.5 * Math.sin(t * 7)) + Math.random() * 0.15));
      transcript = "What's the weather and play some music";
    } else if (phase < 9) {
      state = AssistantState.THINKING;
      category = 'WEATHER';
      desc = 'Checking the forecast';
    } else {
      state = AssistantState.SPEAKING;
      ai = this.voiceEnvelope(t);
      response = "It's clear and pleasant. Now playing your mix.";
      category = 'MEDIA';
    }

    let snap = new VisionSnapshot({
      ...this.snapshot,
      state,
      aiLevel: ai,
      micLevel: mic,
      transcript,
      response,
      category: category || null,
      description: desc,
      connected: false,
    });

    if (phase >= 9 || category === 'MEDIA') {
      snap.nowPlaying = new NowPlaying({
        title: 'Neon Skyline',
        artist: 'The Arc Reactors',
        imageUrl: null,
        playing: true,
      });
    }

    this.apply(snap);
  }

  voiceEnvelope(t) {
    const env = 0.5 + 0.5 * Math.sin(t * 3.1);
    const syl = Math.sin(t * 17) * 0.5 + 0.5;
    return Math.max(0, Math.min(1, 0.15 + 0.85 * env * syl));
  }

  apply(s) {
    this.snapshot = s;
    this.notify();
  }
}
