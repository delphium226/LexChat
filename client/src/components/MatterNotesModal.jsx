import React, { useEffect, useState } from 'react';
import { addMatterNote, deleteMatterNote, getMatterNotes } from '../services/api';

function formatDate(iso) {
  if (!iso) return '';
  return new Date(iso).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' });
}

const MatterNotesModal = ({ matter, onClose }) => {
  const [notes, setNotes] = useState([]);
  const [newNote, setNewNote] = useState('');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    getMatterNotes(matter.id)
      .then(setNotes)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [matter.id]);

  const handleAdd = async () => {
    if (!newNote.trim()) return;
    setSaving(true);
    try {
      const note = await addMatterNote(matter.id, newNote.trim());
      setNotes(prev => [...prev, note]);
      setNewNote('');
    } catch {
      // silently fail
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (noteId) => {
    try {
      await deleteMatterNote(matter.id, noteId);
      setNotes(prev => prev.filter(n => n.id !== noteId));
    } catch {
      // silently fail
    }
  };

  return (
    <div
      style={{
        position: 'fixed', inset: 0, background: 'rgba(11,18,32,0.45)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        zIndex: 50, padding: 16,
      }}
      onMouseDown={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div style={{
        background: 'var(--paper)', borderRadius: 'var(--r-lg)',
        width: '100%', maxWidth: 520, maxHeight: '80vh',
        display: 'flex', flexDirection: 'column',
        boxShadow: '0 8px 32px rgba(11,18,32,0.14)',
        fontFamily: 'var(--font-ui)',
      }}>
        {/* Header */}
        <div style={{
          padding: '18px 20px 14px',
          borderBottom: '1px solid var(--ink-200)',
          display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between',
          flexShrink: 0,
        }}>
          <div>
            <div style={{ fontSize: 15, fontWeight: 600, color: 'var(--ink-900)' }}>Notes</div>
            <div style={{ fontSize: 12, color: 'var(--ink-500)', marginTop: 2 }}>{matter.title}</div>
          </div>
          <button
            onClick={onClose}
            style={{
              width: 28, height: 28, borderRadius: 6, border: 'none',
              background: 'transparent', cursor: 'pointer', color: 'var(--ink-500)',
              display: 'grid', placeItems: 'center', flexShrink: 0,
            }}
            aria-label="Close"
          >
            <svg width={16} height={16} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} strokeLinecap="round">
              <path d="M18 6 6 18M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Notes list */}
        <div className="lex-scroll" style={{ flex: 1, overflowY: 'auto', padding: '12px 20px' }}>
          {loading && (
            <div style={{ color: 'var(--ink-400)', fontSize: 13, padding: '8px 0' }}>Loading…</div>
          )}
          {!loading && notes.length === 0 && (
            <div style={{ color: 'var(--ink-400)', fontSize: 13, fontStyle: 'italic', padding: '8px 0' }}>
              No notes yet. Pin a message from a research thread or add one below.
            </div>
          )}
          {notes.map(note => (
            <div key={note.id} style={{
              padding: '10px 12px', borderRadius: 'var(--r-sm)',
              border: '1px solid var(--ink-200)', marginBottom: 8,
              background: 'var(--ink-25)',
            }}>
              <div style={{ fontSize: 14, color: 'var(--ink-800)', lineHeight: 1.5, whiteSpace: 'pre-wrap' }}>
                {note.content}
              </div>
              <div style={{
                display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                marginTop: 8,
              }}>
                <div style={{ fontSize: 11, color: 'var(--ink-400)' }}>
                  {note.message_id && <span style={{ marginRight: 8, color: 'var(--cite)' }}>Pinned from thread</span>}
                  {formatDate(note.created_at)}
                </div>
                <button
                  onClick={() => handleDelete(note.id)}
                  style={{
                    fontSize: 12, color: 'var(--danger)', background: 'none',
                    border: 'none', cursor: 'pointer', padding: '2px 6px',
                    borderRadius: 4, fontFamily: 'var(--font-ui)',
                  }}
                >Delete</button>
              </div>
            </div>
          ))}
        </div>

        {/* Add note */}
        <div style={{
          padding: '12px 20px 16px',
          borderTop: '1px solid var(--ink-200)',
          flexShrink: 0,
        }}>
          <textarea
            value={newNote}
            onChange={e => setNewNote(e.target.value)}
            onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleAdd(); } }}
            placeholder="Add a note… (Enter to save)"
            rows={2}
            style={{
              width: '100%', boxSizing: 'border-box',
              padding: '8px 12px', borderRadius: 'var(--r-sm)',
              border: '1px solid var(--ink-300)', fontSize: 13,
              color: 'var(--ink-900)', fontFamily: 'var(--font-ui)',
              resize: 'none', outline: 'none', marginBottom: 8,
            }}
          />
          <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
            <button
              onClick={handleAdd}
              disabled={saving || !newNote.trim()}
              style={{
                padding: '6px 16px', borderRadius: 'var(--r-sm)',
                border: 'none', background: 'var(--accent)',
                fontSize: 13, fontWeight: 500, color: 'white',
                cursor: saving || !newNote.trim() ? 'not-allowed' : 'pointer',
                opacity: saving || !newNote.trim() ? 0.6 : 1,
                fontFamily: 'var(--font-ui)',
              }}
            >{saving ? 'Saving…' : 'Add note'}</button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default MatterNotesModal;
