import React from 'react';

// Small reusable button primitives (moved from App.jsx).

export function IBtn({ children, label, onClick, size = 30, disabled }) {
  return (
    <button
      aria-label={label}
      title={label}
      onClick={onClick}
      disabled={disabled}
      className="inline-flex items-center justify-center rounded-md text-ink-500 hover:bg-ink-100 hover:text-ink-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent flex-shrink-0"
      style={{ width: size, height: size }}
    >{children}</button>
  );
}

export function GhostBtn({ children, icon, onClick, disabled, title }) {
  return (
    <button
      onClick={disabled ? undefined : onClick}
      disabled={disabled}
      title={title}
      className={`inline-flex items-center gap-1.5 px-3 py-1.5 font-ui text-sm font-medium rounded-md border border-ink-200 bg-paper focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent ${
 disabled
 ? 'text-ink-300 opacity-60 cursor-not-allowed'
 : 'text-ink-900 hover:bg-ink-50 cursor-pointer'
 }`}
    >{icon}{children}</button>
  );
}
