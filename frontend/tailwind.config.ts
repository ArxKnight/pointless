import type { Config } from 'tailwindcss';
export default {darkMode:'class',content:['./index.html','./src/**/*.{ts,tsx}'],theme:{extend:{fontFamily:{sans:['Inter','sans-serif'],mono:['JetBrains Mono','monospace']},colors:{bg:'#0f1117',surface:'#1a1d27',border:'#2a2d3e',muted:'#64748b'}}},plugins:[]} satisfies Config;
