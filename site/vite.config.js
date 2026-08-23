import path from 'node:path';
import fs from 'node:fs';
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

const projectRoot = __dirname;
const repoRoot = path.resolve(projectRoot, '..');
const dataDirectory = path.resolve(repoRoot, 'data').replace(/\\/g, '/');
const basePath = '/eleicoes-2026-monitor/';

function buildBootData() {
  const dataDir = path.join(projectRoot, 'public', 'data');
  const readJson = (filename) => {
    try {
      return JSON.parse(fs.readFileSync(path.join(dataDir, `${filename}.json`), 'utf8'));
    } catch {
      return null;
    }
  };

  const boot = {};
  for (const filename of ['polls', 'candidates', 'sentiment', 'markets', 'quiz']) {
    boot[filename] = readJson(filename);
  }
  const articles = readJson('articles');
  const articlesList = Array.isArray(articles)
    ? articles
    : Array.isArray(articles?.articles)
      ? articles.articles
      : [];
  if (articlesList.length > 0) {
    boot.articles = {
      articles: articlesList
        .filter((article) => article && typeof article === 'object' && article.status !== 'irrelevant')
        .slice(0, 20),
      last_updated: (articles && typeof articles === 'object' && articles.last_updated) || null,
    };
  }
  return boot;
}

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
      onPageRendered: (_routePath, html) => {
        const boot = buildBootData();
        if (!boot || Object.keys(boot).length === 0) {
          return html;
        }
        const json = JSON.stringify(boot).replace(/</g, '\\u003c').replace(/\u2028/g, '\\u2028').replace(/\u2029/g, '\\u2029');
        const script = `<script>window.__BOOT_DATA__=${json}</script>`;
        return html.includes('</body>') ? html.replace('</body>', `${script}</body>`) : html + script;
      },
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
