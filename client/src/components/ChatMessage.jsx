import React, { useState, useMemo, useRef, useEffect } from 'react';
import ReactDOM from 'react-dom';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { marked } from 'marked';
import { rateMessage, addMatterNote } from '../services/api';
import { CopyIcon, RefreshIcon, BookmarkIcon } from './ui/icons';


function formatTime(isoDate) {
  if (!isoDate) return '';
  const d = new Date(isoDate);
  return d.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' });
}

function formatCost(usd) {
  if (!usd || usd <= 0) return null;
  if (usd < 0.01) return '<$0.01';
  return `$${usd.toFixed(2)}`;
}

function ToolBtn({ label, onClick, active, disabled, error, children }) {
  const [h, setH] = React.useState(false);
  return (
    <button
      aria-label={label}
      title={label}
      onClick={disabled ? undefined : onClick}
      onMouseEnter={() => !disabled && setH(true)}
      onMouseLeave={() => setH(false)}
      style={{
        width: 30, height: 30, borderRadius: 8, border: 'none',
        background: error ? 'var(--red-soft, #fee2e2)' : active ? 'var(--accent-soft)' : (h ? 'var(--ink-100)' : 'transparent'),
        color: error ? 'var(--red, #dc2626)' : active ? 'var(--accent)' : disabled ? 'var(--ink-300)' : 'var(--ink-500)',
        display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
        cursor: disabled ? 'not-allowed' : 'pointer', transition: 'background 120ms',
        opacity: disabled ? 0.5 : 1,
      }}
    >{children}</button>
  );
}

function ThumbsDownModal({ text, onChange, onCancel, onSubmit, submitting }) {
  const textareaRef = useRef(null);

  useEffect(() => {
    textareaRef.current?.focus();
    const onKey = (e) => { if (e.key === 'Escape') onCancel(); };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [onCancel]);

  return (
    <div
      onClick={onCancel}
      style={{
        position: 'fixed', inset: 0, zIndex: 1000,
        background: 'rgba(0,0,0,0.45)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        padding: 24,
      }}
    >
      <div
        onClick={e => e.stopPropagation()}
        style={{
          background: 'var(--paper)', borderRadius: 12,
          boxShadow: '0 8px 32px rgba(0,0,0,0.18)',
          padding: '24px 28px', width: '100%', maxWidth: 460,
          fontFamily: 'var(--font-ui)',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
          <div style={{ fontSize: 15, fontWeight: 600, color: 'var(--ink-900)' }}>
            What went wrong?
          </div>
          <button
            onClick={onCancel}
            className="size-7 flex items-center justify-center rounded-md text-ink-400 hover:bg-ink-100 hover:text-ink-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent"
            aria-label="Close"
          >
            <svg width={16} height={16} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round">
              <path d="M18 6 6 18M6 6l12 12" />
            </svg>
          </button>
        </div>
        <p style={{ fontSize: 13, color: 'var(--ink-500)', marginBottom: 14, lineHeight: 1.5 }}>
          Your feedback helps improve response quality. Reason is optional.
        </p>
        <textarea
          ref={textareaRef}
          value={text}
          onChange={e => onChange(e.target.value)}
          placeholder="Describe the issue with this response…"
          rows={4}
          style={{
            width: '100%', boxSizing: 'border-box', padding: '8px 10px',
            borderRadius: 7, border: '1px solid var(--ink-300)',
            fontSize: 13, fontFamily: 'var(--font-ui)',
            color: 'var(--ink-800)', background: 'var(--paper)',
            resize: 'vertical', outline: 'none', lineHeight: 1.5,
          }}
          onFocus={e => { e.target.style.borderColor = 'var(--accent)'; }}
          onBlur={e => { e.target.style.borderColor = 'var(--ink-300)'; }}
        />
        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8, marginTop: 14 }}>
          <button
            onClick={onCancel}
            className="bg-paper border border-ink-200 text-ink-900 font-ui text-sm font-medium rounded-md px-4 py-2 hover:bg-ink-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent"
          >Cancel</button>
          <button
            onClick={onSubmit}
            disabled={submitting}
            className="bg-brand text-white font-ui text-sm font-medium rounded-md px-4 py-2 hover:bg-brand-hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-1 disabled:opacity-50 disabled:cursor-not-allowed"
          >{submitting ? 'Submitting…' : 'Submit feedback'}</button>
        </div>
      </div>
    </div>
  );
}


function ConfirmModal({ message, confirmLabel, onConfirm, onCancel }) {
  useEffect(() => {
    const onKey = (e) => { if (e.key === 'Escape') onCancel(); };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [onCancel]);

  return (
    <div
      onClick={onCancel}
      style={{
        position: 'fixed', inset: 0, zIndex: 1000,
        background: 'rgba(0,0,0,0.45)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        padding: 24,
      }}
    >
      <div
        onClick={e => e.stopPropagation()}
        style={{
          background: 'var(--paper)', borderRadius: 12,
          boxShadow: '0 8px 32px rgba(0,0,0,0.18)',
          padding: '24px 28px', width: '100%', maxWidth: 400,
          fontFamily: 'var(--font-ui)',
        }}
      >
        <div style={{ fontSize: 15, fontWeight: 600, color: 'var(--ink-900)', marginBottom: 10 }}>
          Change rating?
        </div>
        <p style={{ fontSize: 13, color: 'var(--ink-500)', lineHeight: 1.5, marginBottom: 20 }}>
          {message}
        </p>
        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
          <button
            onClick={onCancel}
            className="bg-paper border border-ink-200 text-ink-900 font-ui text-sm font-medium rounded-md px-4 py-2 hover:bg-ink-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent"
          >Cancel</button>
          <button
            onClick={onConfirm}
            className="bg-brand text-white font-ui text-sm font-medium rounded-md px-4 py-2 hover:bg-brand-hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-1"
          >{confirmLabel}</button>
        </div>
      </div>
    </div>
  );
}


const ChatMessage = ({ message, onResend, onRerun, authorInitials = 'U', matters = [], mattersEnabled = true, sourcesCount = 0, onViewSources, sourcesActive = false }) => {
  const isUser = message.role === 'user';
  const isTool = message.role === 'tool';

  const [copied, setCopied] = useState(false);
  const [copiedUser, setCopiedUser] = useState(false);
  const [rating, setRating] = useState(message.rating || 0);
  const [isRating, setIsRating] = useState(false);
  const [comment, setComment] = useState(message.feedback_comment || '');
  const [showThumbsDownForm, setShowThumbsDownForm] = useState(false);
  const [thumbsDownText, setThumbsDownText] = useState('');
  const [thumbsSubmitting, setThumbsSubmitting] = useState(false);
  const [showUpgradeConfirm, setShowUpgradeConfirm] = useState(false);
  const [showPinPopover, setShowPinPopover] = useState(false);
  const [pinned, setPinned] = useState(false);
  const [pinError, setPinError] = useState(false);
  const pinRef = useRef(null);

  useEffect(() => {
    setRating(message.rating || 0);
    setComment(message.feedback_comment || '');
    setShowThumbsDownForm(false);
    setThumbsDownText('');
    setShowUpgradeConfirm(false);
  }, [message.id]);

  useEffect(() => {
    if (!showPinPopover) return;
    const handler = (e) => {
      if (pinRef.current && !pinRef.current.contains(e.target)) setShowPinPopover(false);
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [showPinPopover]);

  const handlePin = async (matterId) => {
    try {
      await addMatterNote(matterId, message.content, message.id || null);
      setPinned(true);
      setTimeout(() => setPinned(false), 2000);
    } catch {
      setPinError(true);
      setTimeout(() => setPinError(false), 2500);
    }
    setShowPinPopover(false);
  };

  const handleRate = async (value, feedbackComment) => {
    if (!message.id) return;
    setIsRating(true);
    try {
      await rateMessage(message.id, value, feedbackComment !== undefined ? feedbackComment : comment);
      setRating(value);
      if (feedbackComment !== undefined) setComment(feedbackComment);
    } catch (err) {
      console.error('Failed to rate message', err);
    } finally {
      setIsRating(false);
    }
  };

  const handleThumbsUpClick = () => {
    if (rating === 5 || isRating) return;
    if (rating === 1 && comment) {
      setShowUpgradeConfirm(true);
    } else {
      handleRate(5);
    }
  };

  const handleThumbsDownSubmit = async () => {
    if (!message.id) return;
    setThumbsSubmitting(true);
    try {
      await rateMessage(message.id, 1, thumbsDownText.trim() || null);
      setRating(1);
      setComment(thumbsDownText.trim() || '');
      setShowThumbsDownForm(false);
    } catch (err) {
      console.error('Failed to submit thumbs down', err);
    } finally {
      setThumbsSubmitting(false);
    }
  };

  const processedContent = useMemo(() => {
    let content = message.content;
    if (!content) return '';
    content = content.replace(/<(think|thinking)>([\s\S]*?)<\/\1>/gi, '');
    content = content.replace(/<(think|thinking)>([\s\S]*)$/i, '');
    return content.trim();
  }, [message.content]);

  const handleCopy = async () => {
    try {
      const html = await marked(processedContent);
      await navigator.clipboard.write([
        new ClipboardItem({ 'text/html': new Blob([html], { type: 'text/html' }), 'text/plain': new Blob([processedContent], { type: 'text/plain' }) }),
      ]);
    } catch {
      navigator.clipboard.writeText(processedContent);
    }
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  if (isTool) return null;

  const timeStr = formatTime(message.created_at || message.at);

  // ── User message ──────────────────────────────────────────────
  const handleCopyUser = () => {
    navigator.clipboard.writeText(message.content);
    setCopiedUser(true);
    setTimeout(() => setCopiedUser(false), 2000);
  };

  if (isUser) {
    return (
      <div style={{
        display: 'flex', gap: 12, alignItems: 'flex-start',
        padding: '8px 0 4px', fontFamily: 'var(--font-ui)',
      }}>
        <div style={{
          width: 28, height: 28, borderRadius: '50%',
          background: 'var(--ink-100)', color: 'var(--ink-700)',
          display: 'grid', placeItems: 'center',
          fontSize: 11, fontWeight: 600, flex: '0 0 28px',
        }}>{authorInitials}</div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
            <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--ink-900)' }}>You</span>
            {timeStr && <span style={{ fontSize: 12, color: 'var(--ink-400)' }}>{timeStr}</span>}
          </div>
          <div style={{ fontSize: 15, color: 'var(--ink-800)', lineHeight: 1.5 }}>{message.content}</div>
          <div style={{ display: 'flex', gap: 2, marginTop: 6 }}>
            <ToolBtn label={copiedUser ? 'Copied!' : 'Copy query'} onClick={handleCopyUser} active={copiedUser}>
              <CopyIcon />
            </ToolBtn>
            {onRerun && (
              <ToolBtn label="Re-run query" onClick={onRerun}>
                <RefreshIcon />
              </ToolBtn>
            )}
          </div>
        </div>
      </div>
    );
  }

  // ── Assistant message ─────────────────────────────────────────
  const timingMs = message.responseTimeMs;
  const timingLabel = timingMs != null
    ? (timingMs >= 60000
      ? `${Math.floor(timingMs / 60000)}m ${Math.round((timingMs % 60000) / 1000)}s`
      : `${(timingMs / 1000).toFixed(1)}s`)
    : null;
  const cost = formatCost(message.costUsd ?? message.cost_usd);

  return (
    <>
      <div style={{
        background: 'var(--paper)',
        border: '1px solid var(--ink-200)',
        borderRadius: 12, padding: 24,
        boxShadow: 'var(--shadow-sm)',
        fontFamily: 'var(--font-ui)',
      }}>
        <div style={{
          fontFamily: 'var(--font-serif)',
          fontSize: 15.5, lineHeight: 1.7,
          color: 'var(--ink-800)',
        }}>
          <ReactMarkdown
            remarkPlugins={[remarkGfm]}
            components={{
              a: ({ node, ...p }) => <a {...p} target="_blank" rel="noopener noreferrer" style={{ color: 'var(--accent)' }} />,
              p: ({ node, ...p }) => <p {...p} style={{ margin: '0 0 14px' }} />,
              ul: ({ node, ...p }) => <ul {...p} style={{ margin: '0 0 14px', paddingLeft: 24 }} />,
              ol: ({ node, ...p }) => <ol {...p} style={{ margin: '0 0 14px', paddingLeft: 24 }} />,
              li: ({ node, ...p }) => <li {...p} style={{ marginBottom: 4 }} />,
              blockquote: ({ node, ...p }) => (
                <blockquote {...p} style={{
                  borderLeft: '3px solid var(--ink-200)', paddingLeft: 12,
                  marginLeft: 0, color: 'var(--ink-600)', fontStyle: 'italic',
                }} />
              ),
              code: ({ node, inline, ...p }) => inline
                ? <code {...p} style={{ fontFamily: 'var(--font-mono)', fontSize: 13, background: 'var(--ink-100)', padding: '1px 4px', borderRadius: 4, color: 'var(--ink-800)' }} />
                : <code {...p} style={{ fontFamily: 'var(--font-mono)', fontSize: 13 }} />,
              pre: ({ node, ...p }) => (
                <pre {...p} style={{
                  background: 'var(--ink-50)', border: '1px solid var(--ink-200)',
                  borderRadius: 8, padding: '12px 16px', overflowX: 'auto',
                  margin: '0 0 14px', fontFamily: 'var(--font-mono)', fontSize: 13,
                }} />
              ),
              h1: ({ node, ...p }) => <h1 {...p} style={{ fontSize: 18, fontWeight: 700, color: 'var(--ink-900)', margin: '0 0 12px', lineHeight: 1.3, fontFamily: 'var(--font-ui)' }} />,
              h2: ({ node, ...p }) => <h2 {...p} style={{ fontSize: 16, fontWeight: 600, color: 'var(--ink-900)', margin: '18px 0 8px', lineHeight: 1.3, fontFamily: 'var(--font-ui)' }} />,
              h3: ({ node, ...p }) => <h3 {...p} style={{ fontSize: 14, fontWeight: 600, color: 'var(--ink-900)', margin: '14px 0 6px', lineHeight: 1.3, fontFamily: 'var(--font-ui)' }} />,
            }}
          >
            {processedContent}
          </ReactMarkdown>
        </div>

        <div style={{
          borderTop: '1px solid var(--ink-100)', marginTop: 16, paddingTop: 10,
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 2 }}>
            <ToolBtn label={copied ? 'Copied!' : 'Copy answer'} onClick={handleCopy} active={copied}>
              <CopyIcon />
            </ToolBtn>
            <ToolBtn label="Regenerate" onClick={onResend}>
              <RefreshIcon />
            </ToolBtn>
            {sourcesCount > 0 && (
              <button
                onClick={onViewSources}
                title="View sources for this response"
                style={{
                  display: 'inline-flex', alignItems: 'center', gap: 4,
                  padding: '3px 8px', borderRadius: 6, border: '1px solid',
                  fontSize: 12, fontWeight: 500, cursor: 'pointer',
                  fontFamily: 'var(--font-ui)',
                  background: sourcesActive ? 'var(--accent-muted, #e8f0fe)' : 'transparent',
                  borderColor: sourcesActive ? 'var(--accent, #4a6cf7)' : 'var(--ink-200)',
                  color: sourcesActive ? 'var(--accent, #4a6cf7)' : 'var(--ink-500)',
                  transition: 'all 0.15s',
                }}
                onMouseEnter={e => { if (!sourcesActive) { e.currentTarget.style.borderColor = 'var(--ink-400)'; e.currentTarget.style.color = 'var(--ink-700)'; } }}
                onMouseLeave={e => { if (!sourcesActive) { e.currentTarget.style.borderColor = 'var(--ink-200)'; e.currentTarget.style.color = 'var(--ink-500)'; } }}
              >
                <svg width={12} height={12} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round">
                  <path d="M4 4.5A2.5 2.5 0 0 1 6.5 2H20v16H6.5A2.5 2.5 0 0 0 4 20.5z" />
                  <path d="M20 18v4H6.5A2.5 2.5 0 0 1 4 19.5" />
                </svg>
                Sources ({sourcesCount})
              </button>
            )}
            <ToolBtn
              label={rating === 5 ? 'Rated helpful' : 'Mark as helpful'}
              active={rating === 5}
              disabled={isRating || rating === 5}
              onClick={handleThumbsUpClick}
            >
              <svg width={15} height={15} viewBox="0 0 24 24"
                fill={rating === 5 ? 'currentColor' : 'none'}
                stroke="currentColor" strokeWidth={1.6} strokeLinecap="round" strokeLinejoin="round">
                <path d="M7 10V21H3V10zM21 10a2 2 0 0 0-2-2h-5.5l.8-3.7A2 2 0 0 0 12.4 2L7 8v13h11a2 2 0 0 0 2-1.7l1-7A2 2 0 0 0 21 10z" />
              </svg>
            </ToolBtn>
            <ToolBtn
              label={rating === 1 ? 'Marked unhelpful' : 'Mark as unhelpful'}
              active={rating === 1}
              disabled={isRating || rating === 1}
              onClick={() => { if (rating !== 1) setShowThumbsDownForm(v => !v); }}
            >
              <svg width={15} height={15} viewBox="0 0 24 24"
                fill={rating === 1 ? 'currentColor' : 'none'}
                stroke="currentColor" strokeWidth={1.6} strokeLinecap="round" strokeLinejoin="round">
                <path d="M17 14V3H21V14zM3 14a2 2 0 0 0 2 2h5.5l-.8 3.7A2 2 0 0 0 11.6 22L17 16V3H6a2 2 0 0 0-2 1.7l-1 7A2 2 0 0 0 3 14z" />
              </svg>
            </ToolBtn>
            {mattersEnabled && <div ref={pinRef} style={{ position: 'relative' }}>
              <ToolBtn
                label={pinError ? 'Failed to save' : pinned ? 'Pinned!' : matters.length === 0 ? 'Create a matter first' : 'Save to matter'}
                active={pinned}
                onClick={() => matters.length > 0 && setShowPinPopover(v => !v)}
                disabled={matters.length === 0}
                error={pinError}
              >
                <BookmarkIcon />
              </ToolBtn>
              {showPinPopover && (
                <div style={{
                  position: 'absolute', bottom: '100%', left: 0, marginBottom: 4,
                  background: 'var(--paper)', border: '1px solid var(--ink-200)',
                  borderRadius: 'var(--r-md)', boxShadow: 'var(--shadow-md)',
                  minWidth: 200, zIndex: 40, padding: '4px 0',
                  fontFamily: 'var(--font-ui)',
                }}>
                  <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--ink-400)', padding: '4px 10px 6px', textTransform: 'uppercase', letterSpacing: '0.06em' }}>Pin to matter</div>
                  {matters.map(m => (
                    <div
                      key={m.id}
                      onClick={() => handlePin(m.id)}
                      style={{
                        padding: '7px 10px', cursor: 'pointer', fontSize: 13,
                        color: 'var(--ink-800)', display: 'flex', alignItems: 'center', gap: 6,
                      }}
                      onMouseEnter={e => e.currentTarget.style.background = 'var(--ink-50)'}
                      onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
                    >
                      <svg width={13} height={13} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.6} strokeLinecap="round" strokeLinejoin="round">
                        <path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V7z" />
                      </svg>
                      {m.title}
                    </div>
                  ))}
                </div>
              )}
            </div>}
          </div>
          <div style={{
            display: 'flex', gap: 10, fontSize: 11,
            color: 'var(--ink-400)', fontFamily: 'var(--font-mono)',
          }}>
            {timingLabel && <span>{timingLabel}</span>}
            {cost && <span title="Estimated OpenRouter cost">{cost}</span>}
          </div>
        </div>
      </div>

      {showThumbsDownForm && rating !== 1 && ReactDOM.createPortal(
        <ThumbsDownModal
          text={thumbsDownText}
          onChange={setThumbsDownText}
          onCancel={() => { setShowThumbsDownForm(false); setThumbsDownText(''); }}
          onSubmit={handleThumbsDownSubmit}
          submitting={thumbsSubmitting}
        />,
        document.body
      )}
      {showUpgradeConfirm && ReactDOM.createPortal(
        <ConfirmModal
          message="You left a comment when marking this response as unhelpful. Marking it as helpful will delete that comment."
          confirmLabel="Mark helpful & delete comment"
          onConfirm={() => { setShowUpgradeConfirm(false); handleRate(5, null); }}
          onCancel={() => setShowUpgradeConfirm(false)}
        />,
        document.body
      )}
    </>
  );
};

export default ChatMessage;
