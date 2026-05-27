import typography from '@tailwindcss/typography';

/** @type {import('tailwindcss').Config} */
export default {
    darkMode: 'class',
    content: [
        "./index.html",
        "./src/**/*.{js,ts,jsx,tsx}",
    ],
    theme: {
        extend: {
            colors: {
                ink: {
                    950: 'var(--ink-950)',
                    900: 'var(--ink-900)',
                    800: 'var(--ink-800)',
                    700: 'var(--ink-700)',
                    600: 'var(--ink-600)',
                    500: 'var(--ink-500)',
                    400: 'var(--ink-400)',
                    300: 'var(--ink-300)',
                    200: 'var(--ink-200)',
                    100: 'var(--ink-100)',
                    50:  'var(--ink-50)',
                    25:  'var(--ink-25)',
                },
                paper:    'var(--paper)',
                'bg-app': 'var(--bg-app)',
                brand: {
                    DEFAULT: 'var(--brand)',
                    hover:   'var(--brand-hover)',
                    soft:    'var(--brand-soft)',
                },
                accent: {
                    DEFAULT: 'var(--accent)',
                    hover:   'var(--accent-hover)',
                    soft:    'var(--accent-soft)',
                    ink:     'var(--accent-ink)',
                },
                cite: {
                    DEFAULT: 'var(--cite)',
                    soft:    'var(--cite-soft)',
                },
                success: {
                    DEFAULT: 'var(--success)',
                    soft:    'var(--success-soft)',
                },
                warn: {
                    DEFAULT: 'var(--warn)',
                    soft:    'var(--warn-soft)',
                },
                danger: {
                    DEFAULT: 'var(--danger)',
                    soft:    'var(--danger-soft)',
                },
                'legal-gold': 'var(--legal-gold)',
            },
            borderRadius: {
                sm: 'var(--r-sm)',
                md: 'var(--r-md)',
                lg: 'var(--r-lg)',
                xl: 'var(--r-xl)',
            },
            boxShadow: {
                sm: 'var(--shadow-sm)',
                md: 'var(--shadow-md)',
            },
            fontFamily: {
                ui:    'var(--font-ui)',
                serif: 'var(--font-serif)',
                mono:  'var(--font-mono)',
            },
            fontSize: {
                display: ['2rem',      { lineHeight: '1.2', fontWeight: '700' }],
                label:   ['0.6875rem', { lineHeight: '1.4', fontWeight: '500', letterSpacing: '0.06em' }],
            },
        },
    },
    plugins: [
        typography,
    ],
}
