export function LexMark({ size = 22, color = 'currentColor' }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" fill="none" aria-hidden="true">
      <circle cx="16" cy="16" r="4.2" fill={color} />
      <ellipse cx="16" cy="16" rx="13" ry="5.2" stroke={color} strokeWidth="1.6" fill="none" transform="rotate(-22 16 16)" />
      <circle cx="27.5" cy="11.3" r="1.8" fill={color} />
    </svg>
  );
}

export function LexWordmark({ size = 18, name = 'AILA', color, logoEmoji }) {
  const resolvedColor = color || 'var(--accent)';
  const markColor = color || '#2563eb';
  const iconSize = Math.round(size * 1.15);
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: 8,
      fontWeight: 700, fontSize: size, letterSpacing: '-0.01em',
      color: resolvedColor, fontFamily: 'var(--font-ui)',
    }}>
      {logoEmoji
        ? <span style={{ fontSize: iconSize, lineHeight: 1, userSelect: 'none' }} aria-hidden="true">{logoEmoji}</span>
        : <LexMark size={iconSize} color={markColor} />
      }
      {name}
    </span>
  );
}
