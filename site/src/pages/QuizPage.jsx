import { useTranslation } from 'react-i18next';

function QuizPage() {
  const { t } = useTranslation('common');

  return (
    <section className="placeholder-page">
      <h1>{t('nav.quiz')}</h1>
      <p>{t('placeholder.phase_11')}</p>
    </section>
  );
}

export default QuizPage;
