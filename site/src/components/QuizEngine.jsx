import { useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';

function QuizEngine({ topic, topicId, currentIndex, totalTopics, onAnswer }) {
  const { t, i18n } = useTranslation('common');
  const [selectedOptionId, setSelectedOptionId] = useState(null);
  const language = i18n.language === 'en-US' ? 'en-US' : 'pt-BR';

  const safeOptions = useMemo(() => {
    if (!Array.isArray(topic?.options)) {
      return [];
    }
    return topic.options
      .map((option) => {
        if (!option || typeof option !== 'object') {
          return null;
        }
        const { id, text_pt: textPt, text_en: textEn, weight } = option;
        if (typeof id !== 'string' || typeof textPt !== 'string' || typeof textEn !== 'string' || typeof weight !== 'number') {
          return null;
        }
        return { id, textPt, textEn, weight };
      })
      .filter((option) => option !== null);
  }, [topic]);

  const questionText = language === 'en-US' ? topic?.question_en : topic?.question_pt;
  const isLastQuestion = currentIndex + 1 >= totalTopics;
  const progress = totalTopics > 0 ? ((currentIndex + 1) / totalTopics) * 100 : 0;

  const selectedOption = safeOptions.find((option) => option.id === selectedOptionId) || null;

  const handleNext = () => {
    if (!selectedOption) {
      return;
    }
    onAnswer(topicId, selectedOption.id, selectedOption.weight);
    setSelectedOptionId(null);
  };

  return (
    <section>
      <div className="quiz-progress">
        <div className="quiz-progress-bar" style={{ width: `${progress}%` }} />
      </div>
      <p className="quiz-counter">{t('quiz.question_of', { current: currentIndex + 1, total: totalTopics })}</p>
      <h2 className="quiz-question">{questionText}</h2>
      <div className="quiz-options">
        {safeOptions.map((option) => (
          <button
            className={`quiz-option-card ${selectedOptionId === option.id ? 'quiz-option-card--selected' : ''}`}
            key={option.id}
            onClick={() => setSelectedOptionId(option.id)}
            type="button"
          >
            {language === 'en-US' ? option.textEn : option.textPt}
          </button>
        ))}
      </div>
      <button className="quiz-next-btn" disabled={!selectedOptionId} onClick={handleNext} type="button">
        {isLastQuestion ? t('quiz.see_result') : t('quiz.next')}
      </button>
    </section>
  );
}

export default QuizEngine;
