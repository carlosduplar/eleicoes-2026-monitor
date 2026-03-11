import { NavLink } from 'react-router-dom';
import { useTranslation } from 'react-i18next';

import LanguageSwitcher from './LanguageSwitcher';

const navItems = [
  { to: '/', key: 'noticias', end: true },
  { to: '/sentimento', key: 'sentimento' },
  { to: '/pesquisas', key: 'pesquisas' },
  { to: '/candidatos', key: 'candidatos' },
  { to: '/quiz', key: 'quiz' },
  { to: '/metodologia', key: 'metodologia' },
  { to: '/sobre/caso-de-uso', key: 'caso_de_uso' },
];

function Nav() {
  const { t } = useTranslation('common');

  return (
    <header className="top-nav">
      <div className="container top-nav-inner">
        <NavLink to="/" end className="top-nav-logo">
          {t('brand')}
        </NavLink>
        <nav className="top-nav-links" aria-label={t('nav.aria_label')}>
          {navItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) => (isActive ? 'top-link active' : 'top-link')}
            >
              {t(`nav.${item.key}`)}
            </NavLink>
          ))}
        </nav>
        <LanguageSwitcher />
      </div>
    </header>
  );
}

export default Nav;
