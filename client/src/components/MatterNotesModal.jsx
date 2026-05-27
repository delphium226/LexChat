import React, { useEffect, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { marked } from 'marked';
import { useEditor, EditorContent } from '@tiptap/react';
import StarterKit from '@tiptap/starter-kit';
import Link from '@tiptap/extension-link';
import Typography from '@tiptap/extension-typography';
import { Markdown } from 'tiptap-markdown';
import DOMPurify from 'dompurify';
import { addMatterNote, deleteMatterNote, generateMatterBrief, getMatterNotes } from '../services/api';

function formatDate(iso) {
  if (!iso) return '';
  return new Date(iso).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' });
}

const TAB_NOTES = 'notes';
const TAB_BRIEF = 'brief';

// Compact markdown renderer for saved notes
const noteComponents = {
  p: ({ node, ...p }) => <p {...p} style={{ margin: '0 0 4px' }} />,
  ul: ({ node, ...p }) => <ul {...p} style={{ listStyleType: 'disc', paddingLeft: 20, margin: '4px 0' }} />,
  ol: ({ node, ...p }) => <ol {...p} style={{ listStyleType: 'decimal', paddingLeft: 20, margin: '4px 0' }} />,
  li: ({ node, ...p }) => <li {...p} style={{ marginBottom: 2 }} />,
  h1: ({ node, ...p }) => <h1 {...p} style={{ fontSize: 16, fontWeight: 700, margin: '4px 0' }} />,
  h2: ({ node, ...p }) => <h2 {...p} style={{ fontSize: 14, fontWeight: 600, margin: '4px 0' }} />,
  h3: ({ node, ...p }) => <h3 {...p} style={{ fontSize: 13, fontWeight: 600, margin: '4px 0' }} />,
  blockquote: ({ node, ...p }) => (
    <blockquote {...p} style={{ borderLeft: '3px solid var(--ink-300)', margin: '4px 0', paddingLeft: 12, color: 'var(--ink-600)', fontStyle: 'italic' }} />
  ),
  a: ({ node, ...p }) => <a {...p} target="_blank" rel="noopener noreferrer" style={{ color: 'var(--accent)', textDecoration: 'underline' }} />,
  hr: ({ node, ...p }) => <hr {...p} style={{ border: 'none', borderTop: '1px solid var(--ink-300)', margin: '6px 0' }} />,
};

const Sep = () => (
  <div style={{ width: 1, background: 'var(--ink-200)', margin: '3px 3px' }} />
);

function ToolbarBtn({ label, title, active, onClick }) {
  return (
    <button
      type="button"
      title={title}
      onMouseDown={e => { e.preventDefault(); onClick(); }}
      style={{
        display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
        padding: '2px 6px', borderRadius: 4, border: 'none', minWidth: 24, height: 24,
        background: active ? 'var(--ink-200)' : 'transparent',
        color: active ? 'var(--ink-900)' : 'var(--ink-500)',
        cursor: 'pointer', fontSize: 12,
        fontFamily: 'var(--font-ui)', lineHeight: 1,
        transition: 'background 0.1s, color 0.1s',
      }}
    >{label}</button>
  );
}

const IconBlockquote = () => (
  <svg width="13" height="13" viewBox="0 0 24 24" fill="currentColor">
    <path d="M3 21c3 0 7-1 7-8V5c0-1.25-.756-2.017-2-2H4c-1.25 0-2 .75-2 1.972V11c0 1.25.75 2 2 2 1 0 1 0 1 1v1c0 1-1 2-2 2s-1 .008-1 1.031V20c0 1 0 1 1 1z"/>
    <path d="M15 21c3 0 7-1 7-8V5c0-1.25-.757-2.017-2-2h-4c-1.25 0-2 .75-2 1.972V11c0 1.25.75 2 2 2h.75c0 2.25.25 4-2.75 4v3c0 1 0 1 1 1z"/>
  </svg>
);
const IconLink = () => (
  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/>
    <path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/>
  </svg>
);

const MatterNotesModal = ({ matter, onClose }) => {
  const [tab, setTab] = useState(TAB_NOTES);
  const [notes, setNotes] = useState([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [editorEmpty, setEditorEmpty] = useState(true);

  const [briefMode, setBriefMode] = useState('brief');
  const [briefContent, setBriefContent] = useState('');
  const [briefLoading, setBriefLoading] = useState(false);
  const [briefError, setBriefError] = useState('');
  const [copied, setCopied] = useState(false);
  const [savingBrief, setSavingBrief] = useState(false);
  const [briefSaved, setBriefSaved] = useState(false);

  const editor = useEditor({
    extensions: [
      StarterKit,
      Link.configure({ openOnClick: false }),
      Typography,
      Markdown.configure({ html: false, tightLists: true }),
    ],
    content: '',
    editorProps: {
      attributes: { class: 'note-editor-inner' },
    },
    onUpdate: ({ editor }) => setEditorEmpty(editor.isEmpty),
  });

  useEffect(() => {
    getMatterNotes(matter.id)
      .then(setNotes)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [matter.id]);

  const handleAdd = async () => {
    if (!editor) return;
    const md = editor.storage.markdown.getMarkdown();
    if (!md || !md.trim()) return;
    setSaving(true);
    try {
      const note = await addMatterNote(matter.id, md);
      setNotes(prev => [...prev, note]);
      editor.commands.clearContent();
      setEditorEmpty(true);
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

  const handleSetLink = () => {
    if (!editor) return;
    const prev = editor.getAttributes('link').href ?? '';
    const url = window.prompt('Link URL (leave blank to remove):', prev);
    if (url === null) return;
    if (url === '') {
      editor.chain().focus().extendMarkRange('link').unsetLink().run();
    } else {
      editor.chain().focus().extendMarkRange('link').setLink({ href: url }).run();
    }
  };

  const handleSaveBriefAsNote = async () => {
    if (!briefContent) return;
    setSavingBrief(true);
    try {
      const note = await addMatterNote(matter.id, briefContent);
      setNotes(prev => [...prev, note]);
      setBriefSaved(true);
      setTimeout(() => setBriefSaved(false), 2000);
      setTab(TAB_NOTES);
    } catch {
      // silently fail
    } finally {
      setSavingBrief(false);
    }
  };

  const handleGenerateBrief = async () => {
    setBriefLoading(true);
    setBriefError('');
    setBriefContent('');
    setBriefSaved(false);
    try {
      const data = await generateMatterBrief(matter.id, briefMode);
      setBriefContent(data.content || '');
    } catch {
      setBriefError('Failed to generate. Please try again.');
    } finally {
      setBriefLoading(false);
    }
  };

  const handleCopy = async () => {
    try {
      const html = await marked(briefContent);
      await navigator.clipboard.write([
        new ClipboardItem({
          'text/html': new Blob([html], { type: 'text/html' }),
          'text/plain': new Blob([briefContent], { type: 'text/plain' }),
        }),
      ]);
    } catch {
      navigator.clipboard.writeText(briefContent);
    }
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const tabStyle = (active) => ({
    padding: '6px 14px', fontSize: 13, fontWeight: 500,
    color: active ? 'var(--accent)' : 'var(--ink-500)',
    background: 'transparent', border: 'none', cursor: 'pointer',
    borderBottom: active ? '2px solid var(--accent)' : '2px solid transparent',
    fontFamily: 'var(--font-ui)',
  });

  const e = editor;

  return (
    <>
      <style>{`
        .note-editor-inner { outline: none; }
        .note-editor-inner p { margin: 0 0 4px; }
        .note-editor-inner p:last-child { margin-bottom: 0; }
        .note-editor-inner ul { list-style-type: disc; padding-left: 20px; margin: 4px 0; }
        .note-editor-inner ol { list-style-type: decimal; padding-left: 20px; margin: 4px 0; }
        .note-editor-inner li { margin-bottom: 2px; }
        .note-editor-inner h1 { font-size: 18px; font-weight: 700; margin: 4px 0; }
        .note-editor-inner h2 { font-size: 15px; font-weight: 600; margin: 4px 0; }
        .note-editor-inner h3 { font-size: 13px; font-weight: 600; margin: 4px 0; }
        .note-editor-inner blockquote { border-left: 3px solid var(--ink-300); margin: 4px 0; padding-left: 12px; color: var(--ink-600); font-style: italic; }
        .note-editor-inner a { color: var(--accent); text-decoration: underline; }
        .note-editor-inner hr { border: none; border-top: 1px solid var(--ink-300); margin: 8px 0; }
        .note-rich-content p { margin: 0 0 4px; }
        .note-rich-content p:last-child { margin-bottom: 0; }
        .note-rich-content ul { list-style-type: disc; padding-left: 20px; margin: 4px 0; }
        .note-rich-content ol { list-style-type: decimal; padding-left: 20px; margin: 4px 0; }
        .note-rich-content li { margin-bottom: 2px; }
        .note-rich-content strong { font-weight: 600; }
        .note-rich-content em { font-style: italic; }
        .note-rich-content a { color: var(--accent); text-decoration: underline; }
      `}</style>
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
          width: '80vw', height: '80vh',
          display: 'flex', flexDirection: 'column',
          boxShadow: '0 8px 32px rgba(11,18,32,0.14)',
          fontFamily: 'var(--font-ui)',
        }}>
          {/* Header */}
          <div style={{
            padding: '18px 20px 0',
            borderBottom: '1px solid var(--ink-200)',
            flexShrink: 0,
          }}>
            <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: 10 }}>
              <div>
                <div style={{ fontSize: 15, fontWeight: 600, color: 'var(--ink-900)' }}>{matter.title}</div>
              </div>
              <button
                onClick={onClose}
                className="size-7 flex items-center justify-center rounded-md text-ink-500 hover:bg-ink-100 hover:text-ink-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent flex-shrink-0"
                aria-label="Close"
              >
                <svg width={16} height={16} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} strokeLinecap="round">
                  <path d="M18 6 6 18M6 6l12 12" />
                </svg>
              </button>
            </div>
            {/* Tabs */}
            <div style={{ display: 'flex', gap: 0 }}>
              <button style={tabStyle(tab === TAB_NOTES)} onClick={() => setTab(TAB_NOTES)}>Notes</button>
              <button style={tabStyle(tab === TAB_BRIEF)} onClick={() => setTab(TAB_BRIEF)}>AI Brief</button>
            </div>
          </div>

          {/* Notes tab */}
          {tab === TAB_NOTES && (<>
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
                  {note.content.startsWith('<') ? (
                    // Legacy HTML notes
                    <div
                      className="note-rich-content"
                      dangerouslySetInnerHTML={{ __html: DOMPurify.sanitize(note.content) }}
                      style={{ fontSize: 14, color: 'var(--ink-800)', lineHeight: 1.5 }}
                    />
                  ) : (
                    // Markdown notes (and old plain-text notes)
                    <div style={{ fontSize: 14, color: 'var(--ink-800)', lineHeight: 1.5 }}>
                      <ReactMarkdown remarkPlugins={[remarkGfm]} components={noteComponents}>
                        {note.content}
                      </ReactMarkdown>
                    </div>
                  )}
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
                      className="font-ui text-xs text-danger hover:opacity-75 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-danger rounded px-1.5 py-0.5"
                    >Delete</button>
                  </div>
                </div>
              ))}
            </div>
            <div style={{ padding: '12px 20px 16px', borderTop: '1px solid var(--ink-200)', flexShrink: 0 }}>
              {/* Rich text editor */}
              <div style={{
                border: '1px solid var(--ink-300)', borderRadius: 'var(--r-sm)',
                background: '#fff', marginBottom: 8,
              }}>
                {/* Toolbar */}
                <div style={{
                  display: 'flex', flexWrap: 'wrap', gap: 1, padding: '4px 6px',
                  borderBottom: '1px solid var(--ink-200)',
                }}>
                  {/* Inline formatting */}
                  <ToolbarBtn label={<strong>B</strong>} title="Bold (Ctrl+B)"
                    active={e?.isActive('bold') ?? false}
                    onClick={() => e?.chain().focus().toggleBold().run()} />
                  <ToolbarBtn label={<em>I</em>} title="Italic (Ctrl+I)"
                    active={e?.isActive('italic') ?? false}
                    onClick={() => e?.chain().focus().toggleItalic().run()} />
                  <ToolbarBtn label={<s>S</s>} title="Strikethrough"
                    active={e?.isActive('strike') ?? false}
                    onClick={() => e?.chain().focus().toggleStrike().run()} />
                  <Sep />
                  {/* Headings */}
                  <ToolbarBtn label="H1" title="Heading 1"
                    active={e?.isActive('heading', { level: 1 }) ?? false}
                    onClick={() => e?.chain().focus().toggleHeading({ level: 1 }).run()} />
                  <ToolbarBtn label="H2" title="Heading 2"
                    active={e?.isActive('heading', { level: 2 }) ?? false}
                    onClick={() => e?.chain().focus().toggleHeading({ level: 2 }).run()} />
                  <ToolbarBtn label="H3" title="Heading 3"
                    active={e?.isActive('heading', { level: 3 }) ?? false}
                    onClick={() => e?.chain().focus().toggleHeading({ level: 3 }).run()} />
                  <Sep />
                  {/* Blocks */}
                  <ToolbarBtn label="•" title="Bullet list"
                    active={e?.isActive('bulletList') ?? false}
                    onClick={() => e?.chain().focus().toggleBulletList().run()} />
                  <ToolbarBtn label="1." title="Numbered list"
                    active={e?.isActive('orderedList') ?? false}
                    onClick={() => e?.chain().focus().toggleOrderedList().run()} />
                  <ToolbarBtn label={<IconBlockquote />} title="Blockquote"
                    active={e?.isActive('blockquote') ?? false}
                    onClick={() => e?.chain().focus().toggleBlockquote().run()} />
                  <ToolbarBtn label="—" title="Horizontal rule"
                    active={false}
                    onClick={() => e?.chain().focus().setHorizontalRule().run()} />
                  <ToolbarBtn label={<IconLink />} title="Insert link"
                    active={e?.isActive('link') ?? false}
                    onClick={handleSetLink} />
                </div>
                {/* Editor body */}
                <EditorContent
                  editor={editor}
                  style={{ padding: '8px 12px', minHeight: 72, fontSize: 13, color: 'var(--ink-900)', cursor: 'text' }}
                />
              </div>
              <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
                <button
                  onClick={handleAdd}
                  disabled={saving || editorEmpty}
                  className="bg-brand text-white font-ui text-sm font-medium rounded-md px-4 py-2 hover:bg-brand-hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-1 disabled:opacity-50 disabled:cursor-not-allowed"
                >{saving ? 'Saving…' : 'Add note'}</button>
              </div>
            </div>
          </>)}

          {/* AI Brief tab */}
          {tab === TAB_BRIEF && (
            <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minHeight: 0 }}>
              <div style={{ padding: '14px 20px 10px', flexShrink: 0, borderBottom: '1px solid var(--ink-100)' }}>
                <div style={{ fontSize: 12, color: 'var(--ink-500)', marginBottom: 10 }}>
                  Synthesise research findings from all threads assigned to this matter.
                </div>
                <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                  <div style={{ display: 'flex', gap: 6 }}>
                    {[{ value: 'brief', label: 'Research summary' }, { value: 'gaps', label: 'Research gaps' }].map(opt => (
                      <button
                        key={opt.value}
                        onClick={() => { setBriefMode(opt.value); setBriefContent(''); setBriefError(''); }}
                        className={`rounded-full px-3 py-1 font-ui text-xs font-medium border focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent ${
                          briefMode === opt.value
                            ? 'bg-accent text-white border-transparent'
                            : 'border-ink-200 text-ink-600 hover:bg-ink-50'
                        }`}
                      >{opt.label}</button>
                    ))}
                  </div>
                  <button
                    onClick={handleGenerateBrief}
                    disabled={briefLoading}
                    className="ml-auto bg-brand text-white font-ui text-sm font-medium rounded-md px-4 py-2 hover:bg-brand-hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-1 disabled:opacity-50 disabled:cursor-not-allowed"
                  >{briefLoading ? 'Generating…' : 'Generate'}</button>
                </div>
              </div>

              <div className="lex-scroll" style={{ flex: 1, overflowY: 'auto', padding: '14px 20px' }}>
                {!briefContent && !briefLoading && !briefError && (
                  <div style={{ color: 'var(--ink-400)', fontSize: 13, fontStyle: 'italic' }}>
                    Select a mode above and click Generate to produce an AI-synthesised{' '}
                    {briefMode === 'gaps' ? 'research gap analysis' : 'briefing note'} from all threads in this matter.
                  </div>
                )}
                {briefLoading && (
                  <div style={{ color: 'var(--ink-500)', fontSize: 13 }}>Analysing research threads…</div>
                )}
                {briefError && (
                  <div style={{ color: 'var(--danger)', fontSize: 13 }}>{briefError}</div>
                )}
                {briefContent && (
                  <div style={{ fontFamily: 'var(--font-serif)', fontSize: 14.5, lineHeight: 1.7, color: 'var(--ink-800)' }}>
                    <ReactMarkdown
                      remarkPlugins={[remarkGfm]}
                      components={{
                        a: ({ node, ...p }) => <a {...p} target="_blank" rel="noopener noreferrer" style={{ color: 'var(--accent)' }} />,
                        p: ({ node, ...p }) => <p {...p} style={{ margin: '0 0 12px' }} />,
                        ul: ({ node, ...p }) => <ul {...p} style={{ margin: '0 0 12px', paddingLeft: 22 }} />,
                        ol: ({ node, ...p }) => <ol {...p} style={{ margin: '0 0 12px', paddingLeft: 22 }} />,
                        li: ({ node, ...p }) => <li {...p} style={{ marginBottom: 3 }} />,
                        blockquote: ({ node, ...p }) => (
                          <blockquote {...p} style={{
                            borderLeft: '3px solid var(--ink-200)', paddingLeft: 12,
                            marginLeft: 0, color: 'var(--ink-600)', fontStyle: 'italic',
                          }} />
                        ),
                        code: ({ node, inline, ...p }) => inline
                          ? <code {...p} style={{ fontFamily: 'var(--font-mono)', fontSize: 12, background: 'var(--ink-100)', padding: '1px 4px', borderRadius: 4, color: 'var(--ink-800)' }} />
                          : <code {...p} style={{ fontFamily: 'var(--font-mono)', fontSize: 12 }} />,
                        pre: ({ node, ...p }) => (
                          <pre {...p} style={{
                            background: 'var(--ink-50)', border: '1px solid var(--ink-200)',
                            borderRadius: 8, padding: '10px 14px', overflowX: 'auto',
                            margin: '0 0 12px', fontFamily: 'var(--font-mono)', fontSize: 12,
                          }} />
                        ),
                        h1: ({ node, ...p }) => <h1 {...p} style={{ fontSize: 17, fontWeight: 700, color: 'var(--ink-900)', margin: '0 0 10px', lineHeight: 1.3, fontFamily: 'var(--font-ui)' }} />,
                        h2: ({ node, ...p }) => <h2 {...p} style={{ fontSize: 15, fontWeight: 600, color: 'var(--ink-900)', margin: '16px 0 6px', lineHeight: 1.3, fontFamily: 'var(--font-ui)' }} />,
                        h3: ({ node, ...p }) => <h3 {...p} style={{ fontSize: 13, fontWeight: 600, color: 'var(--ink-900)', margin: '12px 0 4px', lineHeight: 1.3, fontFamily: 'var(--font-ui)' }} />,
                      }}
                    >
                      {briefContent}
                    </ReactMarkdown>
                  </div>
                )}
              </div>

              {briefContent && (
                <div style={{ padding: '10px 20px 14px', borderTop: '1px solid var(--ink-200)', flexShrink: 0, display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
                  <button
                    onClick={handleCopy}
                    className={`bg-paper border border-ink-200 font-ui text-sm font-medium rounded-md px-4 py-2 hover:bg-ink-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent ${copied ? 'text-accent' : 'text-ink-700'}`}
                  >{copied ? 'Copied!' : 'Copy to clipboard'}</button>
                  <button
                    onClick={handleSaveBriefAsNote}
                    disabled={savingBrief}
                    className="bg-brand text-white font-ui text-sm font-medium rounded-md px-4 py-2 hover:bg-brand-hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-1 disabled:opacity-50 disabled:cursor-not-allowed"
                  >{briefSaved ? 'Saved!' : savingBrief ? 'Saving…' : 'Save as note'}</button>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </>
  );
};

export default MatterNotesModal;
