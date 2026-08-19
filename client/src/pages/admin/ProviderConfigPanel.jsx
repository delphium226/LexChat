import React from 'react';
import { getProviderConfig, saveProviderConfig, setActiveProvider, getOpenRouterModels } from '../../services/api';
import Spinner from '../../components/ui/Spinner';
import InfoTip from '../../components/ui/InfoTip';
import { Card, SectionHeader } from '../../components/ui/Card';

const PROVIDER_DISPLAY = {
  ollama: 'Ollama (Local)',
  openrouter: 'OpenRouter',
};

const Field = ({ label, children, hint }) => (
  <div>
    <label className="block text-xs font-semibold text-ink-600 uppercase tracking-wide mb-1">{label}</label>
    {children}
    {hint && <p className="text-xs text-ink-400 mt-0.5">{hint}</p>}
  </div>
);

// Type-ahead combobox for selecting a model from a large list.
const ModelCombobox = ({ value, onChange, models, loading, error }) => {
  const [query, setQuery] = React.useState('');
  const [open, setOpen] = React.useState(false);
  const containerRef = React.useRef(null);

  const filtered = React.useMemo(() => {
    if (!query) return models;
    const q = query.toLowerCase();
    return models.filter(m => m.name.toLowerCase().includes(q));
  }, [models, query]);

  const handleSelect = name => {
    onChange(name);
    setQuery('');
    setOpen(false);
  };

  const handleBlur = e => {
    // Close only when focus leaves the whole container
    if (!containerRef.current?.contains(e.relatedTarget)) {
      setOpen(false);
      setQuery('');
    }
  };

  return (
    <div ref={containerRef} className="relative" onBlur={handleBlur}>
      <input
        type="text"
        value={open ? query : value || ''}
        onChange={e => {
          setQuery(e.target.value);
          setOpen(true);
        }}
        onFocus={() => setOpen(true)}
        placeholder={loading ? 'Loading models…' : open ? 'Search models…' : value || 'Select a model'}
        disabled={loading}
        className="w-full text-sm border border-ink-300 rounded-md px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50"
      />
      {loading && (
        <div className="absolute right-2.5 top-1/2 -translate-y-1/2">
          <Spinner size="sm" />
        </div>
      )}
      {open && !loading && (
        <ul
          tabIndex={-1}
          className="absolute z-20 mt-1 w-full max-h-64 overflow-auto bg-paper border border-ink-200 rounded-md shadow-lg text-sm"
        >
          {error && <li className="px-3 py-2 text-red-500 dark:text-red-400">{error}</li>}
          {!error && filtered.length === 0 && <li className="px-3 py-2 text-ink-400">No models match</li>}
          {!error &&
            filtered.map(m => (
              <li
                key={m.name || '__blank__'}
                tabIndex={-1}
                onMouseDown={() => handleSelect(m.name)}
                className={`flex items-center justify-between px-3 py-1.5 cursor-pointer hover:bg-accent-soft ${m.name === value ? 'bg-accent-soft font-medium' : ''}`}
              >
                <span className={`truncate ${m.name ? 'text-ink-900 ' : 'text-ink-400 italic'}`}>
                  {m.name || '— Same as Active Model —'}
                </span>
                {m.context_kb != null && (
                  <span className="ml-3 flex-shrink-0 text-xs text-ink-400">{m.context_kb}K ctx</span>
                )}
              </li>
            ))}
        </ul>
      )}
    </div>
  );
};

const PROVIDER_DEFAULTS = {
  openrouter: {
    model: 'google/gemini-3.1-pro-preview',
    summarisation_model: 'google/gemini-3-flash-preview',
  },
  ollama: {
    model: 'mistral-large-3:675b-cloud',
    summarisation_model: '',
  },
};

export const ProviderConfigPanel = () => {
  const [data, setData] = React.useState(null); // full GET response
  const [selectedId, setSelectedId] = React.useState(null); // which provider card is selected for editing
  const [drafts, setDrafts] = React.useState({}); // {providerId: {config fields}}
  const [showKeys, setShowKeys] = React.useState({}); // {providerId: bool}
  const [savingConfig, setSavingConfig] = React.useState(false);
  const [switchingActive, setSwitchingActive] = React.useState(false);
  const [statusMsg, setStatusMsg] = React.useState(null);
  const [orModels, setOrModels] = React.useState([]);
  const [orModelsLoading, setOrModelsLoading] = React.useState(false);
  const [orModelsError, setOrModelsError] = React.useState(null);

  const flash = (type, text) => {
    setStatusMsg({ type, text });
    setTimeout(() => setStatusMsg(null), 4000);
  };

  React.useEffect(() => {
    getProviderConfig()
      .then(res => {
        setData(res);
        setSelectedId(res.active_provider);
        // Seed drafts from current config
        const d = {};
        res.providers.forEach(p => {
          d[p.id] = { ...p.config };
        });
        setDrafts(d);
      })
      .catch(() => flash('error', 'Failed to load provider config.'));
  }, []);

  React.useEffect(() => {
    if (selectedId !== 'openrouter') return;
    if (orModels.length > 0) return; // already loaded
    setOrModelsLoading(true);
    setOrModelsError(null);
    getOpenRouterModels()
      .then(res => setOrModels(res.models))
      .catch(err => {
        const detail = err?.response?.data?.detail || 'Failed to load OpenRouter models.';
        setOrModelsError(detail);
      })
      .finally(() => setOrModelsLoading(false));
  }, [selectedId]);

  const updateDraft = (providerId, key, value) => {
    setDrafts(prev => ({
      ...prev,
      [providerId]: { ...prev[providerId], [key]: value },
    }));
  };

  const handleSaveConfig = async () => {
    if (!selectedId) return;
    setSavingConfig(true);
    try {
      await saveProviderConfig(selectedId, drafts[selectedId]);
      setData(prev => ({
        ...prev,
        providers: prev.providers.map(p => (p.id === selectedId ? { ...p, config: { ...drafts[selectedId] } } : p)),
      }));
      flash('success', `${PROVIDER_DISPLAY[selectedId]} settings saved.`);
    } catch {
      flash('error', 'Failed to save settings.');
    } finally {
      setSavingConfig(false);
    }
  };

  const handleSetToDefault = () => {
    if (!selectedId) return;
    const defaults = PROVIDER_DEFAULTS[selectedId];
    if (!defaults) return;
    setDrafts(prev => {
      const current = prev[selectedId] || {};
      return {
        ...prev,
        [selectedId]: { ...current, ...defaults, api_key: current.api_key },
      };
    });
  };

  const handleSetActive = async () => {
    if (!selectedId || selectedId === data?.active_provider) return;
    setSwitchingActive(true);
    try {
      await setActiveProvider(selectedId);
      setData(prev => ({ ...prev, active_provider: selectedId }));
      flash('success', `Switched to ${PROVIDER_DISPLAY[selectedId]}. Takes effect for all new requests.`);
    } catch {
      flash('error', 'Failed to switch provider.');
    } finally {
      setSwitchingActive(false);
    }
  };

  if (!data) {
    return (
      <Card className="flex items-center gap-3">
        <Spinner size="sm" />
        <span className="font-ui text-sm text-ink-500">Loading provider config…</span>
      </Card>
    );
  }

  const activeInfo = data.providers.find(p => p.id === data.active_provider);
  const selectedProvider = data.providers.find(p => p.id === selectedId);
  const draft = drafts[selectedId] || {};
  const isActive = selectedId === data.active_provider;
  const hasApiKey = !!draft.api_key;

  return (
    <Card className="space-y-6">
      {/* Header */}
      <SectionHeader
        title="LLM Provider"
        className=""
        right={
          <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full font-ui text-xs font-semibold bg-success-soft text-success">
            <span className="w-2 h-2 rounded-full bg-success inline-block"></span>
            Active: {activeInfo?.name ?? data.active_provider}
          </span>
        }
      />

      {/* Provider picker */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        {data.providers.map(provider => {
          const isSel = selectedId === provider.id;
          const isAct = data.active_provider === provider.id;
          return (
            <button
              key={provider.id}
              onClick={() => setSelectedId(provider.id)}
              className={`text-left p-4 rounded-lg border-2 transition-colors ${
                isSel ? 'border-accent bg-accent-soft' : 'border-ink-200 hover:border-ink-300'
              }`}
            >
              <div className="flex items-center justify-between mb-1">
                <span className="font-semibold text-sm">{provider.name}</span>
                <div className="flex items-center gap-1.5">
                  {isAct && (
                    <span className="font-ui text-xs px-1.5 py-0.5 rounded bg-success-soft text-success font-medium">
                      Active
                    </span>
                  )}
                  {isSel && (
                    <svg
                      xmlns="http://www.w3.org/2000/svg"
                      viewBox="0 0 20 20"
                      fill="currentColor"
                      className="w-4 h-4 text-accent flex-shrink-0"
                    >
                      <path
                        fillRule="evenodd"
                        d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.857-9.809a.75.75 0 00-1.214-.882l-3.483 4.79-1.88-1.88a.75.75 0 10-1.06 1.061l2.5 2.5a.75.75 0 001.137-.089l4-5.5z"
                        clipRule="evenodd"
                      />
                    </svg>
                  )}
                </div>
              </div>
              <p className="text-xs text-ink-400">
                {provider.id === 'openrouter'
                  ? 'Dynamic models'
                  : `${provider.model_list.length} model${provider.model_list.length !== 1 ? 's' : ''}`}{' '}
                · {drafts[provider.id]?.model || provider.config.model}
              </p>
            </button>
          );
        })}
      </div>

      {/* Config fields for selected provider */}
      {selectedProvider && (
        <div className="space-y-4 pt-2 border-t border-ink-100">
          <h3 className="text-sm font-semibold text-ink-700">Configure: {selectedProvider.name}</h3>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {/* Base URL */}
            <Field label="Base URL" hint="Endpoint for this provider's API">
              <input
                type="text"
                value={draft.base_url || ''}
                onChange={e => updateDraft(selectedId, 'base_url', e.target.value)}
                className="w-full text-sm border border-ink-300 rounded-md px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </Field>

            {/* API Key */}
            <Field label="API Key" hint="Stored in database. Leave blank to use .env value.">
              <div className="flex gap-1.5">
                <input
                  type={showKeys[selectedId] ? 'text' : 'password'}
                  value={draft.api_key || ''}
                  onChange={e => updateDraft(selectedId, 'api_key', e.target.value)}
                  placeholder={hasApiKey ? '••••••••' : 'Not set'}
                  className="flex-1 text-sm border border-ink-300 rounded-md px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
                <button
                  type="button"
                  onClick={() => setShowKeys(prev => ({ ...prev, [selectedId]: !prev[selectedId] }))}
                  className="px-2 py-1.5 text-xs border border-ink-200 rounded-md text-ink-500 hover:bg-ink-50 font-ui focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent"
                >
                  {showKeys[selectedId] ? 'Hide' : 'Show'}
                </button>
              </div>
            </Field>

            {/* Active Model */}
            <Field label="Active Model" hint="Model used for Manager and Worker agents">
              {selectedId === 'openrouter' ? (
                <ModelCombobox
                  value={draft.model || ''}
                  onChange={v => updateDraft(selectedId, 'model', v)}
                  models={orModels}
                  loading={orModelsLoading}
                  error={orModelsError}
                />
              ) : (
                <select
                  value={draft.model || ''}
                  onChange={e => updateDraft(selectedId, 'model', e.target.value)}
                  className="w-full text-sm border border-ink-300 rounded-md px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  {selectedProvider.model_list.map(m => (
                    <option key={m.name} value={m.name}>
                      {m.name} ({m.context_kb}K ctx)
                    </option>
                  ))}
                </select>
              )}
            </Field>

            {/* Summarisation Model */}
            <Field
              label="Summarisation Model"
              hint="Faster/cheaper model for document summarisation. Leave blank to use the Active Model."
            >
              {selectedId === 'openrouter' ? (
                <ModelCombobox
                  value={draft.summarisation_model || ''}
                  onChange={v => updateDraft(selectedId, 'summarisation_model', v)}
                  models={[{ name: '', context_kb: null }, ...orModels]}
                  loading={orModelsLoading}
                  error={orModelsError}
                />
              ) : (
                <select
                  value={draft.summarisation_model || ''}
                  onChange={e => updateDraft(selectedId, 'summarisation_model', e.target.value)}
                  className="w-full text-sm border border-ink-300 rounded-md px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  <option value="">— Same as Active Model —</option>
                  {selectedProvider.model_list.map(m => (
                    <option key={m.name} value={m.name}>
                      {m.name} ({m.context_kb}K ctx)
                    </option>
                  ))}
                </select>
              )}
            </Field>

            {/* Temperature */}
            <Field label="Temperature" hint="0 = deterministic · 1 = creative (default 0.1)">
              <input
                type="number"
                min="0"
                max="2"
                step="0.05"
                value={draft.temperature ?? 0.1}
                onChange={e => updateDraft(selectedId, 'temperature', parseFloat(e.target.value))}
                className="w-full text-sm border border-ink-300 rounded-md px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </Field>

            {/* Max Concurrent Requests */}
            <Field label="Max Concurrent Requests" hint="Queue depth — simultaneous users served">
              <input
                type="number"
                min="1"
                max="50"
                step="1"
                value={draft.max_concurrent_requests ?? 3}
                onChange={e => updateDraft(selectedId, 'max_concurrent_requests', parseInt(e.target.value))}
                className="w-full text-sm border border-ink-300 rounded-md px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </Field>

            {/* Max Concurrent Summarisations */}
            <Field label="Max Concurrent Summarisations" hint="Parallel large-document jobs (keep low for local)">
              <input
                type="number"
                min="1"
                max="20"
                step="1"
                value={draft.max_summarise_concurrency ?? 1}
                onChange={e => updateDraft(selectedId, 'max_summarise_concurrency', parseInt(e.target.value))}
                className="w-full text-sm border border-ink-300 rounded-md px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </Field>
          </div>

          {/* Actions */}
          <div className="flex items-center gap-3 pt-1">
            <button
              onClick={handleSaveConfig}
              disabled={savingConfig}
              className="px-5 py-2 bg-brand hover:bg-brand-hover text-white rounded-md font-ui text-sm font-medium disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-1"
            >
              {savingConfig && <Spinner size="sm" />}
              {savingConfig ? 'Saving…' : 'Save Settings'}
            </button>

            {PROVIDER_DEFAULTS[selectedId] && (
              <button
                onClick={handleSetToDefault}
                className="px-5 py-2 bg-paper border border-ink-200 text-ink-900 rounded-md hover:bg-ink-50 font-ui text-sm font-medium focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent"
              >
                Set to default
              </button>
            )}

            {!isActive && (
              <button
                onClick={handleSetActive}
                disabled={switchingActive}
                className="px-5 py-2 bg-brand hover:bg-brand-hover text-white rounded-md font-ui text-sm font-medium disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-1"
              >
                {switchingActive && <Spinner size="sm" />}
                {switchingActive ? 'Switching…' : `Set as Active`}
              </button>
            )}

            {statusMsg && (
              <span
                className={`font-ui text-sm font-medium ${statusMsg.type === 'success' ? 'text-success' : 'text-danger'}`}
              >
                {statusMsg.text}
              </span>
            )}
          </div>
        </div>
      )}
    </Card>
  );
};

export default ProviderConfigPanel;
