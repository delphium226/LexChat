import React, { useState, useEffect } from 'react';
import { submitFeedback } from '../services/api';

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

const WeeklyFeedbackBanner = ({ userId, onClose, onSubmitted, botName = 'AILA' }) => {
  const [timeWithout, setTimeWithout] = useState('');
  const [timeSaved, setTimeSaved] = useState('');
  const [confidence, setConfidence] = useState(null);
  const [usability, setUsability] = useState(null);
  const [verificationHours, setVerificationHours] = useState('');
  const [text, setText] = useState('');
  const [status, setStatus] = useState('idle');

  const dismiss = () => {
    localStorage.setItem(`weeklyFeedbackLastShown_${userId}`, Date.now().toString());
    onClose();
  };

  useEffect(() => {
    const handler = (e) => { if (e.key === 'Escape') dismiss(); };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, []);

  const handleSubmit = async () => {
    localStorage.setItem(`weeklyFeedbackLastShown_${userId}`, Date.now().toString());
    setStatus('submitting');
    try {
      const payload = {
        message: text.trim() || null,
        time_saved_hours: timeSaved !== '' ? parseFloat(timeSaved) : null,
        time_without_aila_hours: timeWithout !== '' ? parseFloat(timeWithout) : null,
        confidence: confidence,
        usability: usability,
        verification_hours: verificationHours !== '' ? parseFloat(verificationHours) : null,
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
    <div
      style={{
        position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.5)', zIndex: 50,
        display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 16,
      }}
      onClick={(e) => { if (e.target === e.currentTarget) dismiss(); }}
    >
      <div style={{
        background: 'var(--paper)', border: '1px solid var(--ink-200)',
        borderRadius: 12, boxShadow: '0 20px 60px rgba(0,0,0,0.25)',
        width: '100%', maxWidth: 560, maxHeight: '90vh',
        overflowY: 'auto', padding: '20px 24px',
        fontFamily: 'var(--font-ui)',
      }}>
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 12 }}>
        <div style={{ flex: 1 }}>
          <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--ink-900)', marginBottom: 12 }}>
            How is {botName} working for you this week?
          </div>

          {status === 'success' ? (
            <div style={{ fontSize: 13, color: 'var(--ink-600)', paddingTop: 4 }}>
              Thank you for your feedback!
            </div>
          ) : (
            <>
              {/* Q1: Time without AILA */}
              <div style={{ marginBottom: 14 }}>
                <label style={labelStyle}>
                  Think about the tasks you used the AI assistant for this past week. If you had to complete those exact same tasks manually, approximately how much total time would it have taken you? (hours)
                </label>
                <input
                  type="number"
                  min="0"
                  step="0.1"
                  value={timeWithout}
                  onChange={e => setTimeWithout(e.target.value)}
                  placeholder="e.g. 4.0"
                  disabled={status === 'submitting'}
                  style={inputStyle}
                />
              </div>

              {/* Q2: Time saved */}
              <div style={{ marginBottom: 14 }}>
                <label style={labelStyle}>
                  By using the AI assistant for those tasks, how much time do you estimate you actively saved this week? (hours)
                </label>
                <input
                  type="number"
                  min="0"
                  step="0.1"
                  value={timeSaved}
                  onChange={e => setTimeSaved(e.target.value)}
                  placeholder="e.g. 1.5"
                  disabled={status === 'submitting'}
                  style={inputStyle}
                />
              </div>

              {/* Q3: Confidence */}
              <div style={{ marginBottom: 14 }}>
                <label style={labelStyle}>Confidence in {botName}'s answers</label>
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

              {/* Q4: Usability */}
              <div style={{ marginBottom: 14 }}>
                <label style={labelStyle}>How easy was it to use {botName}?</label>
                <div style={{ display: 'flex', gap: 6 }}>
                  {[1, 2, 3, 4, 5].map(n => (
                    <button
                      key={n}
                      type="button"
                      onClick={() => setUsability(usability === n ? null : n)}
                      disabled={status === 'submitting'}
                      title={['Very difficult', 'Difficult', 'Neither easy nor difficult', 'Easy', 'Very easy'][n - 1]}
                      style={{
                        width: 32, height: 32, borderRadius: 6, border: '1px solid',
                        borderColor: usability >= n ? 'var(--accent)' : 'var(--ink-300)',
                        background: usability >= n ? 'var(--accent)' : 'transparent',
                        color: usability >= n ? 'white' : 'var(--ink-500)',
                        fontSize: 13, fontWeight: 600, cursor: 'pointer',
                        fontFamily: 'var(--font-ui)',
                        opacity: status === 'submitting' ? 0.6 : 1,
                      }}
                    >
                      {n}
                    </button>
                  ))}
                  {usability !== null && (
                    <span style={{ fontSize: 12, color: 'var(--ink-500)', alignSelf: 'center', marginLeft: 4 }}>
                      {['Very difficult', 'Difficult', 'Neither easy nor difficult', 'Easy', 'Very easy'][usability - 1]}
                    </span>
                  )}
                </div>
              </div>

              {/* Q5: Verification time */}
              <div style={{ marginBottom: 14 }}>
                <label style={labelStyle}>
                  How many hours did you spend checking or correcting the outputs of ALIA this week, if any?
                </label>
                <input
                  type="number"
                  min="0"
                  step="0.1"
                  value={verificationHours}
                  onChange={e => setVerificationHours(e.target.value)}
                  placeholder="e.g. 0.5"
                  disabled={status === 'submitting'}
                  style={inputStyle}
                />
              </div>

              {/* Q6: Free text */}
              <div style={{ marginBottom: 12 }}>
                <label style={labelStyle}>Is there anything we should do to make ALIA better? (optional)</label>
                <textarea
                  value={text}
                  onChange={e => setText(e.target.value)}
                  placeholder="Share any suggestions…"
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
                  className="bg-brand text-white font-ui text-sm font-medium rounded-md px-4 py-2 hover:bg-brand-hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-1 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {status === 'submitting' ? 'Submitting…' : 'Submit'}
                </button>
                <button
                  onClick={dismiss}
                  className="bg-paper border border-ink-200 text-ink-900 font-ui text-sm font-medium rounded-md px-4 py-2 hover:bg-ink-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent"
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
          className="size-6 flex items-center justify-center rounded-md text-ink-400 hover:bg-ink-100 hover:text-ink-900 flex-shrink-0 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent"
        >
          <svg width={14} height={14} viewBox="0 0 24 24" fill="none"
            stroke="currentColor" strokeWidth={2} strokeLinecap="round">
            <path d="M18 6 6 18M6 6l12 12" />
          </svg>
        </button>
      </div>
      </div>
    </div>
  );
};

export default WeeklyFeedbackBanner;
