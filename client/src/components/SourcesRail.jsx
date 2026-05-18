import React, { useEffect, useRef } from 'react';

function IBtn({ label, onClick, children, active = false }) {
  const [h, setH] = React.useState(false);
  return (
    <button
      aria-label={label}
      onClick={onClick}
      onMouseEnter={() => setH(true)}
      onMouseLeave={() => setH(false)}
      style={{
        width: 30, height: 30, borderRadius: 8, border: 'none',
        background: active ? 'var(--accent-soft)' : h ? 'var(--ink-100)' : 'transparent',
        color: active ? 'var(--accent)' : 'var(--ink-600)',
        display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
        cursor: 'pointer', transition: 'background 120ms',
      }}
    >{children}</button>
  );
}

const FilterIcon = () => (
  <svg width={16} height={16} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.6} strokeLinecap="round" strokeLinejoin="round">
    <path d="M3 5h18l-7 9v5l-4 2v-7L3 5z" />
  </svg>
);

const ExternalLinkIcon = () => (
  <svg width={14} height={14} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.6} strokeLinecap="round" strokeLinejoin="round">
    <path d="M15 3h6v6M10 14 21 3M21 14v5a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5" />
  </svg>
);


const ChevronRightIcon = () => (
  <svg width={16} height={16} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
    <path d="M9 18l6-6-6-6" />
  </svg>
);

const ChevronLeftIcon = () => (
  <svg width={16} height={16} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
    <path d="M15 18l-6-6 6-6" />
  </svg>
);

const BookIcon = () => (
  <svg width={13} height={13} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.6} strokeLinecap="round" strokeLinejoin="round">
    <path d="M4 4.5A2.5 2.5 0 0 1 6.5 2H20v16H6.5A2.5 2.5 0 0 0 4 20.5z" />
    <path d="M20 18v4H6.5A2.5 2.5 0 0 1 4 19.5" />
  </svg>
);

const GavelIcon = () => (
  <svg width={13} height={13} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.6} strokeLinecap="round" strokeLinejoin="round">
    <path d="M14 3l7 7-4 4-7-7z" />
    <path d="M10 7 3 14l4 4 7-7" />
    <path d="M5 21h10" />
  </svg>
);

function formatExtent(extent) {
  if (!extent || extent.length === 0) return null;
  const all4 = ['England', 'Wales', 'Scotland', 'Northern Ireland'];
  if (all4.every(j => extent.includes(j))) return 'UK-wide';
  if (extent.length === 1) return extent[0];
  const abbr = { England: 'E', Wales: 'W', Scotland: 'S', 'Northern Ireland': 'NI' };
  const parts = extent.map(j => abbr[j] || j);
  if (parts.length === 2) return parts.join(' & ');
  return parts.slice(0, -1).join(', ') + ' & ' + parts[parts.length - 1];
}

const JURISDICTIONS = ['England', 'Wales', 'Scotland', 'Northern Ireland'];

const TYPE_OPTIONS = [
  { id: 'legislation', label: 'Legislation' },
  { id: 'case', label: 'Case law' },
  { id: 'draft', label: 'Draft instruments' },
];

function sourceType(s) {
  if (s.kind === 'Case') return 'case';
  if (s.kind === 'Draft SI') return 'draft';
  return 'legislation';
}

function FilterPill({ label, active, onClick }) {
  const [h, setH] = React.useState(false);
  return (
    <button
      onClick={onClick}
      onMouseEnter={() => setH(true)}
      onMouseLeave={() => setH(false)}
      style={{
        padding: '3px 10px', borderRadius: 999, fontSize: 12, fontWeight: 500,
        border: '1px solid',
        background: active ? 'var(--accent)' : h ? 'var(--ink-100)' : 'transparent',
        borderColor: active ? 'var(--accent)' : 'var(--ink-300)',
        color: active ? 'white' : 'var(--ink-600)',
        cursor: 'pointer', transition: 'all 120ms',
        whiteSpace: 'nowrap',
      }}
    >{label}</button>
  );
}

export default function SourcesRail({ sources = [], activeCite, onCiteClick, collapsed = false, onCollapsedChange }) {
  const activeRef = useRef(null);
  const setCollapsed = (v) => onCollapsedChange?.(v);

  const [showFilter, setShowFilter] = React.useState(false);
  const [filterTypes, setFilterTypes] = React.useState(new Set());
  const [filterJurisdictions, setFilterJurisdictions] = React.useState(new Set());

  const hasActiveFilters = filterTypes.size > 0 || filterJurisdictions.size > 0;

  const toggleType = (id) => setFilterTypes(prev => {
    const next = new Set(prev);
    if (next.has(id)) next.delete(id); else next.add(id);
    return next;
  });

  const toggleJurisdiction = (j) => setFilterJurisdictions(prev => {
    const next = new Set(prev);
    if (next.has(j)) next.delete(j); else next.add(j);
    return next;
  });

  const clearFilters = () => {
    setFilterTypes(new Set());
    setFilterJurisdictions(new Set());
  };

  const visibleSources = sources.filter(s => {
    if (filterTypes.size > 0 && !filterTypes.has(sourceType(s))) return false;
    if (filterJurisdictions.size > 0) {
      const ext = s.extent || [];
      if (![...filterJurisdictions].some(j => ext.includes(j))) return false;
    }
    return true;
  });

  useEffect(() => {
    if (activeRef.current) {
      activeRef.current.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }
  }, [activeCite]);

  const primaryCount = sources.filter(s => s.kind !== 'Case' && s.kind !== 'Article').length;
  const secondaryCount = sources.filter(s => s.kind === 'Case' || s.kind === 'Article').length;

  const subtitle = sources.length === 0
    ? 'No sources yet'
    : hasActiveFilters
      ? `${visibleSources.length} of ${sources.length} shown`
      : `${primaryCount} primary · ${secondaryCount} secondary`;

  if (collapsed) {
    return (
      <aside style={{
        width: 40, flex: '0 0 40px',
        borderLeft: '1px solid var(--ink-200)',
        background: 'var(--paper)',
        display: 'flex', flexDirection: 'column',
        alignItems: 'center', paddingTop: 10,
        minHeight: 0, fontFamily: 'var(--font-ui)',
        transition: 'width 150ms ease',
      }}>
        <IBtn label="Expand sources" onClick={() => setCollapsed(false)}>
          <ChevronLeftIcon />
        </IBtn>
        <div style={{
          marginTop: 12, fontSize: 12, fontWeight: 600,
          color: 'var(--ink-500)', writingMode: 'vertical-rl',
          transform: 'rotate(180deg)', letterSpacing: '0.06em',
          userSelect: 'none',
        }}>
          Sources
        </div>
      </aside>
    );
  }

  return (
    <aside style={{
      width: 380, flex: '0 0 380px',
      borderLeft: '1px solid var(--ink-200)',
      background: 'var(--paper)',
      display: 'flex', flexDirection: 'column',
      minHeight: 0, fontFamily: 'var(--font-ui)',
    }}>
      {/* Header */}
      <div style={{
        padding: '14px 18px',
        borderBottom: '1px solid var(--ink-200)',
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        flex: '0 0 auto',
      }}>
        <div>
          <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--ink-900)' }}>Sources</div>
          <div style={{ fontSize: 11, color: hasActiveFilters ? 'var(--accent)' : 'var(--ink-500)', marginTop: 1 }}>
            {subtitle}
          </div>
        </div>
        <div style={{ display: 'flex', gap: 4 }}>
          <IBtn
            label="Filter sources"
            onClick={() => setShowFilter(v => !v)}
            active={showFilter || hasActiveFilters}
          >
            <FilterIcon />
          </IBtn>
          <IBtn label="Collapse sources" onClick={() => setCollapsed(true)}>
            <ChevronRightIcon />
          </IBtn>
        </div>
      </div>

      {/* Filter panel */}
      {showFilter && (
        <div style={{
          padding: '12px 18px 14px',
          borderBottom: '1px solid var(--ink-200)',
          background: 'var(--ink-50)',
          flex: '0 0 auto',
        }}>
          <div style={{ marginBottom: 10 }}>
            <div style={{
              fontSize: 10.5, fontWeight: 600, color: 'var(--ink-400)',
              textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 6,
            }}>Type</div>
            <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
              {TYPE_OPTIONS.map(({ id, label }) => (
                <FilterPill
                  key={id}
                  label={label}
                  active={filterTypes.has(id)}
                  onClick={() => toggleType(id)}
                />
              ))}
            </div>
          </div>
          <div>
            <div style={{
              fontSize: 10.5, fontWeight: 600, color: 'var(--ink-400)',
              textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 6,
            }}>Jurisdiction</div>
            <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
              {JURISDICTIONS.map(j => (
                <FilterPill
                  key={j}
                  label={j}
                  active={filterJurisdictions.has(j)}
                  onClick={() => toggleJurisdiction(j)}
                />
              ))}
            </div>
          </div>
          {hasActiveFilters && (
            <button
              onClick={clearFilters}
              style={{
                marginTop: 10, fontSize: 11.5, color: 'var(--accent)',
                background: 'none', border: 'none', cursor: 'pointer',
                padding: 0, fontWeight: 500,
              }}
            >Clear filters</button>
          )}
        </div>
      )}

      {/* Source list */}
      <div className="lex-scroll" style={{ flex: 1, overflow: 'auto', padding: '8px 8px 14px' }}>
        {sources.length === 0 ? (
          <div style={{
            padding: '40px 20px', textAlign: 'center',
            color: 'var(--ink-400)', fontSize: 13, lineHeight: 1.6,
            fontFamily: 'var(--font-ui)',
          }}>
            <div style={{ fontSize: 30, marginBottom: 12, opacity: 0.3, lineHeight: 1 }}>⚖</div>
            Sources will appear here as the research agent cites legislation and case law.
          </div>
        ) : visibleSources.length === 0 ? (
          <div style={{
            padding: '40px 20px', textAlign: 'center',
            color: 'var(--ink-400)', fontSize: 13, lineHeight: 1.6,
            fontFamily: 'var(--font-ui)',
          }}>
            No sources match the current filters.
          </div>
        ) : (
          visibleSources.map(s => {
            const active = s.n === activeCite;
            const isDraftSI = s.kind === 'Draft SI';
            const isCase = s.kind === 'Case';
            const badgeBg = isCase ? 'oklch(0.95 0.04 65)' : isDraftSI ? 'oklch(0.96 0.06 85)' : 'oklch(0.95 0.03 155)';
            const badgeBorder = isCase ? 'oklch(0.85 0.08 65)' : isDraftSI ? 'oklch(0.88 0.10 85)' : 'oklch(0.85 0.06 155)';
            const badgeColor = isCase ? 'oklch(0.40 0.12 65)' : isDraftSI ? 'oklch(0.40 0.14 85)' : 'oklch(0.35 0.10 155)';

            const extentStr = formatExtent(s.extent);
            const metaParts = [s.year, s.meta, extentStr].filter(Boolean);
            const displayMeta = metaParts.length > 0 ? metaParts.join(' · ') : null;

            return (
              <div
                key={s.n}
                ref={active ? activeRef : null}
                onClick={() => onCiteClick?.(s.n)}
                style={{
                  padding: 14, borderRadius: 10, margin: '6px 8px',
                  background: active ? 'var(--accent-soft)' : 'var(--paper)',
                  border: `1px solid ${active ? 'oklch(0.88 0.04 240)' : 'var(--ink-200)'}`,
                  cursor: 'pointer', transition: 'all 120ms',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
                  <span style={{
                    width: 22, height: 22, borderRadius: 6, fontSize: 11, fontWeight: 700,
                    background: active ? 'var(--accent)' : 'var(--ink-100)',
                    color: active ? 'white' : 'var(--ink-700)',
                    display: 'grid', placeItems: 'center', flex: '0 0 22px',
                  }}>{s.n}</span>
                  <span style={{
                    display: 'inline-flex', alignItems: 'center', gap: 4,
                    padding: '3px 8px', borderRadius: 999, fontSize: 12, fontWeight: 500,
                    border: '1px solid',
                    background: badgeBg, borderColor: badgeBorder, color: badgeColor,
                  }}>
                    {isCase ? <GavelIcon /> : <BookIcon />}
                    {s.kind}
                  </span>
                </div>

                <div style={{ fontSize: 13.5, fontWeight: 600, color: 'var(--ink-900)', marginBottom: 2 }}>{s.title}</div>
                {s.sub && <div style={{ fontSize: 12, color: 'var(--ink-600)', marginBottom: 8 }}>{s.sub}</div>}
                {displayMeta && <div style={{ fontSize: 11, color: 'var(--ink-400)', marginBottom: s.excerpt ? 8 : 0, fontFamily: 'var(--font-mono)' }}>{displayMeta}</div>}

                {s.excerpt && (
                  <div style={{
                    fontFamily: 'var(--font-serif)', fontSize: 12.5, color: 'var(--ink-700)',
                    lineHeight: 1.55,
                    borderLeft: `3px solid ${active ? 'var(--accent)' : 'var(--ink-200)'}`,
                    paddingLeft: 10, fontStyle: 'italic', marginBottom: 8,
                  }}>
                    &ldquo;{s.excerpt}&rdquo;
                  </div>
                )}

                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', fontSize: 11, color: 'var(--ink-500)', marginTop: 6 }}>
                  <span style={{ fontFamily: 'var(--font-mono)' }}>{s.cite}</span>
                  {s.url && (
                    <a
                      href={s.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      onClick={e => e.stopPropagation()}
                      style={{
                        display: 'inline-flex', alignItems: 'center', gap: 4,
                        color: 'var(--accent)', fontWeight: 500, textDecoration: 'none',
                      }}
                    >
                      Open <ExternalLinkIcon />
                    </a>
                  )}
                </div>
              </div>
            );
          })
        )}
      </div>
    </aside>
  );
}
