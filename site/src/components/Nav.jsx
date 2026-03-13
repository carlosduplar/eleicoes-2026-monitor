import { useCallback, useEffect, useState } from 'react';
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

function HamburgerIcon({ isOpen }) {
  return (
    <svg aria-hidden="true" fill="none" height="24" stroke="currentColor" viewBox="0 0 24 24" width="24">
      {isOpen ? (
        <path d="M6 6l12 12M6 18L18 6" strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" />
      ) : (
        <>
          <path d="M4 6h16" strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" />
          <path d="M4 12h16" strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" />
          <path d="M4 18h16" strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" />
        </>
      )}
    </svg>
  );
}

function Nav() {
  const { t } = useTranslation('common');
  const [isOpen, setIsOpen] = useState(false);
  const closeMenu = useCallback(() => setIsOpen(false), []);

  useEffect(() => {
    if (!isOpen) return;
    function onKey(e) {
      if (e.key === 'Escape') closeMenu();
    }
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [isOpen, closeMenu]);

  return (
    <>
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
          <button
            type="button"
            className="hamburger-btn"
            aria-expanded={isOpen}
            aria-controls="nav-drawer"
            aria-label={isOpen ? t('nav.close_menu') : t('nav.open_menu')}
            onClick={() => setIsOpen((prev) => !prev)}
          >
            <HamburgerIcon isOpen={isOpen} />
          </button>
        </div>
      </header>
      <div id="nav-drawer" className={`nav-drawer${isOpen ? ' is-open' : ''}`} aria-hidden={!isOpen}>
        <nav className="container" aria-label={t('nav.aria_label')}>
          {navItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) => `nav-drawer-link${isActive ? ' active' : ''}`}
              onClick={closeMenu}
            >
              {t(`nav.${item.key}`)}
            </NavLink>
          ))}
        </nav>
      </div>
      {isOpen && (
        <div
          className="nav-drawer-overlay"
          onClick={closeMenu}
          role="presentation"
          aria-hidden="true"
        />
      )}
    </>
  );
}

export default Nav;
