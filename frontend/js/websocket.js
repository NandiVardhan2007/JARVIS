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
