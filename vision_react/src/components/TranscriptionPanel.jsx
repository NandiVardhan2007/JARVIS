import React from 'react';
import { AssistantState } from '../models/visionState';
import { op } from '../theme';
import { Wrench } from 'lucide-react';

export function TranscriptionPanel({ snapshot }) {
  const s = snapshot;
  const accent = s.colors.primary;
  const you = (s.transcript || '').trim();
  const reply = (s.response || '').trim();
  const showCaret = s.state === AssistantState.SPEAKING;

  const tool = (s.toolName || '').trim();
  const cat = (s.category || '').trim();
  const activeTool = tool ? tool : cat ? cat : '';

  const getStateLabel = () => {
    switch (s.state) {
      case AssistantState.LISTENING: return 'LISTENING';
      case AssistantState.THINKING: return 'THINKING';
      case AssistantState.SPEAKING: return 'SPEAKING';
      case AssistantState.INPUT: return 'COMMAND';
      case AssistantState.ALERT: return 'ALERT';
      case AssistantState.IDLE:
      default: return s.connected ? 'ONLINE' : 'DEMO';
    }
  };

  const getPlaceholder = () => {
    switch (s.state) {
      case AssistantState.LISTENING: return 'Listening…';
      case AssistantState.THINKING: return s.description || 'Thinking…';
      case AssistantState.IDLE: return s.connected ? 'Ready when you are.' : 'Offline · demo mode';
      default: return '…';
    }
  };

  return (
    <div
      style={{
        maxWidth: '680px',
        width: '100%',
        margin: '0 auto',
        padding: '22px 24px',
        borderRadius: '22px',
        background: `linear-gradient(135deg, ${op(accent, 0.08)}, rgba(255,255,255,0.02))`,
        border: `1.2px solid ${op(accent, 0.35)}`,
        boxShadow: `0 8px 32px ${op(accent, 0.15)}`,
        backdropFilter: 'blur(16px)',
        WebkitBackdropFilter: 'blur(16px)',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        textAlign: 'center',
        transition: 'all 0.35s ease',
      }}
    >
      {/* Top Header Chips */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '10px', marginBottom: '14px' }}>
        {/* State Chip */}
        <div
          style={{
            padding: '4px 14px',
            borderRadius: '16px',
            background: op(accent, 0.12),
            border: `1px solid ${op(accent, 0.3)}`,
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
          }}
        >
          <div
            style={{
              width: '7px',
              height: '7px',
              borderRadius: '50%',
              backgroundColor: accent,
              boxShadow: s.state !== AssistantState.IDLE ? `0 0 8px ${accent}` : 'none',
            }}
          />
          <span
            style={{
              color: accent,
              fontSize: '11px',
              fontWeight: 800,
              letterSpacing: '2.2px',
            }}
          >
            {getStateLabel()}
          </span>
        </div>

        {/* Tool Badge */}
        {activeTool && (
          <div
            style={{
              padding: '3px 10px',
              borderRadius: '12px',
              background: op(accent, 0.15),
              border: `1px solid ${op(accent, 0.4)}`,
              display: 'flex',
              alignItems: 'center',
              gap: '4px',
            }}
          >
            <Wrench size={11} color={accent} />
            <span
              style={{
                color: accent,
                fontSize: '9.5px',
                fontWeight: 700,
                letterSpacing: '1.5px',
              }}
            >
              {activeTool.toUpperCase()}
            </span>
          </div>
        )}
      </div>

      {/* Waveform visualizer bars when active */}
      {s.state !== AssistantState.IDLE && (
        <div style={{ display: 'flex', alignItems: 'center', gap: '4px', height: '20px', marginBottom: '12px' }}>
          {[12, 18, 8, 16, 10].map((h, i) => (
            <div
              key={i}
              className="animate-pulse-glow"
              style={{
                width: '3px',
                height: `${h}px`,
                backgroundColor: accent,
                borderRadius: '2px',
                animationDelay: `${i * 0.15}s`,
              }}
            />
          ))}
        </div>
      )}

      {/* User Transcript Line */}
      {you && (
        <div style={{ marginBottom: '12px' }}>
          <div
            style={{
              color: op(accent, 0.6),
              fontSize: '10px',
              fontWeight: 800,
              letterSpacing: '2px',
              marginBottom: '4px',
            }}
          >
            YOU
          </div>
          <div
            style={{
              color: 'rgba(175, 194, 224, 0.7)',
              fontSize: '15px',
              lineHeight: 1.4,
            }}
          >
            {you}
          </div>
        </div>
      )}

      {/* VISION Response Line */}
      <div>
        <div
          style={{
            color: accent,
            fontSize: '10px',
            fontWeight: 800,
            letterSpacing: '2px',
            marginBottom: '4px',
          }}
        >
          VISION
        </div>
        <div
          style={{
            color: reply ? '#EAF2FF' : 'rgba(175, 194, 224, 0.5)',
            fontSize: reply ? '18.5px' : '15px',
            lineHeight: 1.45,
            fontWeight: reply ? 500 : 400,
            fontStyle: reply ? 'normal' : 'italic',
          }}
        >
          {reply || getPlaceholder()}
          {showCaret && <span style={{ color: accent, fontWeight: 'bold' }}> ▌</span>}
        </div>
      </div>
    </div>
  );
}
