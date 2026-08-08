import React, { useState, useEffect } from 'react';
import { Cpu } from 'lucide-react';
import { categoryStyle, AssistantState } from '../models/visionState';
import { getGlassCardStyle, op } from '../theme';

export function AgentActivityCard({ snapshot, isDark = true }) {
  const [logs, setLogs] = useState([]);
  const [lastToolKey, setLastToolKey] = useState('');

  const s = snapshot;
  const accent = s.colors.primary;
  const cat = categoryStyle(s.category);

  useEffect(() => {
    const tool = (s.toolName || '').trim();
    const desc = (s.description || '').trim();
    const currentKey = `${tool}:${desc}`;

    if (currentKey && currentKey !== lastToolKey && s.state !== AssistantState.IDLE) {
      setLastToolKey(currentKey);
      const now = new Date();
      const timeStr = `${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}:${String(now.getSeconds()).padStart(2, '0')}`;

      setLogs((prev) => [
        {
          time: timeStr,
          icon: cat.icon,
          color: cat.color,
          title: tool ? tool.toUpperCase() : cat.label.toUpperCase(),
          description: desc ? desc : 'Executing active command...',
        },
        ...prev.slice(0, 4),
      ]);
    }
  }, [s.toolName, s.description, s.state, s.category, lastToolKey, cat]);

  const isRunning = s.state === AssistantState.THINKING || s.toolName || s.category;

  const activeToolName = s.toolName
    ? s.toolName.toUpperCase()
    : s.category
    ? s.category.toUpperCase()
    : 'AGENT CORE';

  const activeDesc = s.description
    ? s.description
    : s.state === AssistantState.THINKING
    ? 'Processing user request...'
    : 'Standby / Awaiting input';

  return (
    <div
      style={{
        ...getGlassCardStyle(accent, isDark),
        width: '320px',
        padding: '14px',
      }}
    >
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '10px' }}>
        <Cpu size={18} color={accent} />
        <span
          style={{
            color: '#EAF2FF',
            fontSize: '11px',
            fontWeight: 800,
            letterSpacing: '1.5px',
            flex: 1,
          }}
        >
          AGENT EXECUTION STREAM
        </span>

        <div
          style={{
            width: '7px',
            height: '7px',
            borderRadius: '50%',
            backgroundColor: isRunning ? accent : 'rgba(175, 194, 224, 0.4)',
            boxShadow: isRunning ? `0 0 6px ${accent}` : 'none',
          }}
        />
        <span
          style={{
            color: isRunning ? accent : 'rgba(175, 194, 224, 0.6)',
            fontSize: '9.5px',
            fontWeight: 700,
          }}
        >
          {isRunning ? 'ACTIVE' : 'IDLE'}
        </span>
      </div>

      {/* Active Tool Status Header Box */}
      <div
        style={{
          padding: '10px',
          borderRadius: '10px',
          backgroundColor: op(accent, 0.1),
          border: `1px solid ${op(accent, 0.3)}`,
          display: 'flex',
          alignItems: 'center',
          gap: '10px',
          marginBottom: logs.length > 0 ? '10px' : '0',
          transition: 'all 0.3s ease',
        }}
      >
        <div
          style={{
            width: '32px',
            height: '32px',
            borderRadius: '50%',
            backgroundColor: op(cat.color, 0.2),
            border: `1px solid ${op(cat.color, 0.5)}`,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: cat.color,
            fontSize: '14px',
            fontWeight: 'bold',
            flexShrink: 0,
          }}
        >
          {cat.icon}
        </div>
        <div style={{ overflow: 'hidden' }}>
          <div
            style={{
              color: accent,
              fontSize: '10.5px',
              fontWeight: 800,
              letterSpacing: '1.2px',
            }}
          >
            {activeToolName}
          </div>
          <div
            style={{
              color: '#EAF2FF',
              fontSize: '11.5px',
              lineHeight: 1.25,
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
            }}
          >
            {activeDesc}
          </div>
        </div>
      </div>

      {/* Recent Log Stream */}
      {logs.length > 0 && (
        <div>
          <div
            style={{
              color: 'rgba(175, 194, 224, 0.5)',
              fontSize: '9px',
              fontWeight: 700,
              letterSpacing: '1.5px',
              marginBottom: '6px',
            }}
          >
            RECENT EXECUTION LOG
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
            {logs.map((item, idx) => (
              <div key={idx} style={{ display: 'flex', alignItems: 'flex-start', gap: '6px', fontSize: '10.5px' }}>
                <span style={{ color: 'rgba(175, 194, 224, 0.5)', fontFamily: 'monospace', fontSize: '9.5px' }}>
                  {item.time}
                </span>
                <span style={{ color: item.color, fontSize: '10px' }}>{item.icon}</span>
                <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  <strong style={{ color: item.color }}>{item.title}: </strong>
                  <span style={{ color: 'rgba(175, 194, 224, 0.7)' }}>{item.description}</span>
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
