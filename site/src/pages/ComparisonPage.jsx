import * as ReactHelmetAsync from 'react-helmet-async';
import { useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, useParams } from 'react-router-dom';

import MethodologyBadge from '@/components/MethodologyBadge';
import { useData } from '@/hooks/useData';
import { CANDIDATE_COLORS } from '@/utils/candidateColors';

const Helmet = ReactHelmetAsync.Helmet || ReactHelmetAsync.default?.Helmet;
const BASE_URL = 'https://eleicoes2026.com.br';

function StructuredDataScript({ payload }) {
  return <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(payload) }} />;
}

function normalizeCandidates(payload) {
  if (Array.isArray(payload)) {
    return payload;
  }
  if (payload && Array.isArray(payload.candidates)) {
    return payload.candidates;
  }
  return [];
}

function normalizeQuiz(payload) {
  if (!payload || typeof payload !== 'object') {
    return null;
  }
  if (!Array.isArray(payload.ordered_topics) || typeof payload.topics !== 'object' || payload.topics === null) {
    return null;
  }
  return payload;
}

function toTopicLabel(topicId) {
  if (typeof topicId !== 'string') {
    return '';
  }
  return topicId
    .split('_')
    .map((part) => (part ? `${part[0].toUpperCase()}${part.slice(1)}` : part))
    .join(' ');
}

function toInitials(name) {
  if (typeof name !== 'string' || name.length === 0) {
    return '?';
  }
  return name
    .split(' ')
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() || '')
    .join('');
}

function toCandidateDisplayName(slug) {
  if (typeof slug !== 'string') {
    return '';
  }
  return slug
    .split('-')
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

function parseComparisonSlugs(pairSlug) {
  if (typeof pairSlug !== 'string') {
    return null;
  }
  const separator = '-vs-';
  const separatorIndex = pairSlug.indexOf(separator);
  if (separatorIndex <= 0) {
    return null;
  }
  const slugA = pairSlug.slice(0, separatorIndex);
  const slugB = pairSlug.slice(separatorIndex + separator.length);
  if (!slugA || !slugB) {
    return null;
  }
  return [slugA, slugB];
}

function getTopicStance(topic, candidateSlug, language) {
  if (!topic || !Array.isArray(topic.options)) {
    return null;
  }
  const option = topic.options.find((entry) => entry?.candidate_slug === candidateSlug);
  if (!option) {
    return null;
  }
  const text = language === 'en-US' ? option.text_en || option.text_pt : option.text_pt || option.text_en;
  const source = language === 'en-US' ? option.source_en || option.source_pt : option.source_pt || option.source_en;
  return { text, source };
}

function ComparisonHero({ candidateA, candidateB }) {
  return (
    <div className="comparison-hero-grid">
      {[candidateA, candidateB].map((candidate) => (
        <article className="comparison-hero-card" key={candidate.slug} style={{ borderTopColor: candidate.color }}>
          <div className="comparison-avatar" style={{ backgroundColor: candidate.color || CANDIDATE_COLORS[candidate.slug] }}>
            {toInitials(candidate.name)}
          </div>
          <div>
            <h2>{candidate.full_name}</h2>
            <p>{candidate.party}</p>
          </div>
        </article>
      ))}
    </div>
  );
}

function TopicAccordion({ topicId, topic, candidateA, candidateB, options, t }) {
  const topicLabel = toTopicLabel(topicId);

  return (
    <details className="comparison-topic-details">
      <summary>{topicLabel}</summary>
      <div className="comparison-topic-columns">
        <article>
          <h4 style={{ color: candidateA.color || CANDIDATE_COLORS[candidateA.slug] }}>{candidateA.name}</h4>
          <p>{options.a?.text || t('no_position')}</p>
          {options.a?.source ? (
            <p className="candidate-muted">
              {t('source_label')}: {options.a.source}
            </p>
          ) : null}
        </article>
        <article>
          <h4 style={{ color: candidateB.color || CANDIDATE_COLORS[candidateB.slug] }}>{candidateB.name}</h4>
          <p>{options.b?.text || t('no_position')}</p>
          {options.b?.source ? (
            <p className="candidate-muted">
              {t('source_label')}: {options.b.source}
            </p>
          ) : null}
        </article>
      </div>
      {topic?.question_pt || topic?.question_en ? (
        <p className="candidate-muted">{topic.question_pt || topic.question_en}</p>
      ) : null}
    </details>
  );
}

function TopicComparisonTable({ candidateA, candidateB, quizData, lang, t }) {
  const rows = useMemo(
    () =>
      quizData.ordered_topics
        .map((topicId) => {
          const topic = quizData.topics?.[topicId];
          if (!topic) {
            return null;
          }
          const stanceA = getTopicStance(topic, candidateA.slug, lang);
          const stanceB = getTopicStance(topic, candidateB.slug, lang);
          return {
            topicId,
            topic,
            stanceA,
            stanceB,
          };
        })
        .filter((row) => row !== null),
    [candidateA.slug, candidateB.slug, lang, quizData],
  );

  return (
    <>
      <section className="candidate-card comparison-table-card">
        <h3>{t('comparison_positions')}</h3>
        <div className="comparison-table-wrap">
          <table className="comparison-table">
            <thead>
              <tr>
                <th>{t('comparison_topic_header')}</th>
                <th style={{ color: candidateA.color || CANDIDATE_COLORS[candidateA.slug] }}>{candidateA.name}</th>
                <th style={{ color: candidateB.color || CANDIDATE_COLORS[candidateB.slug] }}>{candidateB.name}</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.topicId}>
                  <td>{toTopicLabel(row.topicId)}</td>
                  <td>{row.stanceA?.text || t('no_position')}</td>
                  <td>{row.stanceB?.text || t('no_position')}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="candidate-card comparison-details-card">
        <h3>{t('comparison_details')}</h3>
        {rows.map((row) => (
          <TopicAccordion
            key={`details-${row.topicId}`}
            topicId={row.topicId}
            topic={row.topic}
            candidateA={candidateA}
            candidateB={candidateB}
            options={{ a: row.stanceA, b: row.stanceB }}
            t={t}
          />
        ))}
      </section>
    </>
  );
}

export default function ComparisonPage() {
  const { pairSlug } = useParams();
  const { t, i18n } = useTranslation(['candidates', 'common']);
  const { data: candidatesData, loading: loadingCandidates, error: errorCandidates } = useData('candidates');
  const { data: quizDataRaw, loading: loadingQuiz, error: errorQuiz } = useData('quiz');
  const language = i18n.language === 'en-US' ? 'en-US' : 'pt-BR';

  const candidates = useMemo(() => normalizeCandidates(candidatesData), [candidatesData]);
  const quizData = useMemo(() => normalizeQuiz(quizDataRaw), [quizDataRaw]);
  const parsedSlugs = useMemo(() => parseComparisonSlugs(pairSlug), [pairSlug]);
  const candidateA = useMemo(
    () => candidates.find((entry) => entry?.slug === parsedSlugs?.[0]) || null,
    [candidates, parsedSlugs],
  );
  const candidateB = useMemo(
    () => candidates.find((entry) => entry?.slug === parsedSlugs?.[1]) || null,
    [candidates, parsedSlugs],
  );
  const fallbackSlugA = parsedSlugs?.[0] || '';
  const fallbackSlugB = parsedSlugs?.[1] || '';
  const fallbackNameA = toCandidateDisplayName(fallbackSlugA) || 'A';
  const fallbackNameB = toCandidateDisplayName(fallbackSlugB) || 'B';
  const fallbackTitle = t('comparison_title', { a: fallbackNameA, b: fallbackNameB });
  const fallbackStructuredData = {
    '@context': 'https://schema.org',
    '@type': ['FAQPage', 'Article'],
    headline: `${fallbackTitle} 2026`,
    url: `${BASE_URL}/comparar/${pairSlug || ''}`,
  };

  if (loadingCandidates || loadingQuiz) {
    return (
      <section className="candidate-page">
        <Helmet>
          <title>{`${fallbackTitle} | ${t('common:brand')}`}</title>
          <meta name="description" content={t('comparison_loading')} />
          <script type="application/ld+json">{JSON.stringify(fallbackStructuredData)}</script>
        </Helmet>
        <StructuredDataScript payload={fallbackStructuredData} />
        <article className="feed-state-card candidate-state-card">
          <span className="candidate-spinner" aria-hidden="true" />
          <span>{t('comparison_loading')}</span>
        </article>
        <MethodologyBadge />
      </section>
    );
  }

  if (errorCandidates || errorQuiz) {
    return (
      <section className="candidate-page">
        <Helmet>
          <title>{`${fallbackTitle} | ${t('common:brand')}`}</title>
          <meta name="description" content={t('comparison_error')} />
          <script type="application/ld+json">{JSON.stringify(fallbackStructuredData)}</script>
        </Helmet>
        <StructuredDataScript payload={fallbackStructuredData} />
        <article className="feed-state-card">{t('comparison_error')}</article>
        <MethodologyBadge />
      </section>
    );
  }

  if (!parsedSlugs || !candidateA || !candidateB || !quizData) {
    return (
      <section className="candidate-page">
        <Helmet>
          <title>{`${fallbackTitle} | ${t('common:brand')}`}</title>
          <meta name="description" content={t('comparison_not_found')} />
          <script type="application/ld+json">{JSON.stringify(fallbackStructuredData)}</script>
        </Helmet>
        <StructuredDataScript payload={fallbackStructuredData} />
        <article className="feed-state-card">{t('comparison_not_found')}</article>
        <Link className="candidate-back-link" to="/candidatos">
          {t('back_to_candidates')}
        </Link>
        <MethodologyBadge />
      </section>
    );
  }

  const comparisonTitle = t('comparison_title', { a: candidateA.name, b: candidateB.name });
  const structuredData = {
    '@context': 'https://schema.org',
    '@type': ['FAQPage', 'Article'],
    headline: `${comparisonTitle} 2026`,
    url: `${BASE_URL}/comparar/${candidateA.slug}-vs-${candidateB.slug}`,
  };

  return (
    <section className="candidate-page">
      <Helmet>
        <title>{`${comparisonTitle} | ${t('common:brand')}`}</title>
        <meta name="description" content={comparisonTitle} />
        <script type="application/ld+json">{JSON.stringify(structuredData)}</script>
      </Helmet>
      <StructuredDataScript payload={structuredData} />

      <p className="candidate-breadcrumb">
        <Link to="/candidatos">{t('back_to_candidates')}</Link>
      </p>
      <header className="comparison-header">
        <h1>{comparisonTitle}</h1>
      </header>

      <MethodologyBadge />
      <ComparisonHero candidateA={candidateA} candidateB={candidateB} />
      <TopicComparisonTable candidateA={candidateA} candidateB={candidateB} quizData={quizData} lang={language} t={t} />
    </section>
  );
}
