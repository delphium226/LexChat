import React from 'react';
import { saveFeatures } from '../../services/api';

/**
 * The feature-flag toggle list, rendered from a subset of `featureFlagDefs`.
 *
 * Extracted from the Developer tab so the caching flags can render on the Cache
 * tab with the same control. One toggle implementation, two call sites.
 *
 * `saveFeatures` POSTs the WHOLE flag object, so `features` must already hold
 * real server state before any toggle here fires — otherwise a toggle silently
 * resets every other flag to the client's placeholder defaults. AdminPortal
 * guarantees that with a mount-once `getFeatures()` rather than a per-tab fetch;
 * do not reintroduce a tab-scoped one.
 */
export const FeatureToggleList = ({ flags, features, setFeatures, isSaving, setIsSaving, onError }) => (
  <div>
    {flags.map(({ flag, label, desc }) => (
      <div key={flag} className="flex items-center justify-between py-3 border-b border-ink-100">
        <div>
          <p className="text-sm font-medium">{label}</p>
          <p className="text-xs text-ink-500">{desc}</p>
        </div>
        <button
          role="switch"
          aria-checked={features[flag]}
          aria-label={label}
          disabled={isSaving}
          onClick={async () => {
            const next = { ...features, [flag]: !features[flag] };
            setIsSaving(true);
            try {
              const saved = await saveFeatures(next);
              setFeatures(saved.features);
            } catch {
              if (onError) onError('Failed to save feature flags.');
            } finally {
              setIsSaving(false);
            }
          }}
          className={`relative inline-flex h-6 w-11 shrink-0 items-center rounded-full transition-colors focus:outline-none ${features[flag] ? 'bg-accent' : 'bg-ink-300'} ${isSaving ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}`}
        >
          <span
            className={`inline-block h-4 w-4 transform rounded-full bg-paper shadow transition-transform ${features[flag] ? 'translate-x-6' : 'translate-x-1'}`}
          />
        </button>
      </div>
    ))}
  </div>
);

export default FeatureToggleList;
