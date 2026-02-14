import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],

  // ── Dev server ─────────────────────────────────────────────────────────────
  server: {
    port: 3000,
    // Proxy for local dev only; production uses VITE_API_BASE_URL directly.
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
    },
  },

  // ── Production build ───────────────────────────────────────────────────────
  build: {
    outDir: 'dist',
    sourcemap: false,

    rollupOptions: {
      output: {
        // Split large deps into separate cacheable chunks
        manualChunks(id) {
          if (id.includes('node_modules/three'))     return 'three';
          if (id.includes('node_modules/react-dom')) return 'react-dom';
          if (id.includes('node_modules/react'))     return 'react';
          if (id.includes('node_modules'))           return 'vendor';
        },
      },
    },
  },

  // ── Drop console.log / debugger in production bundle ───────────────────────
  esbuild: {
    drop: ['console', 'debugger'],
  },
});
