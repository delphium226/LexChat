import React, { useState } from 'react';

// Deep Research plan review card. Renders the planner's drafted plan as an
// editable ordered list — edit title/detail, delete, add, reorder — with
// "Run research" (primary) and "Cancel" (secondary) actions. All classes are
// design tokens per docs/frontend/design-system.md.

let nextLocalId = 1000; // client-side ids for steps added during review

export default function DeepResearchPlan({ plan, onRun, onCancel, disabled = false }) {
  const [scopeNote, setScopeNote] = useState(plan.scope_note || '');
  const [steps, setSteps] = useState(
    (plan.steps || []).map(s => ({ id: s.id ?? nextLocalId++, title: s.title || '', detail: s.detail || '' }))
  );

  const updateStep = (id, field, value) =>
    setSteps(prev => prev.map(s => (s.id === id ? { ...s, [field]: value } : s)));

  const deleteStep = id => setSteps(prev => prev.filter(s => s.id !== id));

  const addStep = () => setSteps(prev => [...prev, { id: nextLocalId++, title: '', detail: '' }]);

  const moveStep = (index, delta) =>
    setSteps(prev => {
      const target = index + delta;
      if (target < 0 || target >= prev.length) return prev;
      const next = [...prev];
      [next[index], next[target]] = [next[target], next[index]];
      return next;
    });

  const validSteps = steps.filter(s => s.title.trim());
  const canRun = validSteps.length >= 1 && validSteps.length <= 8 && !disabled;

  const handleRun = () => {
    if (!canRun) return;
    onRun({
      scope_note: scopeNote.trim(),
      steps: validSteps.map((s, i) => ({ id: i + 1, title: s.title.trim(), detail: s.detail.trim() })),
    });
  };

  const iconBtnClass =
    'size-[30px] flex items-center justify-center rounded-md text-ink-500 hover:bg-ink-100 hover:text-ink-900 ' +
    'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent ' +
    'disabled:opacity-40 disabled:cursor-not-allowed disabled:hover:bg-transparent';

  const inputClass =
    'w-full border border-ink-200 rounded-sm px-3 py-2 font-ui text-sm bg-paper text-ink-900 ' +
    'placeholder:text-ink-400 focus:outline-none focus:ring-2 focus:ring-accent focus:border-accent';

  return (
    <div className="bg-paper rounded-lg shadow-md border border-ink-100 p-4 my-3">
      {/* Header */}
      <div className="flex items-center gap-2 mb-1">
        <span className="bg-accent-soft text-accent-ink rounded-full px-2 py-0.5 font-ui text-label uppercase tracking-wide">
          Deep Research
        </span>
        <h2 className="font-ui text-base font-semibold text-ink-900 m-0">Proposed research plan</h2>
      </div>
      <p className="font-ui text-xs text-ink-600 mt-0 mb-3">
        Review and edit the steps below. Each step runs as an independent research task; nothing is executed
        until you click Run research.
      </p>

      {/* Scope note */}
      <label className="font-ui text-label uppercase tracking-wide text-ink-600 block mb-1">Scope</label>
      <textarea
        value={scopeNote}
        onChange={e => setScopeNote(e.target.value)}
        rows={2}
        disabled={disabled}
        placeholder="What this plan covers and any deliberate exclusions"
        className={`${inputClass} resize-none mb-3`}
      />

      {/* Steps */}
      <ol className="list-none m-0 p-0 flex flex-col gap-2">
        {steps.map((step, index) => (
          <li key={step.id} className="border border-ink-200 rounded-md p-3 flex gap-3">
            <div className="font-ui text-sm font-semibold text-ink-500 pt-2 w-5 text-right shrink-0">
              {index + 1}
            </div>
            <div className="flex-1 flex flex-col gap-2 min-w-0">
              <input
                type="text"
                value={step.title}
                onChange={e => updateStep(step.id, 'title', e.target.value)}
                disabled={disabled}
                placeholder="Step title (what to find)"
                className={inputClass}
                aria-label={`Step ${index + 1} title`}
              />
              <textarea
                value={step.detail}
                onChange={e => updateStep(step.id, 'detail', e.target.value)}
                rows={2}
                disabled={disabled}
                placeholder="Detail — Acts, provisions, issues, identifiers"
                className={`${inputClass} resize-none`}
                aria-label={`Step ${index + 1} detail`}
              />
            </div>
            <div className="flex flex-col gap-1 shrink-0">
              <button
                type="button"
                onClick={() => moveStep(index, -1)}
                disabled={disabled || index === 0}
                title="Move up"
                aria-label={`Move step ${index + 1} up`}
                className={iconBtnClass}
              >
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round"><path d="M18 15l-6-6-6 6" /></svg>
              </button>
              <button
                type="button"
                onClick={() => moveStep(index, 1)}
                disabled={disabled || index === steps.length - 1}
                title="Move down"
                aria-label={`Move step ${index + 1} down`}
                className={iconBtnClass}
              >
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round"><path d="M6 9l6 6 6-6" /></svg>
              </button>
              <button
                type="button"
                onClick={() => deleteStep(step.id)}
                disabled={disabled || steps.length <= 1}
                title="Delete step"
                aria-label={`Delete step ${index + 1}`}
                className={`${iconBtnClass} hover:text-danger`}
              >
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M3 6h18M8 6V4a1 1 0 011-1h6a1 1 0 011 1v2m3 0v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6" /></svg>
              </button>
            </div>
          </li>
        ))}
      </ol>

      {/* Add step */}
      <button
        type="button"
        onClick={addStep}
        disabled={disabled || steps.length >= 8}
        className="text-accent-ink font-ui text-sm rounded-md px-3 py-1.5 mt-2 hover:bg-accent-soft focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent disabled:opacity-50 disabled:cursor-not-allowed"
      >
        + Add step
      </button>

      {/* Actions */}
      <div className="flex items-center justify-end gap-2 mt-4 pt-3 border-t border-ink-100">
        <button
          type="button"
          onClick={onCancel}
          disabled={disabled}
          className="bg-paper border border-ink-200 text-ink-900 font-ui text-sm font-medium rounded-md px-4 py-2 hover:bg-ink-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent disabled:opacity-50 disabled:cursor-not-allowed"
        >
          Cancel
        </button>
        <button
          type="button"
          onClick={handleRun}
          disabled={!canRun}
          className="bg-brand hover:bg-brand-hover text-white font-ui text-sm font-medium rounded-md px-4 py-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-1 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          Run research ({validSteps.length} step{validSteps.length === 1 ? '' : 's'})
        </button>
      </div>
    </div>
  );
}
