// Shared chart formatting helpers and colour palettes for the admin tabs.

export const fmtMs = (ms) => {
    if (ms == null || ms === 0) return '—';
    if (ms >= 60000) return `${(ms / 60000).toFixed(1)}m`;
    if (ms >= 1000) return `${(ms / 1000).toFixed(1)}s`;
    return `${Math.round(ms)}ms`;
};

export const PERF_COLORS = {
    llm: '#6366f1',    // indigo
    lex: '#f59e0b',    // amber
    other: '#94a3b8',  // slate
    total: '#2563eb',  // blue
    ttft: '#10b981',   // emerald
};

export const fmtUsd = (v) => {
    if (!v || v <= 0) return '$0.00';
    if (v < 0.01) return '<$0.01';
    return `$${v.toFixed(2)}`;
};

export const COST_COLORS = {
    spend: '#10b981',   // emerald
    user: '#6366f1',    // indigo
};

