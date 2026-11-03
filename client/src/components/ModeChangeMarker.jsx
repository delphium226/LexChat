// P4.9: a small in-thread note where the research type or the chat mode
// changed between two answers ("Research type changed to Legislation & case
// law"). Display only; where it goes and what it says come from
// `utils/modeChange.js`.
export default function ModeChangeMarker({ parts }) {
  if (!parts?.length) return null;
  return (
    <div role="note" className="flex items-center gap-3 font-ui text-xs text-ink-600">
      <span aria-hidden="true" className="h-px flex-1 bg-ink-200" />
      <span className="text-center">{parts.map(p => p.text).join(' · ')}</span>
      <span aria-hidden="true" className="h-px flex-1 bg-ink-200" />
    </div>
  );
}
