import * as ReactHelmetAsync from 'react-helmet-async';
import { useTranslation } from 'react-i18next';

import QuizEngine from '../components/QuizEngine';
import QuizResultCard from '../components/QuizResultCard';
import { useQuiz } from '../hooks/useQuiz';

const Helmet = ReactHelmetAsync.Helmet || ReactHelmetAsync.default?.Helmet;

function QuizPage() {
  const { t, i18n } = useTranslation('common');
  const {
    quizData,
    loading,
    error,
    answers,
    currentTopicIndex,
    isComplete,
    results,
    currentTopic,
    orderedTopics,
    totalTopics,
    handleAnswer,
    reset,
  } = useQuiz();

  const language = i18n.language === 'en-US' ? 'en-US' : 'pt-BR';
  const quizJsonLd = {
    '@context': 'https://schema.org',
    '@type': 'Quiz',
    name: t('quiz.title'),
    inLanguage: language,
    url: '/quiz',
  };

  if (loading) {
    return <p>{t('quiz.loading')}</p>;
  }

  if (error) {
    return <p className="error-state">{t('quiz.error')}</p>;
  }

  if (!quizData || !Array.isArray(orderedTopics) || orderedTopics.length === 0) {
    return <p>{t('quiz.empty')}</p>;
  }

  const currentTopicId = orderedTopics[currentTopicIndex];
  const topicForEngine =
    currentTopic && Array.isArray(currentTopic.options)
      ? {
          question_pt: currentTopic.question_pt,
          question_en: currentTopic.question_en,
          options: currentTopic.options
            .map((option) => {
              if (!option || typeof option !== 'object') {
                return null;
              }
              const { id, text_pt: textPt, text_en: textEn, weight } = option;
              if (typeof id !== 'string' || typeof textPt !== 'string' || typeof textEn !== 'string' || typeof weight !== 'number') {
                return null;
              }
              return { id, text_pt: textPt, text_en: textEn, weight };
            })
            .filter((option) => option !== null),
        }
      : null;

  return (
    <>
      <Helmet>
        <title>{`${t('quiz.title')} | ${t('brand')}`}</title>
        <meta name="description" content={t('quiz.title')} />
        <script type="application/ld+json">{JSON.stringify(quizJsonLd)}</script>
      </Helmet>
      {isComplete ? (
        <QuizResultCard
          answers={answers}
          onRestart={reset}
          quizData={quizData}
          results={Array.isArray(results) ? results : []}
        />
      ) : (
        <QuizEngine
          currentIndex={currentTopicIndex}
          onAnswer={handleAnswer}
          topic={topicForEngine}
          topicId={currentTopicId}
          totalTopics={totalTopics}
        />
      )}
    </>
  );
}

export default QuizPage;
