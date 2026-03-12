import path from 'node:path';
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

const projectRoot = __dirname;
const repoRoot = path.resolve(projectRoot, '..');
const dataDirectory = path.resolve(repoRoot, 'data').replace(/\\/g, '/');
const basePath = '/eleicoes-2026-monitor/';

export default defineConfig(({ command }) => {
  const isDev = command === 'serve';

  return {
    base: basePath,
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
      proxy: isDev ? {
        '/data': {
          target: 'http://localhost:5173',
          changeOrigin: true,
          rewrite: (requestPath) => requestPath.replace(/^\/data/, `/@fs/${dataDirectory}`),
        },
      } : undefined,
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
          '/sobre/caso-de-uso',
        ];
      },
    },
  };
});
