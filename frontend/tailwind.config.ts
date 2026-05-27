import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        "tm-bg": "#080c14",
        "tm-card": "#111827",
        "tm-green": "#00f5a0",
        "tm-red": "#ff4466",
        "tm-blue": "#4facfe",
        "tm-gold": "#ffd700",
        "tm-purple": "#a78bfa",
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "monospace"],
      },
      animation: {
        "slide-in": "slide-in 0.4s ease forwards",
        "fade-in": "fade-in 0.3s ease",
        "pulse-green": "pulse-green 2s infinite",
      },
    },
  },
  plugins: [],
};

export default config;
