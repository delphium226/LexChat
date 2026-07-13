import Modal from './ui/Modal';
import {
  RECORD_TYPE_OPTIONS,
  JURISDICTION_OPTIONS,
  LEGISLATION_TYPE_OPTIONS,
  COURT_GROUPS,
} from '../constants/research';

// Research-filters popover. Presentational — all filter state and persistence
// lives in useFilters (passed in via the `filters` bag) and usePreferences
// (research mode). Rendered as a centered Modal from the composer.
export default function ResearchFiltersModal({
  isParliament,
  researchMode,
  onResearchModeChange,
  showScotlandNINote,
  filters,
  onClose,
}) {
  const {
    recordType,
    setRecordTypePersist,
    jurisdiction,
    setJurisdictionPersist,
    legislationType,
    setLegislationTypePersist,
    currentOnly,
    setCurrentOnlyPersist,
    dateFrom,
    setDateFromPersist,
    dateTo,
    setDateToPersist,
    caseLawCourt,
    setCourtPersist,
    hasActiveFilters,
    clearAllFilters,
  } = filters;

  const secHead = label => (
    <div
      style={{
        fontSize: 11,
        fontWeight: 600,
        color: 'var(--ink-500)',
        textTransform: 'uppercase',
        letterSpacing: '0.06em',
        padding: '4px 8px 6px',
      }}
    >
      {label}
    </div>
  );
  const divider = () => <div style={{ height: 1, background: 'var(--ink-100)', margin: '6px 0' }} />;
  const optBtn = (isActive, onClick, label) => (
    <button
      onClick={onClick}
      className={`block w-full text-left px-[10px] py-[6px] rounded-md font-ui text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent ${isActive ? 'bg-accent-soft text-accent-ink font-semibold' : 'text-ink-700 hover:bg-ink-50'}`}
    >
      {label}
    </button>
  );
  const inputRow = (labelA, valA, setA, labelB, valB, setB) => (
    <div style={{ display: 'flex', gap: 6, padding: '0 8px 6px', alignItems: 'center' }}>
      <input
        type="text"
        placeholder={labelA}
        value={valA}
        maxLength={4}
        onChange={e => setA(e.target.value.replace(/\D/g, '').slice(0, 4))}
        style={{
          flex: 1,
          padding: '4px 7px',
          borderRadius: 6,
          border: '1px solid var(--ink-200)',
          fontSize: 12,
          fontFamily: 'var(--font-ui)',
          background: 'var(--paper)',
          color: 'var(--ink-700)',
          outline: 'none',
        }}
      />
      <span style={{ fontSize: 11, color: 'var(--ink-400)' }}>–</span>
      <input
        type="text"
        placeholder={labelB}
        value={valB}
        maxLength={4}
        onChange={e => setB(e.target.value.replace(/\D/g, '').slice(0, 4))}
        style={{
          flex: 1,
          padding: '4px 7px',
          borderRadius: 6,
          border: '1px solid var(--ink-200)',
          fontSize: 12,
          fontFamily: 'var(--font-ui)',
          background: 'var(--paper)',
          color: 'var(--ink-700)',
          outline: 'none',
        }}
      />
    </div>
  );

  return (
    <Modal onClose={onClose} className="w-full max-w-[420px] max-h-[85vh] flex flex-col font-ui">
      {/* Header */}
      <div
        style={{
          padding: '16px 20px 12px',
          borderBottom: '1px solid var(--ink-200)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexShrink: 0,
        }}
      >
        <span style={{ fontSize: 15, fontWeight: 600, color: 'var(--ink-900)' }}>Research filters</span>
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

      {/* Scrollable body */}
      <div style={{ overflowY: 'auto', padding: '8px 0 4px' }}>
        {/* ── Parliament bot filters (Scottish Parliament only) ── */}
        {isParliament && (
          <>
            {/* § Record type */}
            {secHead('Record type')}
            {RECORD_TYPE_OPTIONS.map(opt =>
              optBtn(recordType === opt.value, () => setRecordTypePersist(opt.value), opt.label)
            )}
          </>
        )}

        {/* ── Legislation bot filters ──────────────────── */}
        {!isParliament && (
          <>
            {/* § Research type */}
            {secHead('Research type')}
            {[
              { value: 'legislation_only', label: 'Legislation only' },
              { value: 'case_law_only', label: 'Case law only' },
              { value: 'legislation_and_case_law', label: 'Legislation & case law' },
            ].map(opt => optBtn(researchMode === opt.value, () => onResearchModeChange(opt.value), opt.label))}

            {divider()}

            {/* § Jurisdiction */}
            {secHead('Jurisdiction')}
            {JURISDICTION_OPTIONS.map(opt =>
              optBtn(jurisdiction === opt.value, () => setJurisdictionPersist(opt.value), opt.label)
            )}
            {showScotlandNINote && (
              <div
                style={{
                  margin: '2px 8px 4px',
                  padding: '5px 8px',
                  borderRadius: 6,
                  background: 'var(--accent-soft)',
                  fontSize: 11,
                  color: 'var(--accent-ink)',
                  lineHeight: 1.4,
                }}
              >
                Case law database covers E&amp;W and UK-wide courts only — Scottish and NI courts are not indexed.
              </div>
            )}

            {/* § Legislation type */}
            {researchMode !== 'case_law_only' && (
              <>
                {divider()}
                {secHead('Legislation type')}
                {LEGISLATION_TYPE_OPTIONS.map(opt =>
                  optBtn(legislationType === opt.value, () => setLegislationTypePersist(opt.value), opt.label)
                )}
                {divider()}
                {secHead('Status')}
                <div
                  style={{
                    padding: '4px 8px 8px',
                    display: 'flex',
                    alignItems: 'center',
                    gap: 8,
                    cursor: 'pointer',
                  }}
                  onClick={() => setCurrentOnlyPersist(!currentOnly)}
                >
                  <div
                    style={{
                      width: 30,
                      height: 17,
                      borderRadius: 9,
                      background: currentOnly ? 'var(--accent)' : 'var(--ink-200)',
                      position: 'relative',
                      flexShrink: 0,
                      transition: 'background 120ms',
                    }}
                  >
                    <span
                      style={{
                        position: 'absolute',
                        top: 2,
                        left: currentOnly ? 15 : 2,
                        width: 13,
                        height: 13,
                        borderRadius: '50%',
                        background: 'white',
                        transition: 'left 120ms',
                        display: 'block',
                      }}
                    />
                  </div>
                  <span
                    style={{
                      fontSize: 13,
                      color: 'var(--ink-700)',
                      fontFamily: 'var(--font-ui)',
                      userSelect: 'none',
                    }}
                  >
                    Current legislation only
                  </span>
                </div>
              </>
            )}
          </>
        )}

        {/* § Date range (common to both bots) */}
        {divider()}
        {secHead('Date range')}
        {inputRow('From', dateFrom, setDateFromPersist, 'To', dateTo, setDateToPersist)}

        {/* § Case law court */}
        {!isParliament && researchMode !== 'legislation_only' && (
          <>
            {divider()}
            {secHead('Case law court')}
            <div style={{ padding: '0 8px 6px' }}>
              <select
                value={caseLawCourt}
                onChange={e => setCourtPersist(e.target.value)}
                style={{
                  width: '100%',
                  padding: '5px 7px',
                  borderRadius: 6,
                  border: '1px solid var(--ink-200)',
                  fontSize: 12,
                  fontFamily: 'var(--font-ui)',
                  background: 'var(--paper)',
                  color: 'var(--ink-700)',
                  cursor: 'pointer',
                  outline: 'none',
                }}
              >
                <option value="">All courts</option>
                {COURT_GROUPS.map(g => (
                  <optgroup key={g.group} label={g.group}>
                    {g.courts.map(c => (
                      <option key={c.value} value={c.value}>
                        {c.label}
                      </option>
                    ))}
                  </optgroup>
                ))}
              </select>
            </div>
          </>
        )}
      </div>

      {/* Footer */}
      {hasActiveFilters && (
        <div
          style={{
            borderTop: '1px solid var(--ink-200)',
            padding: '10px 16px',
            textAlign: 'right',
            flexShrink: 0,
          }}
        >
          <button
            onClick={clearAllFilters}
            className="font-ui text-xs text-ink-500 underline hover:text-ink-700 hover:no-underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent rounded"
          >
            Clear filters
          </button>
        </div>
      )}
    </Modal>
  );
}
