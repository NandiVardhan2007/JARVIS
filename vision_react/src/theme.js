// Theme tokens & styling helpers for VISION React frontend

export const VisionTheme = {
  // Dark Palette (default)
  bgTop: '#05070D',
  bgBottom: '#0B0F1A',
  card: 'rgba(32, 40, 64, 0.08)',
  cardBorder: 'rgba(57, 75, 110, 0.22)',
  textPrimary: '#EAF2FF',
  textDim: 'rgba(175, 194, 224, 0.6)',
  accent: '#00D4FF',

  // Light Palette
  bgTopLight: '#EFF3FA',
  bgBottomLight: '#DCE4F2',
  cardLight: 'rgba(255, 255, 255, 0.8)',
  cardBorderLight: 'rgba(11, 61, 145, 0.2)',
  textPrimaryLight: '#0B1526',
  textDimLight: 'rgba(27, 42, 68, 0.6)',
  accentLight: '#0072C6',
};

/**
 * Returns RGBA color with target opacity
 */
export function op(hexOrRgb, opacity) {
  if (!hexOrRgb) return `rgba(0, 212, 255, ${opacity})`;
  if (hexOrRgb.startsWith('rgba')) {
    return hexOrRgb.replace(/[\d\.]+\)$/g, `${opacity})`);
  }
  if (hexOrRgb.startsWith('#')) {
    let hex = hexOrRgb.replace('#', '');
    if (hex.length === 3) {
      hex = hex.split('').map(c => c + c).join('');
    }
    const r = parseInt(hex.substring(0, 2), 16);
    const g = parseInt(hex.substring(2, 4), 16);
    const b = parseInt(hex.substring(4, 6), 16);
    return `rgba(${r}, ${g}, ${b}, ${opacity})`;
  }
  return hexOrRgb;
}

export function getBackgroundGradient(glowColor, isDark = true) {
  const top = isDark ? VisionTheme.bgTop : VisionTheme.bgTopLight;
  const bottom = isDark ? VisionTheme.bgBottom : VisionTheme.bgBottomLight;
  return `radial-gradient(ellipse at 50% 25%, ${op(glowColor || VisionTheme.accent, isDark ? 0.12 : 0.18)}, ${top} 55%, ${bottom} 100%)`;
}

export function getGlassCardStyle(accentColor = VisionTheme.accent, isDark = true) {
  const base = isDark ? '255, 255, 255' : '0, 0, 0';
  const border = op(accentColor, isDark ? 0.32 : 0.4);
  const glow = op(accentColor, isDark ? 0.14 : 0.1);

  return {
    borderRadius: '20px',
    background: `linear-gradient(135deg, ${op(accentColor, isDark ? 0.1 : 0.14)}, rgba(${base}, 0.02))`,
    border: `1px solid ${border}`,
    boxShadow: `0 8px 32px 0 ${glow}, inset 0 0 12px 0 ${op(accentColor, 0.05)}`,
    backdropFilter: 'blur(16px)',
    WebkitBackdropFilter: 'blur(16px)',
  };
}
