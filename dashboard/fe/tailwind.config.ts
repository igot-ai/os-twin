import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        "primary": "#2563eb",
        "background-light": "#f8fafc",
        "background-dark": "#0f172a",
        "surface": "#ffffff",
        "text-main": "#0f172a",
        "text-muted": "#64748b",
        "border-color": "#e2e8f0",
        "warning": "#eab308",
        "warning-light": "#fef9c3",
        "warning-text": "#854d0e",
        "terminal-bg": "#0f172a",
        "terminal-sys": "#38bdf8",
        "terminal-out": "#e2e8f0"
      },
      fontFamily: {
        "display": ["Plus Jakarta Sans", "sans-serif"],
        "mono": ["IBM Plex Mono", "monospace"]
      },
      borderRadius: {
        "DEFAULT": "4px",
        "md": "6px",
        "lg": "8px",
        "full": "9999px"
      },
      boxShadow: {
        "card": "0 4px 6px -1px rgba(15, 23, 42, 0.05)"
      }
    },
  },
  plugins: [],
};
export default config;
