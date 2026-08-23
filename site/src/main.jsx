import * as ReactHelmetAsync from 'react-helmet-async';
import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';
import { ViteReactSSG } from 'vite-react-ssg';

import { routes } from './App';
import enCandidates from './locales/en-US/candidates.json';
import enCaseStudy from './locales/en-US/case-study.json';
import enCommon from './locales/en-US/common.json';
import enMethodology from './locales/en-US/methodology.json';
import ptCandidates from './locales/pt-BR/candidates.json';
import ptCaseStudy from './locales/pt-BR/case-study.json';
import ptCommon from './locales/pt-BR/common.json';
import ptMethodology from './locales/pt-BR/methodology.json';
import { setBootData } from './utils/bootData';
import './styles.css';

const HelmetProvider = ReactHelmetAsync.HelmetProvider || ReactHelmetAsync.default?.HelmetProvider;

const DEFAULT_LANGUAGE = 'pt-BR';
const SUPPORTED_LANGUAGES = ['pt-BR', 'en-US'];

const ARTICLES_BOOT_LIMIT = 20;
const BOOT_DATA_FILES = ['polls', 'candidates', 'sentiment', 'markets', 'quiz'];

async function loadServerBootData() {
  const [{ readFileSync }, { join }] = await Promise.all([
    import('node:fs'),
    import('node:path'),
  ]);
  const dataDir = join(process.cwd(), 'public', 'data');
  const readJson = (filename) => {
    try {
      return JSON.parse(readFileSync(join(dataDir, `${filename}.json`), 'utf8'));
    } catch {
      return null;
    }
  };

  const boot = {};
  for (const filename of BOOT_DATA_FILES) {
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
        .slice(0, ARTICLES_BOOT_LIMIT),
      last_updated: (articles && typeof articles === 'object' && articles.last_updated) || null,
    };
  }
  return boot;
}

if (!i18n.isInitialized) {
  i18n.use(initReactI18next).init({
    resources: {
      'pt-BR': {
        common: ptCommon,
        methodology: ptMethodology,
        candidates: ptCandidates,
        'case-study': ptCaseStudy,
      },
      'en-US': {
        common: enCommon,
        methodology: enMethodology,
        candidates: enCandidates,
        'case-study': enCaseStudy,
      },
    },
    lng: DEFAULT_LANGUAGE,
    fallbackLng: 'pt-BR',
    interpolation: { escapeValue: false },
    defaultNS: 'common',
    ns: ['common', 'methodology', 'candidates', 'case-study'],
    supportedLngs: SUPPORTED_LANGUAGES,
    react: {
      useSuspense: false,
    },
  });
}

const routesWithProviders = routes.map((route, index) => {
  if (index !== 0) {
    return route;
  }
  return {
    ...route,
    element: <HelmetProvider>{route.element}</HelmetProvider>,
  };
});

export const createRoot = ViteReactSSG(
  {
    routes: routesWithProviders,
    basename: import.meta.env.BASE_URL.replace(/\/+$/, '') || '/',
  },
  async ({ isClient }) => {
    if (isClient) {
      setBootData(window.__BOOT_DATA__ || null);
      return;
    }
    setBootData(await loadServerBootData());
  },
);
