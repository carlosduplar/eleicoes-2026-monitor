import { useEffect, useMemo, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import * as ReactHelmetAsync from 'react-helmet-async';
import { useTranslation } from 'react-i18next';

import QuizResultCard from '../components/QuizResultCard';
import { useData } from '../hooks/useData';
import { calculateAffinity } from '../utils/affinity';
import { decodeResult } from '../utils/shareUrl';

const Helmet = ReactHelmetAsync.Helmet || ReactHelmetAsync.default?.Helmet;

function QuizResult() {
  const { t, i18n } = useTranslation('common');
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const { data: quizData, loading, error } = useData('quiz');
  const [decodedAnswers, setDecodedAnswers] = useState(null);

  useEffect(() => {
    const encoded = searchParams.get('r');
    if (!encoded) {
      navigate('/quiz', { replace: true });
      return;
    }

    try {
      const parsed = decodeResult(encoded);
      if (!parsed || typeof parsed !== 'object') {
        throw new Error('Invalid payload');
      }
      setDecodedAnswers(parsed);
    } catch {
      navigate('/quiz', { replace: true });
    }
  }, [navigate, searchParams]);

  const results = useMemo(() => {
    if (!decodedAnswers || !quizData) {
      return [];
    }
    return calculateAffinity(decodedAnswers, quizData);
  }, [decodedAnswers, quizData]);

  const language = i18n.language === 'en-US' ? 'en-US' : 'pt-BR';
  const quizJsonLd = {
    '@context': 'https://schema.org',
    '@type': 'Quiz',
    name: t('quiz.result_title'),
    inLanguage: language,
    url: '/quiz/resultado',
  };

  if (loading || !decodedAnswers) {
    return <p>{t('quiz.loading')}</p>;
  }

  if (error || !quizData) {
    return <p className="error-state">{t('quiz.error')}</p>;
  }

  return (
    <>
      <Helmet>
        <title>{`${t('quiz.result_title')} | ${t('brand')}`}</title>
        <meta name="description" content={t('quiz.result_title')} />
        <script type="application/ld+json">{JSON.stringify(quizJsonLd)}</script>
      </Helmet>
      <QuizResultCard
        answers={decodedAnswers}
        onRestart={() => navigate('/quiz')}
        quizData={quizData}
        results={results}
      />
    </>
  );
}

export default QuizResult;
