import { useTranslation } from 'react-i18next';

function CandidatesPage() {
  const { t } = useTranslation('common');

  return (
    <section className="placeholder-page">
      <h1>{t('nav.candidatos')}</h1>
      <p>{t('placeholder.phase_12')}</p>
    </section>
  );
}

export default CandidatesPage;
