import React, { useState } from 'react';
import { createMatter } from '../services/api';

const JURISDICTION_OPTIONS = [
  { value: '', label: 'All UK jurisdictions' },
  { value: 'england_and_wales', label: 'England & Wales' },
  { value: 'scotland', label: 'Scotland' },
  { value: 'northern_ireland', label: 'Northern Ireland' },
  { value: 'wales', label: 'Wales' },
];

const LEGISLATION_TYPE_OPTIONS = [
  { value: '', label: 'All types' },
  { value: 'primary', label: 'Acts (primary)' },
  { value: 'secondary', label: 'SIs & Rules (secondary)' },
  { value: 'draft', label: 'Draft instruments' },
];

const selectStyle = {
  width: '100%',
  boxSizing: 'border-box',
  padding: '8px 12px',
  borderRadius: 'var(--r-sm)',
  border: '1px solid var(--ink-300)',
  fontSize: 14,
  color: 'var(--ink-900)',
  fontFamily: 'var(--font-ui)',
  background: 'var(--paper)',
  outline: 'none',
};

const CreateMatterModal = ({ onClose, onCreated }) => {
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [jurisdiction, setJurisdiction] = useState('');
  const [legislationType, setLegislationType] = useState('');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async () => {
    if (!title.trim()) {
      setError('Title is required.');
      return;
    }
    setSaving(true);
    setError('');
    try {
      const matter = await createMatter(
        title.trim(),
        description.trim() || null,
        jurisdiction || null,
        legislationType || null
      );
      onCreated(matter);
      onClose();
    } catch {
      setError('Failed to create matter. Please try again.');
      setSaving(false);
    }
  };

  const handleKeyDown = e => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
    if (e.key === 'Escape') onClose();
  };

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        background: 'rgba(11,18,32,0.45)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 50,
        padding: 16,
      }}
      onMouseDown={e => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div
        style={{
          background: 'var(--paper)',
          borderRadius: 'var(--r-lg)',
          width: '100%',
          maxWidth: 440,
          boxShadow: '0 8px 32px rgba(11,18,32,0.14)',
          border: '1px solid var(--ink-200)',
          fontFamily: 'var(--font-ui)',
        }}
      >
        <div
          style={{
            padding: '18px 20px 14px',
            borderBottom: '1px solid var(--ink-200)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
          }}
        >
          <span style={{ fontSize: 15, fontWeight: 600, color: 'var(--ink-900)' }}>New matter</span>
          <button
            onClick={onClose}
            className="size-7 flex items-center justify-center rounded-md text-ink-500 hover:bg-ink-100 hover:text-ink-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent"
            aria-label="Close"
          >
            <svg
              width={16}
              height={16}
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth={1.8}
              strokeLinecap="round"
            >
              <path d="M18 6 6 18M6 6l12 12" />
            </svg>
          </button>
        </div>

        <div style={{ padding: '18px 20px' }}>
          <label style={{ display: 'block', fontSize: 12, fontWeight: 600, color: 'var(--ink-700)', marginBottom: 6 }}>
            Matter title <span style={{ color: 'var(--danger)' }}>*</span>
          </label>
          <input
            autoFocus
            value={title}
            onChange={e => setTitle(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="e.g. Judicial review — Planning Authority"
            style={{
              width: '100%',
              boxSizing: 'border-box',
              padding: '8px 12px',
              borderRadius: 'var(--r-sm)',
              border: '1px solid var(--ink-300)',
              fontSize: 14,
              color: 'var(--ink-900)',
              fontFamily: 'var(--font-ui)',
              outline: 'none',
            }}
          />

          <label
            style={{ display: 'block', fontSize: 12, fontWeight: 600, color: 'var(--ink-700)', margin: '14px 0 6px' }}
          >
            Description <span style={{ color: 'var(--ink-400)', fontWeight: 400 }}>(optional)</span>
          </label>
          <textarea
            value={description}
            onChange={e => setDescription(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Brief context for this matter…"
            rows={3}
            style={{
              width: '100%',
              boxSizing: 'border-box',
              padding: '8px 12px',
              borderRadius: 'var(--r-sm)',
              border: '1px solid var(--ink-300)',
              fontSize: 14,
              color: 'var(--ink-900)',
              fontFamily: 'var(--font-ui)',
              resize: 'vertical',
              outline: 'none',
            }}
          />

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10, marginTop: 14 }}>
            <div>
              <label
                style={{ display: 'block', fontSize: 12, fontWeight: 600, color: 'var(--ink-700)', marginBottom: 6 }}
              >
                Jurisdiction <span style={{ color: 'var(--ink-400)', fontWeight: 400 }}>(optional)</span>
              </label>
              <select value={jurisdiction} onChange={e => setJurisdiction(e.target.value)} style={selectStyle}>
                {JURISDICTION_OPTIONS.map(o => (
                  <option key={o.value} value={o.value}>
                    {o.label}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label
                style={{ display: 'block', fontSize: 12, fontWeight: 600, color: 'var(--ink-700)', marginBottom: 6 }}
              >
                Legislation type <span style={{ color: 'var(--ink-400)', fontWeight: 400 }}>(optional)</span>
              </label>
              <select value={legislationType} onChange={e => setLegislationType(e.target.value)} style={selectStyle}>
                {LEGISLATION_TYPE_OPTIONS.map(o => (
                  <option key={o.value} value={o.value}>
                    {o.label}
                  </option>
                ))}
              </select>
            </div>
          </div>

          {error && <div style={{ marginTop: 10, fontSize: 13, color: 'var(--danger)' }}>{error}</div>}
        </div>

        <div
          style={{
            padding: '12px 20px 16px',
            borderTop: '1px solid var(--ink-200)',
            display: 'flex',
            justifyContent: 'flex-end',
            gap: 8,
          }}
        >
          <button
            onClick={onClose}
            className="bg-paper border border-ink-200 text-ink-900 font-ui text-sm font-medium rounded-md px-4 py-2 hover:bg-ink-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent"
          >
            Cancel
          </button>
          <button
            onClick={handleSubmit}
            disabled={saving || !title.trim()}
            className="bg-brand text-white font-ui text-sm font-medium rounded-md px-4 py-2 hover:bg-brand-hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-1 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {saving ? 'Creating…' : 'Create matter'}
          </button>
        </div>
      </div>
    </div>
  );
};

export default CreateMatterModal;
