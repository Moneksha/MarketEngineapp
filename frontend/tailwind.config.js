/** @type {import('tailwindcss').Config} */
export default {
    content: [
        "./index.html",
        "./src/**/*.{js,ts,jsx,tsx}",
    ],
    theme: {
        extend: {
            colors: {
                background: "#090C15", // Deep Space Navy
                surface: "#131826", // Elevated dark
                primary: "#05E07D", // Neon profit
                danger: "#FF334B", // Neon loss
                warning: "#FFB020", // Amber neutral
                text: "#F3F4F6", // Primary white
                muted: "#8B95A5", // Muted info
                border: "rgba(255, 255, 255, 0.1)", // Glass borders
            },
            fontFamily: {
                sans: ['Inter', 'sans-serif'],
                mono: ['JetBrains Mono', 'monospace'],
            },
            animation: {
                'pulse-slow': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
                'marquee': 'marquee 30s linear infinite',
                'glow': 'glow 2s ease-in-out infinite alternate',
            },
            keyframes: {
                marquee: {
                    '0%': { transform: 'translateX(0%)' },
                    '100%': { transform: 'translateX(-100%)' },
                },
                glow: {
                    '0%': { boxShadow: '0 0 5px rgba(5, 224, 125, 0.2)' },
                    '100%': { boxShadow: '0 0 20px rgba(5, 224, 125, 0.6)' },
                }
            }
        },
    },
    plugins: [],
}
