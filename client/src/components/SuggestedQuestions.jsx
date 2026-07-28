import React from 'react';

// One-click chips for the questions the assistant just asked — either the
// follow-ups from its <suggestions> block or the options offered alongside a
// clarifying question. Purely presentational: clicking sends the text verbatim
// as the next user turn. All classes are design tokens per
// docs/frontend/design-system.md (accent = interactive/selected, not brand).

export default function SuggestedQuestions({ suggestions, onSelect, disabled = false }) {
  if (!suggestions?.length) return null;

  return (
    <div role="group" aria-label="Suggested questions" className="mt-3 mb-4">
      <p className="font-ui text-label uppercase tracking-wide text-ink-600 mb-2">
        Suggested next questions
      </p>
      <div className="flex flex-wrap gap-2">
        {suggestions.map((text, i) => (
          <button
            key={`${i}-${text}`}
            type="button"
            onClick={() => onSelect(text)}
            disabled={disabled}
            className="rounded-full px-3 py-1.5 font-ui text-xs text-left
                       border border-ink-200 text-ink-700 bg-paper
                       hover:bg-accent-soft hover:text-accent-ink hover:border-accent
                       focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent
                       disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {text}
          </button>
        ))}
      </div>
    </div>
  );
}
