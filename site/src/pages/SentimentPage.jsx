import { useTranslation } from 'react-i18next';

function SentimentPage() {
  const { t } = useTranslation('common');

  return (
    <section className="placeholder-page">
      <h1>{t('nav.sentimento')}</h1>
      <p>{t('placeholder.phase_7')}</p>
    </section>
  );
}

export default SentimentPage;
