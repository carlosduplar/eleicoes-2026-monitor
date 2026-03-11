import { useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import { RadarChart, PolarGrid, PolarAngleAxis, Radar, ResponsiveContainer } from 'recharts';

import { CANDIDATE_COLORS } from '../utils/candidateColors';

import MethodologyBadge from './MethodologyBadge';
import ShareButton from './ShareButton';

function formatCandidateName(slug) {
  if (typeof slug !== 'string') {
    return '';
  }
  return slug
    .split(/[-_]/g)
    .map((part) => {
      if (!part) {
        return part;
      }
      if (part.toLowerCase() === 'jr') {
        return 'Jr';
      }
      return `${part[0].toUpperCase()}${part.slice(1)}`;
    })
    .join(' ');
}

function topicLabel(topicId) {
  if (typeof topicId !== 'string') {
    return '';
  }
  return topicId
    .split('_')
    .map((part) => (part ? `${part[0].toUpperCase()}${part.slice(1)}` : part))
    .join(' ');
}

function QuizResultCard({ results, answers, quizData, onRestart }) {
  const { t, i18n } = useTranslation('common');
  const language = i18n.language === 'en-US' ? 'en-US' : 'pt-BR';
  const ranking = Array.isArray(results) ? results : [];
  const topResults = ranking.slice(0, 3);
  const orderedTopics = Array.isArray(quizData?.ordered_topics) ? quizData.ordered_topics : [];

  const answeredTopicIds = useMemo(
    () => orderedTopics.filter((topicId) => answers?.[topicId]),
    [answers, orderedTopics],
  );

  const radarData = useMemo(
    () =>
      answeredTopicIds.map((topicId) => {
        const row = { topic: topicLabel(topicId) };
        topResults.forEach((result) => {
          row[result.slug] = result.byTopic?.[topicId] ?? 0;
        });
        return row;
      }),
    [answeredTopicIds, topResults],
  );

  if (ranking.length === 0) {
    return (
      <section className="quiz-sources">
        <h2>{t('quiz.result_title')}</h2>
        <p>{t('quiz.empty')}</p>
        <button className="quiz-restart-btn" onClick={onRestart} type="button">
          {t('quiz.restart')}
        </button>
      </section>
    );
  }

  return (
    <section>
      <h2>{t('quiz.result_title')}</h2>

      <div className="quiz-ranking">
        {ranking.map((result) => (
          <div className="quiz-ranking-item" key={result.slug}>
            <div className="quiz-ranking-row">
              <span>{formatCandidateName(result.slug)}</span>
              <span>{Math.round(result.affinity)}%</span>
            </div>
            <progress
              max={100}
              value={Math.max(0, Math.min(100, result.affinity))}
              style={{ accentColor: CANDIDATE_COLORS[result.slug] || '#4A5568' }}
            />
            <span>{t('quiz.affinity_label')}</span>
          </div>
        ))}
      </div>

      <div className="quiz-radar">
        <ResponsiveContainer height={350} width="100%">
          <RadarChart data={radarData}>
            <PolarGrid />
            <PolarAngleAxis dataKey="topic" />
            {topResults.map((result) => (
              <Radar
                dataKey={result.slug}
                fill={CANDIDATE_COLORS[result.slug] || '#4A5568'}
                fillOpacity={0.15}
                key={result.slug}
                name={formatCandidateName(result.slug)}
                stroke={CANDIDATE_COLORS[result.slug] || '#4A5568'}
              />
            ))}
          </RadarChart>
        </ResponsiveContainer>
        <MethodologyBadge />
      </div>

      <div className="quiz-sources">
        <h3>{t('quiz.source_reveal_heading')}</h3>
        {answeredTopicIds.map((topicId) => {
          const topic = quizData?.topics?.[topicId];
          if (!topic || !Array.isArray(topic.options)) {
            return null;
          }

          const selected = answers?.[topicId];
          if (!selected || typeof selected.optionId !== 'string') {
            return null;
          }

          const selectedOption = topic.options.find((option) => option?.id === selected.optionId);
          if (!selectedOption) {
            return null;
          }

          const question = language === 'en-US' ? topic.question_en : topic.question_pt;
          const answerText = language === 'en-US' ? selectedOption.text_en : selectedOption.text_pt;
          const sourceText =
            language === 'en-US'
              ? selectedOption.source_en || selectedOption.source_pt
              : selectedOption.source_pt || selectedOption.source_en;

          return (
            <article className="quiz-source-item" key={topicId}>
              <p>
                <strong>{question}</strong>
              </p>
              <p>{answerText}</p>
              <p>{formatCandidateName(selectedOption.candidate_slug)}</p>
              {sourceText ? <p>{sourceText}</p> : null}
            </article>
          );
        })}
      </div>

      <ShareButton answers={answers} />
      <button className="quiz-restart-btn" onClick={onRestart} type="button">
        {t('quiz.restart')}
      </button>
    </section>
  );
}

export default QuizResultCard;
