import React, { useState } from 'react';
import { submitFeedback } from '../services/api';

const RESEARCH_OPTIONS = [
  'Always',
  'Most of the time',
  'About half the time',
  'Rarely',
  'Never',
];

const inputStyle = {
  width: '100%', boxSizing: 'border-box',
  padding: '6px 10px', borderRadius: 6,
  border: '1px solid var(--ink-300)',
  fontSize: 13, fontFamily: 'var(--font-ui)',
  color: 'var(--ink-800)', background: 'var(--ink-50)',
  outline: 'none',
};

const labelStyle = {
  fontSize: 12, fontWeight: 600, color: 'var(--ink-600)',
  marginBottom: 5, display: 'block', textTransform: 'uppercase', letterSpacing: '0.04em',
};

const WeeklyFeedbackBanner = ({ userId, onClose, onSubmitted }) => {
  const [timeSaved, setTimeSaved] = useState('');
  const [timeWithout, setTimeWithout] = useState('');
  const [researchSuccess, setResearchSuccess] = useState('');
  const [confidence, setConfidence] = useState(null);
  const [text, setText] = useState('');
  const [status, setStatus] = useState('idle');

  const dismiss = () => {
    localStorage.setItem(`weeklyFeedbackLastShown_${userId}`, Date.now().toString());
    onClose();
  };

  const handleSubmit = async () => {
    localStorage.setItem(`weeklyFeedbackLastShown_${userId}`, Date.now().toString());
    setStatus('submitting');
    try {
      const payload = {
        message: text.trim() || null,
        time_saved_hours: timeSaved !== '' ? parseFloat(timeSaved) : null,
        time_without_aila_hours: timeWithout !== '' ? parseFloat(timeWithout) : null,
        research_success: researchSuccess || null,
        confidence: confidence,
      };
      await submitFeedback(payload);
      if (onSubmitted) onSubmitted();
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
          <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--ink-900)', marginBottom: 12 }}>
            How is AILA working for you this week?
          </div>

          {status === 'success' ? (
            <div style={{ fontSize: 13, color: 'var(--ink-600)', paddingTop: 4 }}>
              Thank you for your feedback!
            </div>
          ) : (
            <>
              {/* Time inputs side-by-side */}
              <div style={{ display: 'flex', gap: 12, marginBottom: 14 }}>
                <div style={{ flex: 1 }}>
                  <label style={labelStyle}>Time AILA saved you (hrs)</label>
                  <input
                    type="number"
                    min="0"
                    step="0.5"
                    value={timeSaved}
                    onChange={e => setTimeSaved(e.target.value)}
                    placeholder="e.g. 1.5"
                    disabled={status === 'submitting'}
                    style={inputStyle}
                  />
                </div>
                <div style={{ flex: 1 }}>
                  <label style={labelStyle}>Time without AILA (hrs)</label>
                  <input
                    type="number"
                    min="0"
                    step="0.5"
                    value={timeWithout}
                    onChange={e => setTimeWithout(e.target.value)}
                    placeholder="e.g. 4"
                    disabled={status === 'submitting'}
                    style={inputStyle}
                  />
                </div>
              </div>

              {/* Research success */}
              <div style={{ marginBottom: 14 }}>
                <label style={labelStyle}>Did AILA find what you were looking for?</label>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px 14px' }}>
                  {RESEARCH_OPTIONS.map(opt => (
                    <label key={opt} style={{ display: 'flex', alignItems: 'center', gap: 5, fontSize: 13, color: 'var(--ink-700)', cursor: 'pointer' }}>
                      <input
                        type="radio"
                        name="researchSuccess"
                        value={opt}
                        checked={researchSuccess === opt}
                        onChange={() => setResearchSuccess(opt)}
                        disabled={status === 'submitting'}
                      />
                      {opt}
                    </label>
                  ))}
                </div>
              </div>

              {/* Confidence */}
              <div style={{ marginBottom: 14 }}>
                <label style={labelStyle}>Confidence in AILA's answers</label>
                <div style={{ display: 'flex', gap: 6 }}>
                  {[1, 2, 3, 4, 5].map(n => (
                    <button
                      key={n}
                      type="button"
                      onClick={() => setConfidence(confidence === n ? null : n)}
                      disabled={status === 'submitting'}
                      title={['Not confident', 'Slightly confident', 'Somewhat confident', 'Mostly confident', 'Very confident'][n - 1]}
                      style={{
                        width: 32, height: 32, borderRadius: 6, border: '1px solid',
                        borderColor: confidence >= n ? 'var(--accent)' : 'var(--ink-300)',
                        background: confidence >= n ? 'var(--accent)' : 'transparent',
                        color: confidence >= n ? 'white' : 'var(--ink-500)',
                        fontSize: 13, fontWeight: 600, cursor: 'pointer',
                        fontFamily: 'var(--font-ui)',
                        opacity: status === 'submitting' ? 0.6 : 1,
                      }}
                    >
                      {n}
                    </button>
                  ))}
                  {confidence !== null && (
                    <span style={{ fontSize: 12, color: 'var(--ink-500)', alignSelf: 'center', marginLeft: 4 }}>
                      {['Not confident', 'Slightly confident', 'Somewhat confident', 'Mostly confident', 'Very confident'][confidence - 1]}
                    </span>
                  )}
                </div>
              </div>

              {/* Free text */}
              <div style={{ marginBottom: 12 }}>
                <label style={labelStyle}>Anything else? (optional)</label>
                <textarea
                  value={text}
                  onChange={e => setText(e.target.value)}
                  placeholder="Suggestions, issues, or comments…"
                  rows={2}
                  disabled={status === 'submitting'}
                  style={{ ...inputStyle, resize: 'vertical' }}
                />
              </div>

              {status === 'error' && (
                <div style={{ fontSize: 12, color: 'var(--danger, #dc2626)', marginBottom: 8 }}>
                  Something went wrong — please try again.
                </div>
              )}

              <div style={{ display: 'flex', gap: 8 }}>
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
