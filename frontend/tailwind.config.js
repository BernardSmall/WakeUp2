/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        canvas: "#0a1118",
        panel: "#111b24",
        teal: "#2dd4bf",
      },
    },
  },
  plugins: [],
};
