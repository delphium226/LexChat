import React from 'react';

/**
 * The admin-panel card and its heading.
 *
 * Both recipes already existed — as copy-pasted className literals that had
 * drifted apart. `bg-paper p-6 rounded-lg shadow` appeared five times on the
 * Developer tab alone, some copies carrying a border and some not, and headings
 * were split between `text-lg font-bold` and the design-system's Heading 2.
 * Extracting them is what stops the drift recurring.
 *
 * The base matches docs/frontend/design-system.md § Card except for padding:
 * `p-6` rather than the documented `p-4`, because these are full-width panels
 * rather than tiles, and p-6 is what every panel on the tab already used.
 */

const TONES = {
  default: 'border-ink-100',
  danger: 'border-danger',
};

export const Card = ({ tone = 'default', className = '', children }) => (
  <div
    className={`bg-paper rounded-lg shadow-md border ${TONES[tone] || TONES.default} p-6 ${className}`}
  >
    {children}
  </div>
);

/**
 * Card header. `right` is the slot for a control that belongs to the panel as a
 * whole rather than to any one field — BackupStatus's Refresh button, the
 * provider panel's "Active:" pill.
 */
export const SectionHeader = ({ title, description, right, tone = 'default', className }) => (
  <div className={className ?? (description ? 'mb-4' : 'mb-3')}>
    <div className="flex flex-wrap items-start justify-between gap-3">
      <h2
        className={`font-ui text-base font-semibold ${
          tone === 'danger' ? 'text-danger' : 'text-ink-900'
        }`}
      >
        {title}
      </h2>
      {right}
    </div>
    {description && <p className="font-ui text-sm text-ink-500 mt-1">{description}</p>}
  </div>
);

export default Card;
