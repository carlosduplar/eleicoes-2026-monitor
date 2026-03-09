import { useTranslation } from 'react-i18next';

function MethodologyPage() {
  const { t } = useTranslation('common');

  return (
    <section className="placeholder-page">
      <h1>{t('nav.metodologia')}</h1>
      <p>{t('placeholder.phase_10')}</p>
    </section>
  );
}

export default MethodologyPage;
