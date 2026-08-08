import React, { useState, useEffect, useRef } from 'react';
import { VisionConnection } from './services/visionConnection';
import { VisionSnapshot, AssistantState } from './models/visionState';
import { VisionConfig } from './config';
import { getBackgroundGradient, op } from './theme';
import { VisionFace } from './face/VisionFace';
import { SplashScreen } from './components/SplashScreen';
import { AuthScreen } from './components/AuthScreen';
import { TranscriptionPanel } from './components/TranscriptionPanel';
import { SystemMonitorCard } from './components/SystemMonitorCard';
import { WeatherCard } from './components/WeatherCard';
import { AgentActivityCard } from './components/AgentActivityCard';
import { CameraCard } from './components/CameraCard';
import { MusicPlayerCard } from './components/MusicPlayerCard';

import {
  FileText,
  Camera,
  PlayCircle,
  FlaskConical,
  Mic,
  MicOff,
  Sun,
  Moon,
  Send,
} from 'lucide-react';

export default function App() {
  const [booted, setBooted] = useState(false);
  const [isDark, setIsDark] = useState(true);
  const [snapshot, setSnapshot] = useState(new VisionSnapshot());
  const [cmdText, setCmdText] = useState('');
  const [viewportWidth, setViewportWidth] = useState(window.innerWidth);

  const connRef = useRef(null);

  useEffect(() => {
    const conn = new VisionConnection(VisionConfig.bridgeUrl);
    connRef.current = conn;
    const unsubscribe = conn.subscribe((snap) => {
      setSnapshot(snap);
    });
    conn.start();

    const handleResize = () => setViewportWidth(window.innerWidth);
    window.addEventListener('resize', handleResize);

    return () => {
      window.removeEventListener('resize', handleResize);
      unsubscribe();
      conn.stop();
    };
  }, []);

  const handleCommandSubmit = (e) => {
    if (e) e.preventDefault();
    if (!cmdText.trim()) return;
    if (connRef.current) {
      connRef.current.sendText(cmdText);
    }
    setCmdText('');
  };

  const handleChipClick = (cmd) => {
    if (connRef.current) {
      connRef.current.sendText(cmd);
    }
  };

  const glowColor = snapshot.colors.primary;
  const isAuthScreen = snapshot.stateString === 'auth_locked' || snapshot.stateString === 'auth_listening';

  const quickChips = [
    { label: '🧠 Knowledge RAG', cmd: 'search the knowledge base' },
    { label: '📝 Text Editor', cmd: 'open text editor' },
    { label: '📸 Screenshot', cmd: 'take screenshot' },
    { label: '👁️ What\'s on screen?', cmd: 'what is on my screen' },
    { label: '💻 System Info', cmd: 'show system info' },
    { label: '☀️ Weather', cmd: 'what is the weather' },
  ];

  const handleBootComplete = React.useCallback(() => setBooted(true), []);

  if (!booted) {
    return <SplashScreen onComplete={handleBootComplete} />;
  }

  if (isAuthScreen) {
    return (
      <AuthScreen
        stateString={snapshot.stateString}
        description={snapshot.description}
        onAuthenticated={() => {}}
      />
    );
  }

  return (
    <div
      style={{
        width: '100vw',
        height: '100vh',
        overflow: 'hidden',
        background: getBackgroundGradient(glowColor, isDark),
        color: isDark ? '#EAF2FF' : '#0B1526',
        display: 'flex',
        flexDirection: 'column',
        position: 'relative',
        transition: 'background 0.6s ease',
      }}
    >
      {/* Top Bar Navigation */}
      <header
        style={{
          padding: '16px 24px 8px 24px',
          display: 'flex',
          alignItems: 'center',
          gap: '12px',
          zIndex: 10,
        }}
      >
        <h1
          className="font-orbitron glow-text"
          style={{
            fontSize: '18px',
            fontWeight: 700,
            letterSpacing: '4px',
            margin: 0,
            color: isDark ? '#EAF2FF' : '#0B1526',
          }}
        >
          VISION
        </h1>

        {/* Live / Demo Pill */}
        <div
          style={{
            padding: '4px 10px',
            borderRadius: '12px',
            backgroundColor: snapshot.connected ? 'rgba(50, 215, 75, 0.15)' : 'rgba(255, 159, 10, 0.15)',
            border: `1px solid ${snapshot.connected ? 'rgba(50, 215, 75, 0.4)' : 'rgba(255, 159, 10, 0.4)'}`,
          }}
        >
          <span
            style={{
              color: snapshot.connected ? '#32D74B' : '#FF9F0A',
              fontSize: '10px',
              fontWeight: 700,
              letterSpacing: '1.5px',
            }}
          >
            {snapshot.connected ? 'LIVE' : 'DEMO'}
          </span>
        </div>

        <div style={{ flex: 1 }} />

        {/* Action Buttons */}
        <button
          onClick={() => handleChipClick('open text editor')}
          title="Open Text Editor"
          style={iconBtnStyle(false, glowColor, isDark)}
        >
          <FileText size={18} color="rgba(175, 194, 224, 0.8)" />
        </button>

        <button
          onClick={() => connRef.current?.screenshot()}
          title="Take Screenshot"
          style={iconBtnStyle(false, glowColor, isDark)}
        >
          <Camera size={18} color="rgba(175, 194, 224, 0.8)" />
        </button>

        <button
          onClick={() => connRef.current?.setDemo(!connRef.current?.demoMode)}
          title={connRef.current?.demoMode ? 'Demo mode on' : 'Try demo mode'}
          style={iconBtnStyle(connRef.current?.demoMode, glowColor, isDark)}
        >
          {connRef.current?.demoMode ? (
            <PlayCircle size={18} color={glowColor} />
          ) : (
            <FlaskConical size={18} color="rgba(175, 194, 224, 0.8)" />
          )}
        </button>

        <button
          onClick={() => connRef.current?.toggleMute()}
          title={snapshot.micMuted ? 'Unmute mic' : 'Mute mic'}
          style={iconBtnStyle(!snapshot.micMuted, glowColor, isDark)}
        >
          {snapshot.micMuted ? (
            <MicOff size={18} color="#FF3B30" />
          ) : (
            <Mic size={18} color={glowColor} />
          )}
        </button>

        <button
          onClick={() => setIsDark(!isDark)}
          title={isDark ? 'Switch to light mode' : 'Switch to dark mode'}
          style={iconBtnStyle(false, glowColor, isDark)}
        >
          {isDark ? <Sun size={18} color="rgba(175, 194, 224, 0.8)" /> : <Moon size={18} color="#0B1526" />}
        </button>
      </header>

      {/* Main Content Area */}
      <main
        style={{
          flex: 1,
          overflowY: 'auto',
          padding: '8px 20px',
          display: 'flex',
          flexDirection: 'column',
        }}
      >
        {viewportWidth >= 1100 ? (
          /* 3-COLUMN DESKTOP LAYOUT */
          <div style={{ flex: 1, display: 'flex', gap: '20px', alignItems: 'flex-start' }}>
            {/* Left Panel */}
            <div style={{ width: '320px', display: 'flex', flexDirection: 'column', gap: '12px' }}>
              <SystemMonitorCard isDark={isDark} />
              <WeatherCard city={VisionConfig.weatherCity} isDark={isDark} />
              <AgentActivityCard snapshot={snapshot} isDark={isDark} />
            </div>

            {/* Center Panel */}
            <div
              style={{
                flex: 1,
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                justifyContent: 'center',
                gap: '16px',
              }}
            >
              <VisionFace snapshot={snapshot} size={340} />
              <TranscriptionPanel snapshot={snapshot} />
            </div>

            {/* Right Panel */}
            <div style={{ width: '320px', display: 'flex', flexDirection: 'column', gap: '12px' }}>
              <CameraCard
                onStartWebcam={() => handleChipClick('start webcam')}
                onStopWebcam={() => handleChipClick('stop webcam')}
                isDark={isDark}
              />
              <MusicPlayerCard
                snapshot={snapshot}
                onPlayPause={() => connRef.current?.sendMedia('playpause')}
                onStop={() => connRef.current?.sendMedia('stop')}
                isDark={isDark}
              />
            </div>
          </div>
        ) : viewportWidth >= 740 ? (
          /* 2-COLUMN TABLET LAYOUT */
          <div style={{ flex: 1, display: 'flex', gap: '14px', alignItems: 'flex-start' }}>
            {/* Left Column: Face + Transcript */}
            <div
              style={{
                flex: 1,
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                gap: '14px',
              }}
            >
              <VisionFace snapshot={snapshot} size={280} />
              <TranscriptionPanel snapshot={snapshot} />
              <AgentActivityCard snapshot={snapshot} isDark={isDark} />
            </div>

            {/* Right Column: Utilities */}
            <div style={{ width: '310px', display: 'flex', flexDirection: 'column', gap: '12px' }}>
              <CameraCard
                onStartWebcam={() => handleChipClick('start webcam')}
                onStopWebcam={() => handleChipClick('stop webcam')}
                isDark={isDark}
              />
              <SystemMonitorCard isDark={isDark} />
              <WeatherCard city={VisionConfig.weatherCity} isDark={isDark} />
              <MusicPlayerCard
                snapshot={snapshot}
                onPlayPause={() => connRef.current?.sendMedia('playpause')}
                onStop={() => connRef.current?.sendMedia('stop')}
                isDark={isDark}
              />
            </div>
          </div>
        ) : (
          /* 1-COLUMN COMPACT LAYOUT */
          <div style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '14px' }}>
            <VisionFace snapshot={snapshot} size={240} />
            <TranscriptionPanel snapshot={snapshot} />
            <AgentActivityCard snapshot={snapshot} isDark={isDark} />
            <CameraCard
              onStartWebcam={() => handleChipClick('start webcam')}
              onStopWebcam={() => handleChipClick('stop webcam')}
              isDark={isDark}
            />
            <SystemMonitorCard isDark={isDark} />
            <WeatherCard city={VisionConfig.weatherCity} isDark={isDark} />
            <MusicPlayerCard
              snapshot={snapshot}
              onPlayPause={() => connRef.current?.sendMedia('playpause')}
              onStop={() => connRef.current?.sendMedia('stop')}
              isDark={isDark}
            />
          </div>
        )}
      </main>

      {/* Quick Action Command Chips */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'center',
          gap: '8px',
          padding: '6px 16px',
          overflowX: 'auto',
        }}
      >
        {quickChips.map((chip, idx) => (
          <button
            key={idx}
            onClick={() => handleChipClick(chip.cmd)}
            style={{
              padding: '6px 14px',
              borderRadius: '16px',
              backgroundColor: 'rgba(255, 255, 255, 0.04)',
              border: '1px solid rgba(57, 75, 110, 0.35)',
              color: isDark ? '#EAF2FF' : '#0B1526',
              fontSize: '11.5px',
              cursor: 'pointer',
              whiteSpace: 'nowrap',
              transition: 'background 0.2s ease',
            }}
          >
            {chip.label}
          </button>
        ))}
      </div>

      {/* Command Input Bar */}
      <footer style={{ padding: '8px 24px 20px 24px', display: 'flex', justifyContent: 'center' }}>
        <form
          onSubmit={handleCommandSubmit}
          style={{
            maxWidth: '640px',
            width: '100%',
            borderRadius: '28px',
            backgroundColor: 'rgba(255, 255, 255, 0.04)',
            border: '1px solid rgba(57, 75, 110, 0.35)',
            padding: '4px 6px 4px 20px',
            display: 'flex',
            alignItems: 'center',
          }}
        >
          <input
            type="text"
            value={cmdText}
            onChange={(e) => setCmdText(e.target.value)}
            placeholder="Type a command for VISION…"
            style={{
              flex: 1,
              background: 'transparent',
              border: 'none',
              outline: 'none',
              color: isDark ? '#EAF2FF' : '#0B1526',
              fontSize: '14px',
            }}
          />
          <button
            type="submit"
            style={{
              width: '40px',
              height: '40px',
              borderRadius: '50%',
              backgroundColor: 'transparent',
              border: 'none',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              cursor: 'pointer',
            }}
          >
            <Send size={18} color={glowColor} />
          </button>
        </form>
      </footer>
    </div>
  );
}

function iconBtnStyle(active, glowColor, isDark) {
  return {
    width: '40px',
    height: '40px',
    borderRadius: '50%',
    backgroundColor: active ? op(glowColor, 0.18) : 'rgba(255, 255, 255, 0.05)',
    border: `1px solid ${active ? op(glowColor, 0.5) : 'rgba(255, 255, 255, 0.08)'}`,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    cursor: 'pointer',
  };
}
