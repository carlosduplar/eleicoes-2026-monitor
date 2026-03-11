import * as ReactHelmetAsync from 'react-helmet-async';
import { Outlet } from 'react-router-dom';
import { useTranslation } from 'react-i18next';

import CountdownTimer from './components/CountdownTimer';
import Nav from './components/Nav';
import CandidatePage from './pages/CandidatePage';
import CandidatesPage from './pages/CandidatesPage';
import ComparisonPage from './pages/ComparisonPage';
import Home from './pages/Home';
import MethodologyPage from './pages/MethodologyPage';
import PollsPage from './pages/PollsPage';
import QuizPage from './pages/QuizPage';
import QuizResult from './pages/QuizResult';
import SentimentPage from './pages/SentimentPage';

const Helmet = ReactHelmetAsync.Helmet || ReactHelmetAsync.default?.Helmet;

function AppShell() {
  const { t } = useTranslation('common');

  return (
    <div className="app-shell">
      <Helmet>
        <title>{t('brand')}</title>
        <meta name="description" content={t('meta.description')} />
      </Helmet>
      <Nav />
      <CountdownTimer />
      <main className="container app-main">
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
              <li>{t('nav.noticias')}</li>
              <li>{t('nav.sentimento')}</li>
              <li>{t('nav.pesquisas')}</li>
              <li>{t('nav.quiz')}</li>
            </ul>
          </div>
          <div>
            <h3>{t('footer.transparency_title')}</h3>
            <ul>
              <li>{t('nav.metodologia')}</li>
              <li>{t('footer.transparency_open_source')}</li>
              <li>{t('footer.transparency_disclaimer')}</li>
            </ul>
          </div>
        </div>
        <div className="container footer-bottom">{t('footer.copyright')}</div>
      </footer>
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
    ],
  },
];
