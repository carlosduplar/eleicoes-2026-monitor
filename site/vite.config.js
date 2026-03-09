import path from 'node:path';
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

const projectRoot = __dirname;
const repoRoot = path.resolve(projectRoot, '..');
const dataDirectory = path.resolve(repoRoot, 'data').replace(/\\/g, '/');

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(projectRoot, 'src'),
    },
  },
  server: {
    port: 5173,
    strictPort: true,
    fs: {
      allow: [repoRoot],
    },
    proxy: {
      '/data': {
        target: 'http://localhost:5173',
        changeOrigin: true,
        rewrite: (requestPath) => requestPath.replace(/^\/data/, `/@fs/${dataDirectory}`),
      },
    },
  },
  ssgOptions: {
    script: 'defer',
    dirStyle: 'nested',
    formatting: 'none',
  },
});
