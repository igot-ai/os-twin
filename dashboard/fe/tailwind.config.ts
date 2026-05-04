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
        "background-light": "#ffffff",
        "background-dark": "#000000",
        "surface": "#ffffff",
        "text-main": "#000000",
        "text-muted": "#6b7280",
        "border-color": "#e5e7eb",
        "warning": "#eab308",
        "warning-light": "#fef9c3",
        "warning-text": "#854d0e",
        "terminal-bg": "#000000",
        "terminal-sys": "#38bdf8",
        "terminal-out": "#e5e7eb"
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
