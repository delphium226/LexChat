import { useState } from 'react';
import Modal from './ui/Modal';
import {
  HOUSE_OPTIONS,
  JURISDICTION_OPTIONS,
  LEGISLATION_TYPE_OPTIONS,
  COURT_GROUPS,
  getLatestSession,
  getRecordTypeOptions,
  getSessionFilterLabel,
  getSessionOptions,
} from '../constants/research';

// Research-filters dialog. Draft-and-apply: all edits mutate a local draft and
// are only committed to the persisted filter state (useFilters) / research mode
// (usePreferences) when the user clicks Apply. Cancel / backdrop / ESC discard
// the draft. `initial` seeds the draft from the currently-applied values on open.
export default function ResearchFiltersModal({
  isParliament,
  isWestminster = false,
  botMode = '',
  thisYear,
  initial,
  onApply,
  onClose,
}) {
  const [draft, setDraft] = useState(() => ({ ...initial }));
  const set = (key, value) => setDraft(d => ({ ...d, [key]: value }));

  const {
    researchMode,
    recordType,
    house,
    jurisdiction,
    legislationType,
    currentOnly,
    dateFrom,
    dateTo,
    caseLawCourt,
  } = draft;

  // Filter vocabulary is fixed by the bot's research mode (Holyrood vs Westminster).
  const recordTypeOptions = getRecordTypeOptions(botMode);
  const sessionOptions = getSessionOptions(botMode);
  const latestSession = getLatestSession(botMode);
  const sessionLabel = getSessionFilterLabel(botMode);

  const sessions = Array.isArray(draft.sessions) ? draft.sessions : [];
  const toggleSession = value =>
    setDraft(d => {
      const cur = Array.isArray(d.sessions) ? d.sessions : [];
      const next = cur.includes(value) ? cur.filter(s => s !== value) : [...cur, value];
      return { ...d, sessions: next };
    });

  const showScotlandNINote =
    (jurisdiction === 'scotland' || jurisdiction === 'northern_ireland') && researchMode !== 'legislation_only';

  const sessionsAreDefault = sessions.length === 1 && sessions[0] === latestSession;

  const hasActiveFilters =
    jurisdiction ||
    dateFrom ||
    dateTo !== thisYear ||
    caseLawCourt ||
    legislationType ||
    currentOnly ||
    recordType ||
    house ||
    !sessionsAreDefault;

  const clearAllFilters = () =>
    setDraft(d => ({
      ...d,
      jurisdiction: null,
      dateFrom: '',
      dateTo: thisYear,
      caseLawCourt: '',
      legislationType: null,
      currentOnly: false,
      recordType: null,
      house: null,
      sessions: [latestSession],
    }));

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
      style={isActive ? { background: 'var(--accent-soft-strong)' } : undefined}
      className={`block w-full text-left px-[10px] py-[6px] rounded-md font-ui text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent ${isActive ? 'text-accent-ink font-semibold' : 'text-ink-700 hover:bg-ink-50'}`}
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
    <Modal
      onClose={onClose}
      className={`w-full ${isParliament ? 'max-w-[420px]' : 'max-w-[680px]'} max-h-[85vh] flex flex-col font-ui`}
    >
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
      <div style={{ overflowY: 'auto' }}>
        {/* ── Parliament bot filters — narrow single column ── */}
        {isParliament && (
          <div style={{ padding: '8px 0 4px' }}>
            {/* § House — Westminster only; Holyrood is unicameral */}
            {isWestminster && (
              <>
                {secHead('House')}
                {HOUSE_OPTIONS.map(opt =>
                  optBtn(house === opt.value, () => set('house', opt.value), opt.label)
                )}
                {divider()}
              </>
            )}

            {/* § Record type */}
            {secHead('Record type')}
            {recordTypeOptions.map(opt =>
              optBtn(recordType === opt.value, () => set('recordType', opt.value), opt.label)
            )}

            {/* § Session / Parliament (multiselect) */}
            {divider()}
            {secHead(sessionLabel)}
            {sessionOptions.map(opt => {
              const checked = sessions.includes(opt.value);
              return (
                <button
                  key={opt.value}
                  onClick={() => toggleSession(opt.value)}
                  style={checked ? { background: 'var(--accent-soft-strong)' } : undefined}
                  className={`flex w-full items-center gap-2 text-left px-[10px] py-[6px] rounded-md font-ui text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent ${checked ? 'text-accent-ink font-semibold' : 'text-ink-700 hover:bg-ink-50'}`}
                >
                  <span
                    aria-hidden
                    style={{
                      width: 15,
                      height: 15,
                      flexShrink: 0,
                      borderRadius: 4,
                      border: `1.5px solid ${checked ? 'var(--accent)' : 'var(--ink-300)'}`,
                      background: checked ? 'var(--accent)' : 'transparent',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                    }}
                  >
                    {checked && (
                      <svg width={10} height={10} viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth={3.5} strokeLinecap="round" strokeLinejoin="round">
                        <path d="M20 6 9 17l-5-5" />
                      </svg>
                    )}
                  </span>
                  {opt.label}
                </button>
              );
            })}

            {/* § Date range */}
            {divider()}
            {secHead('Date range')}
            {inputRow('From', dateFrom, v => set('dateFrom', v), 'To', dateTo, v => set('dateTo', v))}
          </div>
        )}

        {/* ── Legislation bot filters — landscape two-column grid ── */}
        {!isParliament && (
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: '1fr 1fr',
              columnGap: 20,
              rowGap: 4,
              padding: '12px 16px 8px',
              alignItems: 'start',
            }}
          >
            {/* § Research type */}
            <div>
              {secHead('Research type')}
              {[
                { value: 'legislation_only', label: 'Legislation only' },
                { value: 'case_law_only', label: 'Case law only' },
                { value: 'legislation_and_case_law', label: 'Legislation & case law' },
              ].map(opt => optBtn(researchMode === opt.value, () => set('researchMode', opt.value), opt.label))}
            </div>

            {/* § Jurisdiction */}
            <div>
              {secHead('Jurisdiction')}
              {JURISDICTION_OPTIONS.map(opt =>
                optBtn(jurisdiction === opt.value, () => set('jurisdiction', opt.value), opt.label)
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
            </div>

            {/* § Legislation type */}
            {researchMode !== 'case_law_only' && (
              <div>
                {secHead('Legislation type')}
                {LEGISLATION_TYPE_OPTIONS.map(opt =>
                  optBtn(legislationType === opt.value, () => set('legislationType', opt.value), opt.label)
                )}
              </div>
            )}

            {/* § Status */}
            {researchMode !== 'case_law_only' && (
              <div>
                {secHead('Status')}
                <div
                  style={{
                    padding: '4px 8px 8px',
                    display: 'flex',
                    alignItems: 'center',
                    gap: 8,
                    cursor: 'pointer',
                  }}
                  onClick={() => set('currentOnly', !currentOnly)}
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
              </div>
            )}

            {/* § Date range */}
            <div>
              {secHead('Date range')}
              {inputRow('From', dateFrom, v => set('dateFrom', v), 'To', dateTo, v => set('dateTo', v))}
            </div>

            {/* § Case law court */}
            {researchMode !== 'legislation_only' && (
              <div>
                {secHead('Case law court')}
                <div style={{ padding: '0 8px 6px' }}>
                  <select
                    value={caseLawCourt}
                    onChange={e => set('caseLawCourt', e.target.value)}
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
              </div>
            )}
          </div>
        )}
      </div>

      {/* Footer — Clear (left) + Cancel / Apply (right) */}
      <div
        style={{
          borderTop: '1px solid var(--ink-200)',
          padding: '10px 16px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: 8,
          flexShrink: 0,
        }}
      >
        <button
          onClick={clearAllFilters}
          disabled={!hasActiveFilters}
          className="font-ui text-xs text-ink-500 underline hover:text-ink-700 hover:no-underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent rounded disabled:opacity-40 disabled:no-underline disabled:cursor-not-allowed"
        >
          Clear filters
        </button>
        <div style={{ display: 'flex', gap: 8 }}>
          <button
            onClick={onClose}
            className="bg-paper border border-ink-200 text-ink-900 font-ui text-sm font-medium rounded-md px-4 py-2 hover:bg-ink-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent"
          >
            Cancel
          </button>
          <button
            onClick={() => onApply(draft)}
            className="bg-brand hover:bg-brand-hover text-white font-ui text-sm font-medium rounded-md px-4 py-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-1"
          >
            Apply
          </button>
        </div>
      </div>
    </Modal>
  );
}
