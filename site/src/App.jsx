import * as ReactHelmetAsync from 'react-helmet-async';
import { Link, Outlet, useLocation } from 'react-router-dom';
import { useTranslation } from 'react-i18next';

import BottomNav from './components/BottomNav';
import CountdownTimer from './components/CountdownTimer';
import Nav from './components/Nav';
import CandidatePage from './pages/CandidatePage';
import CandidatesPage from './pages/CandidatesPage';
import ComparisonPage from './pages/ComparisonPage';
import CaseStudyPage from './pages/CaseStudyPage';
import FinanciamentoPage from './pages/FinanciamentoPage';
import Home from './pages/Home';
import MethodologyPage from './pages/MethodologyPage';
import PollsPage from './pages/PollsPage';
import QuizPage from './pages/QuizPage';
import QuizResult from './pages/QuizResult';
import SentimentPage from './pages/SentimentPage';

const Helmet = ReactHelmetAsync.Helmet || ReactHelmetAsync.default?.Helmet;
const CANONICAL_BASE_URL = 'https://eleicoes2026.com.br';

function toMetaLabelFromSlug(value) {
  if (!value) {
    return '';
  }
  return value
    .split('-')
    .filter(Boolean)
    .map((part) => `${part.slice(0, 1).toUpperCase()}${part.slice(1)}`)
    .join(' ');
}

function AppShell() {
  const { t } = useTranslation('common');
  const { pathname } = useLocation();

  // Strip basename if present in pathname (some environments/routers differ in this)
  const basename = import.meta.env.BASE_URL.replace(/\/+$/, '');
  const pathWithoutBasename = pathname.startsWith(basename)
    ? pathname.slice(basename.length)
    : pathname;

  // Ensure leading slash and no trailing slash
  const normalizedPath = pathWithoutBasename.startsWith('/')
    ? pathWithoutBasename.replace(/\/+$/, '') || '/'
    : `/${pathWithoutBasename}`.replace(/\/+$/, '') || '/';

  const pathLabels = {
    '/': t('home.feed_title'),
    '/sentimento': t('sentiment.title'),
    '/pesquisas': t('polls.title'),
    '/quiz': t('quiz.title'),
    '/quiz/resultado': t('quiz.result_title'),
    '/metodologia': t('nav.metodologia'),
    '/candidatos': t('nav.candidatos'),
    '/sobre/caso-de-uso': t('nav.caso_de_uso'),
    '/financiamento': t('financiamento.title'),
  };

  let routeLabel = pathLabels[normalizedPath] || '';
  if (!routeLabel && normalizedPath.startsWith('/candidato/')) {
    routeLabel = `${t('nav.candidatos')} - ${toMetaLabelFromSlug(normalizedPath.split('/')[2] || '')}`;
  }
  if (!routeLabel && normalizedPath.startsWith('/comparar/')) {
    const pairSlug = normalizedPath.split('/')[2] || '';
    routeLabel = `${t('nav.candidatos')} - ${toMetaLabelFromSlug(pairSlug.replace('-vs-', '-'))}`;
  }
  if (!routeLabel) {
    routeLabel = t('brand');
  }

  const title = routeLabel === t('brand') ? t('brand') : `${routeLabel} | ${t('brand')}`;
  const description = routeLabel === t('brand') ? t('meta.description') : `${routeLabel} - ${t('meta.description')}`;
  const canonicalPath = normalizedPath === '/' ? '' : normalizedPath;
  const canonicalUrl = `${CANONICAL_BASE_URL}${canonicalPath}`;

  return (
    <div className="app-shell">
      <Helmet>
        <title>{title}</title>
        <meta name="description" content={description} />
        <link rel="canonical" href={canonicalUrl} />
        <meta property="og:title" content={title} />
        <meta property="og:description" content={description} />
      </Helmet>
      <a className="skip-link" href="#main-content">
        {t('a11y.skip_to_content')}
      </a>
      <Nav />
      <CountdownTimer />
      <main id="main-content" className="container app-main main-content">
        <Outlet />
      </main>
      <footer className="site-footer">
        <div className="container footer-grid">
          <div>
            <h3>{t('footer.about_title')}</h3>
            <p>{t('footer.about_body')}</p>
          </div>
          <div>
            <h3>{t('footer.nav_title')}</h3>
            <ul>
              <li>
                <Link to="/">{t('nav.noticias')}</Link>
              </li>
              <li>
                <Link to="/sentimento">{t('nav.sentimento')}</Link>
              </li>
              <li>
                <Link to="/pesquisas">{t('nav.pesquisas')}</Link>
              </li>
              <li>
                <Link to="/quiz">{t('nav.quiz')}</Link>
              </li>
              <li>
                <Link to="/financiamento">{t('nav.financiamento')}</Link>
              </li>
            </ul>
          </div>
          <div>
            <h3>{t('footer.transparency_title')}</h3>
            <ul>
              <li>
                <Link to="/metodologia">{t('nav.metodologia')}</Link>
              </li>
              <li>
                <a href="https://github.com/carlosduplar/eleicoes-2026-monitor" target="_blank" rel="noopener noreferrer">
                  {t('footer.transparency_open_source')}
                </a>
              </li>
              <li>
                <Link to="/sobre/caso-de-uso">{t('footer.transparency_disclaimer')}</Link>
              </li>
            </ul>
          </div>
        </div>
        <div className="container footer-bottom">{t('footer.copyright')}</div>
      </footer>
      <BottomNav />
    </div>
  );
}

export const routes = [
  {
    path: '/',
    element: <AppShell />,
    children: [
      { index: true, element: <Home /> },
      { path: 'sentimento', element: <SentimentPage /> },
      { path: 'pesquisas', element: <PollsPage /> },
      { path: 'candidatos', element: <CandidatesPage /> },
      { path: 'candidato/:slug', element: <CandidatePage /> },
      { path: 'comparar/:pairSlug', element: <ComparisonPage /> },
      { path: 'quiz/resultado', element: <QuizResult /> },
      { path: 'quiz', element: <QuizPage /> },
      { path: 'metodologia', element: <MethodologyPage /> },
      { path: 'sobre/caso-de-uso', element: <CaseStudyPage /> },
      { path: 'financiamento', element: <FinanciamentoPage /> },
    ],
  },
];
