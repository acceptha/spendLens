/** @type {import('tailwindcss').Config} */
export default {
  darkMode: "class",
  content: [
    "./index.html",
    "./src/**/*.{ts,tsx}",
    "./node_modules/@tremor/**/*.{js,ts,jsx,tsx}",
  ],
  // Tremor가 fill-cyan-500 같은 클래스를 런타임에 생성하므로 Tailwind 정적 분석이
  // 못 잡음 → safelist로 차트 색이 purge되지 않게 한다.
  safelist: [
    {
      pattern:
        /^(bg|text|border|ring|stroke|fill)-(slate|gray|zinc|red|orange|amber|yellow|lime|green|emerald|teal|cyan|sky|blue|indigo|violet|purple|fuchsia|pink|rose)-(50|100|200|300|400|500|600|700|800|900|950)$/,
    },
  ],
  theme: { extend: {} },
  plugins: [],
};
