import { useTranslation } from 'react-i18next';

const DEFAULT_LANGUAGE = 'pt-BR';

function LanguageSwitcher() {
  const { i18n, t } = useTranslation('common');
  const activeLanguage = i18n.resolvedLanguage || i18n.language || DEFAULT_LANGUAGE;

  const setLanguage = (language) => {
    if (language === activeLanguage) {
      return;
    }
    void i18n.changeLanguage(language);
    if (typeof window !== 'undefined') {
      window.localStorage.setItem('lang', language);
    }
  };

  const ptActive = activeLanguage.startsWith('pt');
  const enActive = activeLanguage.startsWith('en');

  return (
    <div className="language-switcher" aria-label={t('language.switcher_aria')}>
      <button
        type="button"
        className={`lang-button ${ptActive ? 'active' : ''}`}
        onClick={() => setLanguage('pt-BR')}
      >
        {t('language.pt')}
      </button>
      <span aria-hidden="true">|</span>
      <button
        type="button"
        className={`lang-button ${enActive ? 'active' : ''}`}
        onClick={() => setLanguage('en-US')}
      >
        {t('language.en')}
      </button>
    </div>
  );
}

export default LanguageSwitcher;
