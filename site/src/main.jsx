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
import './styles.css';

const HelmetProvider = ReactHelmetAsync.HelmetProvider || ReactHelmetAsync.default?.HelmetProvider;

const DEFAULT_LANGUAGE = 'pt-BR';
const SUPPORTED_LANGUAGES = ['pt-BR', 'en-US'];

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
);
