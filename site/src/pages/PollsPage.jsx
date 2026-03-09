import { useTranslation } from 'react-i18next';

function PollsPage() {
  const { t } = useTranslation('common');

  return (
    <section className="placeholder-page">
      <h1>{t('nav.pesquisas')}</h1>
      <p>{t('placeholder.phase_8')}</p>
    </section>
  );
}

export default PollsPage;
