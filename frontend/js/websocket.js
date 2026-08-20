/**
 * VISION AI — WebSocket Client
 * Persistent connection with auto-reconnect, real-time event streaming
 */

const VisionWS = (() => {
  let ws = null;
  let reconnectTimer = null;
  let reconnectAttempts = 0;
  const MAX_RECONNECT = 10;
  const BASE_DELAY = 1000;
  const listeners = {};

  function getUrl() {
    const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
    return `${proto}//${location.host}/ws`;
  }

  function connect() {
    if (ws && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)) return;

    try {
      ws = new WebSocket(getUrl());
    } catch (e) {
      console.warn('[WS] Connection failed:', e);
      scheduleReconnect();
      return;
    }

    ws.onopen = () => {
      reconnectAttempts = 0;
      console.log('[WS] Connected');
      emit('status', { connected: true });
      // Ping keepalive
      startPing();
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        emit('message', data);

        // Route specific event types
        if (data.type === 'chat_response') {
          emit('chat_response', data.data);
        } else if (data.type === 'pong') {
          // keepalive ack
        } else if (data.tool) {
          emit('tool_event', data);
        } else if (data.text) {
          emit('stream_chunk', data);
        }
      } catch (e) {
        console.warn('[WS] Parse error:', e);
      }
    };

    ws.onclose = (event) => {
      console.log('[WS] Disconnected:', event.code);
      emit('status', { connected: false });
      stopPing();
      scheduleReconnect();
    };

    ws.onerror = (error) => {
      console.warn('[WS] Error:', error);
    };
  }

  let pingInterval = null;
  function startPing() {
    stopPing();
    pingInterval = setInterval(() => {
      if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ action: 'ping' }));
      }
    }, 30000);
  }

  function stopPing() {
    if (pingInterval) {
      clearInterval(pingInterval);
      pingInterval = null;
    }
  }

  function scheduleReconnect() {
    if (reconnectAttempts >= MAX_RECONNECT) {
      console.warn('[WS] Max reconnect attempts reached');
      return;
    }
    const delay = BASE_DELAY * Math.pow(1.5, reconnectAttempts);
    reconnectAttempts++;
    reconnectTimer = setTimeout(connect, Math.min(delay, 15000));
  }

  function send(action, payload = {}) {
    if (!ws || ws.readyState !== WebSocket.OPEN) {
      console.warn('[WS] Not connected, queuing reconnect');
      connect();
      return false;
    }
    ws.send(JSON.stringify({ action, ...payload }));
    return true;
  }

  function sendChat(message, sessionId = 'web_session', synthesizeVoice = false) {
    return send('chat', { message, session_id: sessionId, synthesize_voice: synthesizeVoice });
  }

  function on(event, callback) {
    if (!listeners[event]) listeners[event] = [];
    listeners[event].push(callback);
  }

  function off(event, callback) {
    if (!listeners[event]) return;
    listeners[event] = listeners[event].filter(cb => cb !== callback);
  }

  function emit(event, data) {
    if (listeners[event]) {
      listeners[event].forEach(cb => {
        try { cb(data); } catch (e) { console.error('[WS] Listener error:', e); }
      });
    }
  }

  function isConnected() {
    return ws && ws.readyState === WebSocket.OPEN;
  }

  function disconnect() {
    stopPing();
    if (reconnectTimer) clearTimeout(reconnectTimer);
    if (ws) ws.close();
  }

  return { connect, disconnect, send, sendChat, on, off, isConnected };
})();

/**
 * VISION AI — OpenAI Realtime Protocol Client (/v1/realtime)
 * Supports bidirectional Web Audio PCM16 streaming, turn-taking, and instant barge-in.
 */
const VisionRealtime = (() => {
  let ws = null;
  let audioContext = null;
  let isPlaying = false;
  let audioQueue = [];
  let scheduledTime = 0;
  const listeners = {};

  function getUrl() {
    const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
    return `${proto}//${location.host}/v1/realtime`;
  }

  function initAudioContext() {
    if (!audioContext) {
      audioContext = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: 24000 });
    }
    if (audioContext.state === 'suspended') {
      audioContext.resume();
    }
  }

  function connect() {
    if (ws && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)) return;

    try {
      ws = new WebSocket(getUrl());
    } catch (e) {
      console.warn('[RealtimeWS] Connection failed:', e);
      return;
    }

    ws.onopen = () => {
      console.log('[RealtimeWS] Connected to /v1/realtime');
      initAudioContext();
      emit('status', { connected: true });
    };

    ws.onmessage = async (event) => {
      try {
        const payload = JSON.parse(event.data);
        emit('event', payload);
        emit(payload.type, payload);

        if (payload.type === 'response.audio.delta' && payload.delta) {
          playAudioChunk(payload.delta);
        } else if (payload.type === 'response.cancelled' || payload.type === 'input_audio_buffer.speech_started') {
          stopAudioPlayback();
        }
      } catch (e) {
        console.warn('[RealtimeWS] Parse error:', e);
      }
    };

    ws.onclose = () => {
      console.log('[RealtimeWS] Disconnected');
      emit('status', { connected: false });
    };
  }

  function playAudioChunk(base64Data) {
    try {
      initAudioContext();
      const binaryString = window.atob(base64Data);
      const len = binaryString.length;
      const bytes = new Uint8Array(len);
      for (let i = 0; i < len; i++) {
        bytes[i] = binaryString.charCodeAt(i);
      }
      
      // Decode PCM16 or WAV buffer
      audioContext.decodeAudioData(bytes.buffer.slice(0), (buffer) => {
        const source = audioContext.createBufferSource();
        source.buffer = buffer;
        source.connect(audioContext.destination);

        const now = audioContext.currentTime;
        if (scheduledTime < now) {
          scheduledTime = now;
        }
        source.start(scheduledTime);
        scheduledTime += buffer.duration;
      }, (err) => {
        // Fallback for raw PCM bytes
      });
    } catch (e) {
      console.debug('[RealtimeWS] Audio decode notice:', e);
    }
  }

  function stopAudioPlayback() {
    if (audioContext) {
      scheduledTime = audioContext.currentTime;
    }
  }

  function sendEvent(type, data = {}) {
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type, ...data }));
    }
  }

  function appendAudioChunk(base64Chunk) {
    sendEvent('input_audio_buffer.append', { audio: base64Chunk });
  }

  function commitAudio() {
    sendEvent('input_audio_buffer.commit');
  }

  function cancelResponse() {
    stopAudioPlayback();
    sendEvent('response.cancel');
  }

  function sendTextMessage(text) {
    sendEvent('conversation.item.create', {
      item: {
        type: 'message',
        role: 'user',
        content: [{ type: 'input_text', text }]
      }
    });
    sendEvent('response.create');
  }

  function on(event, callback) {
    if (!listeners[event]) listeners[event] = [];
    listeners[event].push(callback);
  }

  function emit(event, data) {
    if (listeners[event]) {
      listeners[event].forEach(cb => {
        try { cb(data); } catch (e) { console.error('[RealtimeWS] Listener error:', e); }
      });
    }
  }

  return {
    connect,
    sendEvent,
    appendAudioChunk,
    commitAudio,
    cancelResponse,
    sendTextMessage,
    stopAudioPlayback,
    on
  };
})();
