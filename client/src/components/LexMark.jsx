export function LexMark({ size = 22, color = 'currentColor' }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" fill="none" aria-hidden="true">
      <circle cx="16" cy="16" r="4.2" fill={color} />
      <ellipse cx="16" cy="16" rx="13" ry="5.2" stroke={color} strokeWidth="1.6" fill="none" transform="rotate(-22 16 16)" />
      <circle cx="27.5" cy="11.3" r="1.8" fill={color} />
    </svg>
  );
}

export function LexWordmark({ size = 18 }) {
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: 8,
      fontWeight: 700, fontSize: size, letterSpacing: '-0.01em',
      color: 'var(--ink-900)', fontFamily: 'var(--font-ui)',
    }}>
      <LexMark size={Math.round(size * 1.15)} color="var(--accent)" />
      Lex<span style={{ color: 'var(--accent)' }}>Chat</span>
    </span>
  );
}
