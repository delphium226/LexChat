import { IBtn } from './ui/buttons';
import { PaperclipIcon, SendIcon, StopIcon } from './ui/icons';

// The message composer card: attached-document chips, the textarea, and the
// action row (attach / filters toggle / send-or-stop). Presentational — all
// chat state and handlers live in useChat / App and are passed in.
export default function Composer({
  fileInputRef,
  textareaRef,
  onFileUpload,
  chatDocuments,
  onDeleteDocument,
  uploadingDoc,
  uploadError,
  onDismissUploadError,
  input,
  setInput,
  loading,
  onSend,
  onStop,
  chatMode,
}) {
  return (
    <div
      style={{
        background: 'var(--paper)',
        border: '1px solid var(--ink-200)',
        borderRadius: 12,
        padding: 12,
        boxShadow: 'var(--shadow-sm)',
      }}
    >
      {/* Hidden file input */}
      <input
        ref={fileInputRef}
        type="file"
        accept=".pdf,.docx,.txt,.md"
        style={{ display: 'none' }}
        onChange={onFileUpload}
      />

      {/* Document chips */}
      {chatDocuments.length > 0 && (
        <div
          style={{
            display: 'flex',
            flexWrap: 'wrap',
            gap: 4,
            paddingBottom: 8,
            marginBottom: 6,
            borderBottom: '1px solid var(--ink-100)',
          }}
        >
          {chatDocuments.map(doc => (
            <div
              key={doc.id}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: 4,
                padding: '2px 8px',
                background: 'var(--ink-100)',
                borderRadius: 6,
                fontSize: 12,
                color: 'var(--ink-600)',
                maxWidth: 220,
              }}
            >
              <PaperclipIcon style={{ width: 11, height: 11, flexShrink: 0 }} />
              <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={doc.filename}>
                {doc.filename}
              </span>
              <button
                onClick={() => onDeleteDocument(doc.id)}
                style={{
                  background: 'none',
                  border: 'none',
                  padding: '0 0 0 2px',
                  cursor: 'pointer',
                  color: 'var(--ink-400)',
                  fontSize: 14,
                  lineHeight: 1,
                  flexShrink: 0,
                }}
                title="Remove document"
              >
                ×
              </button>
            </div>
          ))}
          {uploadingDoc && (
            <div
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: 4,
                padding: '2px 8px',
                background: 'var(--ink-100)',
                borderRadius: 6,
                fontSize: 12,
                color: 'var(--ink-400)',
              }}
            >
              Uploading…
            </div>
          )}
        </div>
      )}
      {uploadingDoc && chatDocuments.length === 0 && (
        <div
          style={{
            fontSize: 12,
            color: 'var(--ink-400)',
            paddingBottom: 6,
            borderBottom: '1px solid var(--ink-100)',
            marginBottom: 6,
          }}
        >
          Uploading…
        </div>
      )}
      {uploadError && (
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 6,
            fontSize: 12,
            color: 'var(--danger)',
            paddingBottom: 6,
            borderBottom: '1px solid var(--ink-100)',
            marginBottom: 6,
          }}
        >
          <span>{uploadError}</span>
          <button
            onClick={onDismissUploadError}
            style={{
              background: 'none',
              border: 'none',
              padding: 0,
              cursor: 'pointer',
              color: 'var(--ink-400)',
              fontSize: 14,
              lineHeight: 1,
            }}
            title="Dismiss"
          >
            ×
          </button>
        </div>
      )}

      <textarea
        ref={textareaRef}
        value={input}
        onChange={e => setInput(e.target.value)}
        onKeyDown={e => {
          if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            if (!loading && input.trim()) onSend();
          }
        }}
        disabled={loading}
        rows={1}
        placeholder={
          chatMode === 'conversational'
            ? 'Ask a legal question…'
            : chatMode === 'deep_research'
              ? 'Describe your research question — a plan will be drafted for review…'
              : 'Ask about UK legislation or case law…'
        }
        style={{
          width: '100%',
          resize: 'none',
          border: 'none',
          outline: 'none',
          fontSize: 14,
          lineHeight: 1.5,
          color: 'var(--ink-800)',
          background: 'transparent',
          minHeight: 44,
          maxHeight: 180,
          overflow: 'auto',
          fontFamily: 'var(--font-ui)',
          padding: '8px 0 4px',
        }}
      />
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          marginTop: 6,
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 2, color: 'var(--ink-500)' }}>
          <IBtn label="Attach file (PDF, DOCX, TXT)" onClick={() => fileInputRef.current?.click()} disabled={uploadingDoc}>
            <PaperclipIcon />
          </IBtn>
        </div>

        {loading ? (
          <button
            onClick={onStop}
            className="inline-flex items-center gap-1.5 px-3 py-2 bg-danger text-white font-ui text-sm font-semibold rounded-md hover:opacity-90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-danger"
          >
            <StopIcon /> Stop
          </button>
        ) : (
          <button
            onClick={() => {
              if (input.trim()) onSend();
            }}
            disabled={!input.trim()}
            className="inline-flex items-center gap-1.5 px-3 py-2 font-ui text-sm font-semibold rounded-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-1 disabled:cursor-not-allowed transition-colors disabled:bg-ink-200 disabled:text-ink-400 bg-brand text-white hover:bg-brand-hover"
          >
            <SendIcon /> Send
          </button>
        )}
      </div>
    </div>
  );
}
