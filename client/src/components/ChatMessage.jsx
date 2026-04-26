import React, { useState, useMemo } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { marked } from 'marked';
import { rateMessage } from '../services/api';
import CommentModal from './CommentModal';

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

function ToolBtn({ label, onClick, active, children }) {
  const [h, setH] = React.useState(false);
  return (
    <button
      aria-label={label}
      title={label}
      onClick={onClick}
      onMouseEnter={() => setH(true)}
      onMouseLeave={() => setH(false)}
      style={{
        width: 30, height: 30, borderRadius: 8, border: 'none',
        background: active ? 'var(--accent-soft)' : (h ? 'var(--ink-100)' : 'transparent'),
        color: active ? 'var(--accent)' : 'var(--ink-500)',
        display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
        cursor: 'pointer', transition: 'background 120ms',
      }}
    >{children}</button>
  );
}

const CopyIcon = () => (
  <svg width={15} height={15} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.6} strokeLinecap="round" strokeLinejoin="round">
    <rect x="9" y="9" width="11" height="11" rx="2" />
    <path d="M6 15H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h8a2 2 0 0 1 2 2v1" />
  </svg>
);

const RefreshIcon = () => (
  <svg width={15} height={15} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.6} strokeLinecap="round" strokeLinejoin="round">
    <path d="M4 12a8 8 0 0 1 14-5.3L21 9" />
    <path d="M21 4v5h-5" />
    <path d="M20 12a8 8 0 0 1-14 5.3L3 15" />
    <path d="M3 20v-5h5" />
  </svg>
);

const ThumbUpIcon = () => (
  <svg width={15} height={15} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.6} strokeLinecap="round" strokeLinejoin="round">
    <path d="M7 10v10H4V10h3zm0 0 4-7a2 2 0 0 1 2 2v3h5a2 2 0 0 1 2 2.3l-1.2 7A2 2 0 0 1 16.8 19H7" />
  </svg>
);

const ThumbDownIcon = () => (
  <svg width={15} height={15} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.6} strokeLinecap="round" strokeLinejoin="round">
    <path d="M7 14V4H4v10h3zm0 0 4 7a2 2 0 0 0 2-2v-3h5a2 2 0 0 0 2-2.3L18.8 6.7A2 2 0 0 0 16.8 5H7" />
  </svg>
);

const BookmarkIcon = () => (
  <svg width={15} height={15} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.6} strokeLinecap="round" strokeLinejoin="round">
    <path d="M6 3h12v18l-6-4-6 4z" />
  </svg>
);

const ShareIcon = () => (
  <svg width={15} height={15} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.6} strokeLinecap="round" strokeLinejoin="round">
    <circle cx="18" cy="5" r="2.5" />
    <circle cx="6" cy="12" r="2.5" />
    <circle cx="18" cy="19" r="2.5" />
    <path d="M8.2 10.8 15.8 6.2M8.2 13.2l7.6 4.6" />
  </svg>
);

const ChatMessage = ({ message, onResend, showThinking, authorInitials = 'U' }) => {
  const isUser = message.role === 'user';
  const isTool = message.role === 'tool';

  const [copied, setCopied] = useState(false);
  const [rating, setRating] = useState(message.rating || 0);
  const [isRating, setIsRating] = useState(false);
  const [comment, setComment] = useState(message.feedback_comment || '');
  const [showCommentModal, setShowCommentModal] = useState(false);

  const handleRate = async (value) => {
    if (!message.id) return;
    setIsRating(true);
    try {
      await rateMessage(message.id, value, comment);
      setRating(value);
    } catch (err) {
      console.error('Failed to rate message', err);
    } finally {
      setIsRating(false);
    }
  };

  const handleCommentSubmit = async (newComment) => {
    if (!message.id) return;
    setIsRating(true);
    try {
      await rateMessage(message.id, rating, newComment);
      setComment(newComment);
      setShowCommentModal(false);
    } catch (err) {
      console.error('Failed to save comment', err);
    } finally {
      setIsRating(false);
    }
  };

  const processedContent = useMemo(() => {
    let content = message.content;
    if (!content) return '';
    const thinkBlock = /<(think|thinking)>([\s\S]*?)<\/\1>/gi;
    const unclosed = /<(think|thinking)>([\s\S]*)$/i;
    if (showThinking) {
      content = content.replace(thinkBlock, (_, _t, inner) => `\n*${inner.trim()}*\n`);
      content = content.replace(unclosed, (_, _t, inner) => `\n*${inner.trim()}*`);
      return content;
    }
    content = content.replace(thinkBlock, '');
    content = content.replace(unclosed, '');
    return content.trim();
  }, [message.content, showThinking]);

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
            <ToolBtn
              label="Good answer"
              onClick={() => handleRate(5)}
              active={rating === 5}
            >
              <ThumbUpIcon />
            </ToolBtn>
            <ToolBtn
              label="Report an issue"
              onClick={() => { handleRate(1); setShowCommentModal(true); }}
              active={rating === 1}
            >
              <ThumbDownIcon />
            </ToolBtn>
            <ToolBtn label="Save to matter">
              <BookmarkIcon />
            </ToolBtn>
            <ToolBtn label="Share">
              <ShareIcon />
            </ToolBtn>
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

      <CommentModal
        isOpen={showCommentModal}
        onClose={() => setShowCommentModal(false)}
        onSubmit={handleCommentSubmit}
        initialComment={comment}
        rating={rating}
        onRate={handleRate}
      />
    </>
  );
};

export default ChatMessage;
