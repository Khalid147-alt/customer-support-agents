/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,jsx,ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // Linear/Intercom-ish dark palette
        ink: {
          950: "#0b0d12",
          900: "#11141b",
          800: "#181c25",
          700: "#222733",
          600: "#2c3242",
          500: "#3a4154",
          400: "#5b6478",
          300: "#8b94a8",
          200: "#c2c8d4",
          100: "#e6e9f0",
        },
        accent: {
          DEFAULT: "#7c3aed",   // violet-600
          soft: "#a78bfa",
        },
      },
      fontFamily: {
        sans: ["ui-sans-serif", "system-ui", "Inter", "Segoe UI", "Roboto", "sans-serif"],
      },
      keyframes: {
        bounceDot: {
          "0%,80%,100%": { transform: "translateY(0)", opacity: "0.4" },
          "40%":         { transform: "translateY(-4px)", opacity: "1" },
        },
      },
      animation: {
        "bounce-dot": "bounceDot 1.2s infinite ease-in-out",
      },
    },
  },
  plugins: [],
};
