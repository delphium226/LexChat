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
                'legal-blue': '#1e3a8a',
                'legal-gold': '#c2a355',
                'brand-navy': 'rgb(0, 60, 130)',
                'brand-navy-dark': 'rgb(0, 45, 105)',
            }
        },
    },
    plugins: [
        typography,
    ],
}
