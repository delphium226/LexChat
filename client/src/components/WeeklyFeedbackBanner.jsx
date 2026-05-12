import React, { useState } from 'react';
import { submitFeedback } from '../services/api';

const WeeklyFeedbackBanner = ({ userId, onClose }) => {
  const [text, setText] = useState('');
  const [status, setStatus] = useState('idle');

  const dismiss = () => {
    localStorage.setItem(`weeklyFeedbackLastShown_${userId}`, Date.now().toString());
    onClose();
  };

  const handleSubmit = async () => {
    if (!text.trim()) { dismiss(); return; }
    localStorage.setItem(`weeklyFeedbackLastShown_${userId}`, Date.now().toString());
    setStatus('submitting');
    try {
      await submitFeedback(text.trim());
      setStatus('success');
      setTimeout(onClose, 1800);
    } catch {
      setStatus('error');
    }
  };

  return (
    <div style={{
      marginBottom: 18,
      padding: '16px 20px',
      background: 'var(--paper)',
      border: '1px solid var(--ink-200)',
      borderRadius: 12,
      boxShadow: 'var(--shadow-sm)',
      fontFamily: 'var(--font-ui)',
    }}>
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 12 }}>
        <div style={{ flex: 1 }}>
          <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--ink-900)', marginBottom: 4 }}>
            How is AILA working for you this week?
          </div>
          {status === 'success' ? (
            <div style={{ fontSize: 13, color: 'var(--ink-600)', paddingTop: 4 }}>
              Thank you for your feedback!
            </div>
          ) : (
            <>
              <textarea
                value={text}
                onChange={e => setText(e.target.value)}
                placeholder="Share any thoughts, suggestions, or issues…"
                rows={2}
                disabled={status === 'submitting'}
                style={{
                  width: '100%', boxSizing: 'border-box', marginTop: 8,
                  padding: '7px 10px', borderRadius: 6,
                  border: '1px solid var(--ink-300)',
                  fontSize: 13, fontFamily: 'var(--font-ui)',
                  color: 'var(--ink-800)', background: 'var(--ink-50)',
                  resize: 'vertical', outline: 'none',
                }}
              />
              {status === 'error' && (
                <div style={{ fontSize: 12, color: 'var(--danger, #dc2626)', marginTop: 4 }}>
                  Something went wrong — please try again.
                </div>
              )}
              <div style={{ display: 'flex', gap: 8, marginTop: 10 }}>
                <button
                  onClick={handleSubmit}
                  disabled={status === 'submitting'}
                  style={{
                    padding: '6px 16px', borderRadius: 6, border: 'none',
                    background: 'var(--accent)', color: 'white',
                    fontSize: 13, fontWeight: 500,
                    cursor: status === 'submitting' ? 'not-allowed' : 'pointer',
                    opacity: status === 'submitting' ? 0.6 : 1,
                    fontFamily: 'var(--font-ui)',
                  }}
                >
                  {status === 'submitting' ? 'Submitting…' : 'Submit'}
                </button>
                <button
                  onClick={dismiss}
                  style={{
                    padding: '6px 16px', borderRadius: 6,
                    border: '1px solid var(--ink-200)', background: 'transparent',
                    fontSize: 13, fontWeight: 500, color: 'var(--ink-600)',
                    cursor: 'pointer', fontFamily: 'var(--font-ui)',
                  }}
                >
                  Maybe Later
                </button>
              </div>
            </>
          )}
        </div>
        <button
          onClick={dismiss}
          aria-label="Dismiss"
          style={{
            width: 24, height: 24, border: 'none', background: 'transparent',
            cursor: 'pointer', color: 'var(--ink-400)',
            display: 'grid', placeItems: 'center', borderRadius: 4, flexShrink: 0,
          }}
        >
          <svg width={14} height={14} viewBox="0 0 24 24" fill="none"
            stroke="currentColor" strokeWidth={2} strokeLinecap="round">
            <path d="M18 6 6 18M6 6l12 12" />
          </svg>
        </button>
      </div>
    </div>
  );
};

export default WeeklyFeedbackBanner;
