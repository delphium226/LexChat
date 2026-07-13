import Modal from './ui/Modal';
import { FolderIcon } from './ui/icons';

// "Save thread to matter" dialog. Presentational — the caller owns the assign
// mutation and list refetch via onAssign (pass null to remove from a matter).
export default function AssignMatterModal({ matters, currentMatterId, onAssign, onClose }) {
  return (
    <Modal onClose={onClose} className="w-full max-w-[380px] font-ui">
      <div
        style={{
          padding: '16px 20px 12px',
          borderBottom: '1px solid var(--ink-200)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
        }}
      >
        <span style={{ fontSize: 15, fontWeight: 600, color: 'var(--ink-900)' }}>Save thread to matter</span>
        <button
          onClick={onClose}
          className="size-7 flex items-center justify-center rounded-md text-ink-500 hover:bg-ink-100 hover:text-ink-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent"
          aria-label="Close"
        >
          <svg width={16} height={16} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} strokeLinecap="round">
            <path d="M18 6 6 18M6 6l12 12" />
          </svg>
        </button>
      </div>
      <div style={{ padding: '8px 12px' }}>
        {matters.length === 0 ? (
          <div style={{ padding: '12px 8px', color: 'var(--ink-400)', fontSize: 13, fontStyle: 'italic' }}>
            No matters yet. Create one first.
          </div>
        ) : (
          matters.map(m => {
            const isAssigned = currentMatterId === m.id;
            return (
              <div
                key={m.id}
                onClick={() => onAssign(isAssigned ? null : m.id)}
                style={{
                  padding: '9px 10px',
                  borderRadius: 6,
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  gap: 8,
                  background: isAssigned ? 'var(--accent-soft)' : 'transparent',
                  color: isAssigned ? 'var(--accent-ink)' : 'var(--ink-800)',
                  marginBottom: 2,
                }}
              >
                <FolderIcon />
                <span style={{ flex: 1, fontSize: 13 }}>{m.title}</span>
                {isAssigned && <span style={{ fontSize: 11, color: 'var(--accent)' }}>✓ Assigned</span>}
              </div>
            );
          })
        )}
        {currentMatterId && (
          <div
            onClick={() => onAssign(null)}
            style={{
              padding: '8px 10px',
              borderRadius: 6,
              cursor: 'pointer',
              fontSize: 13,
              color: 'var(--danger)',
              marginTop: 4,
              borderTop: '1px solid var(--ink-200)',
              paddingTop: 10,
            }}
          >
            Remove from matter
          </div>
        )}
      </div>
      <div style={{ height: 8 }} />
    </Modal>
  );
}
