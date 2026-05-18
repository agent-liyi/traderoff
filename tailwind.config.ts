import type { Config } from 'tailwindcss';

const config: Config = {
  content: [
    './src/pages/**/*.{js,ts,jsx,tsx,mdx}',
    './src/components/**/*.{js,ts,jsx,tsx,mdx}',
    './src/app/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        background: '#fafaf9',
        foreground: '#1c1917',
        muted: '#78716c',
        accent: '#b45309',
      },
      fontFamily: {
        sans: ['-apple-system', 'PingFang SC', 'Helvetica Neue', 'Arial', 'sans-serif'],
      },
      lineHeight: {
        relaxed: '1.8',
      },
    },
  },
  plugins: [],
};

export default config;
