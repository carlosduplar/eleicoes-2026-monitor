import { NavLink } from 'react-router-dom';
import { useTranslation } from 'react-i18next';

function IconHome() {
  return (
    <svg aria-hidden="true" fill="none" height="24" stroke="currentColor" viewBox="0 0 24 24" width="24">
      <path d="M3 10.5 12 3l9 7.5" strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" />
      <path d="M6 9.5V21h12V9.5" strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" />
    </svg>
  );
}

function IconSentiment() {
  return (
    <svg aria-hidden="true" fill="none" height="24" stroke="currentColor" viewBox="0 0 24 24" width="24">
      <path d="M5 20V12M12 20V8M19 20V4" strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" />
    </svg>
  );
}

function IconPolls() {
  return (
    <svg aria-hidden="true" fill="none" height="24" stroke="currentColor" viewBox="0 0 24 24" width="24">
      <path d="M4 7h12M4 12h16M4 17h9" strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" />
    </svg>
  );
}

function IconQuiz() {
  return (
    <svg aria-hidden="true" fill="none" height="24" stroke="currentColor" viewBox="0 0 24 24" width="24">
      <path
        d="M6 4h12a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2h-8l-4 4v-4H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2Z"
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth="1.8"
      />
      <path d="M10 9a2 2 0 1 1 3.5 1.3c-.9.8-1.5 1.3-1.5 2.2" strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" />
      <circle cx="12" cy="15.5" fill="currentColor" r="1" stroke="none" />
    </svg>
  );
}

function IconCandidates() {
  return (
    <svg aria-hidden="true" fill="none" height="24" stroke="currentColor" viewBox="0 0 24 24" width="24">
      <circle cx="9" cy="8" r="3" strokeWidth="1.8" />
      <path d="M4.5 19a4.5 4.5 0 0 1 9 0" strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" />
      <circle cx="17" cy="9" r="2.5" strokeWidth="1.8" />
      <path d="M14.5 19a3.5 3.5 0 0 1 7 0" strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" />
    </svg>
  );
}

/** @type {Array<{ to: string, key: string, Icon: () => JSX.Element, end?: boolean }>} */
const bottomNavItems = [
  { to: '/', key: 'noticias', Icon: IconHome, end: true },
  { to: '/sentimento', key: 'sentimento', Icon: IconSentiment },
  { to: '/pesquisas', key: 'pesquisas', Icon: IconPolls },
  { to: '/quiz', key: 'quiz', Icon: IconQuiz },
  { to: '/candidatos', key: 'candidatos', Icon: IconCandidates },
];

function BottomNav() {
  const { t } = useTranslation('common');

  return (
    <nav aria-label={t('nav.aria_label')} className="bottom-nav">
      {bottomNavItems.map((item) => (
        <NavLink
          key={item.to}
          to={item.to}
          end={item.end}
          className={({ isActive }) => `bottom-nav-item ${isActive ? 'bottom-nav-item--active' : ''}`}
        >
          <item.Icon />
          <span className="bottom-nav-label">{t(`bottom_nav.${item.key}`)}</span>
        </NavLink>
      ))}
    </nav>
  );
}

export default BottomNav;
