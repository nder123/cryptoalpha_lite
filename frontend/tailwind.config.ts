import type { Config } from 'tailwindcss';

export default {
    content: ['./index.html', './src/**/*.{ts,tsx}'],
    theme: {
        extend: {
            fontFamily: {
                sans: ['"DM Sans"', 'system-ui', 'sans-serif'],
                mono: ['"JetBrains Mono"', 'monospace'],
            },
            colors: {
                space: {
                    50: '#f4f5ff',
                    100: '#e4e6ff',
                    200: '#c4c9ff',
                    300: '#a4acff',
                    400: '#7684ff',
                    500: '#4f60ff',
                    600: '#3a49db',
                    700: '#2e39ab',
                    800: '#252f86',
                    900: '#1d2666',
                },
            },
            boxShadow: {
                card: '0 20px 45px -15px rgba(23, 30, 60, 0.35)',
            },
        },
    },
    plugins: [],
} satisfies Config;
