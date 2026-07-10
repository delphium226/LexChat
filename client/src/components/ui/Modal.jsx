import { useEffect } from 'react';

// Shared dialog shell: a centered card over a dimmed backdrop. Consolidates the
// overlay, ESC-to-close, and backdrop-click dismissal that each modal used to
// re-implement inline. Callers pass their own header/body/footer as children
// and use `className` for the card's size/padding (append `relative` if the
// content positions an absolute close button). Set dismissable={false} to
// require an explicit close.
export default function Modal({ onClose, className = '', dismissable = true, children }) {
  useEffect(() => {
    if (!dismissable) return;
    const handler = e => {
      if (e.key === 'Escape') onClose?.();
    };
    document.addEventListener('keydown', handler);
    return () => document.removeEventListener('keydown', handler);
  }, [dismissable, onClose]);

  return (
    <div
      className="fixed inset-0 bg-black/50 flex items-center justify-center p-4 z-50"
      onMouseDown={
        dismissable
          ? e => {
              if (e.target === e.currentTarget) onClose?.();
            }
          : undefined
      }
    >
      <div className={`bg-paper rounded-lg shadow-xl border border-ink-200 ${className}`}>{children}</div>
    </div>
  );
}
