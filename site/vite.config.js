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
    includedRoutes: (paths) => {
      const candidateSlugs = [
        'lula',
        'flavio-bolsonaro',
        'tarcisio',
        'caiado',
        'zema',
        'ratinho-jr',
        'eduardo-leite',
        'aldo-rebelo',
        'renan-santos',
      ];
      const comparisonPairs = [
        'lula-vs-tarcisio',
        'lula-vs-caiado',
        'tarcisio-vs-caiado',
        'tarcisio-vs-ratinho-jr',
        'lula-vs-zema',
        'caiado-vs-ratinho-jr',
        'lula-vs-ratinho-jr',
        'tarcisio-vs-zema',
      ];
      return [
        ...paths,
        ...candidateSlugs.map((slug) => `/candidato/${slug}`),
        ...comparisonPairs.map((pair) => `/comparar/${pair}`),
      ];
    },
  },
});
