import * as ReactHelmetAsync from 'react-helmet-async';
import { useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, useParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';

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

function normalizeArticles(payload) {
  if (Array.isArray(payload)) {
    return payload;
  }
  if (payload && Array.isArray(payload.articles)) {
    return payload.articles;
  }
  return [];
}

function normalizePolls(payload) {
  if (Array.isArray(payload)) {
    return payload;
  }
  if (payload && Array.isArray(payload.polls)) {
    return payload.polls;
  }
  return [];
}

function statusTranslationKey(status) {
  return typeof status === 'string' ? status.replace('-', '_') : 'pre_candidate';
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

function toDateLabel(value, language) {
  if (typeof value !== 'string' || value.length === 0) {
    return '--';
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return '--';
  }
  const locale = language === 'en-US' ? 'en-US' : 'pt-BR';
  return new Intl.DateTimeFormat(locale, {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
  }).format(date);
}

function CandidateHero({ candidate, t }) {
  const statusKey = statusTranslationKey(candidate.status);
  return (
    <header className="candidate-hero" style={{ borderTopColor: candidate.color || CANDIDATE_COLORS[candidate.slug] }}>
      <h1>{candidate.full_name}</h1>
      <p>
        <strong>{t('party_label')}:</strong> {candidate.party}
      </p>
      <span className="candidate-status">{t(statusKey)}</span>
    </header>
  );
}

function CandidateBio({ candidate, lang, t }) {
  const bio = lang === 'en-US' ? candidate.bio_en : candidate.bio_pt;
  return (
    <section className="candidate-card">
      <h2>{t('bio_label')}</h2>
      <p>{bio}</p>
    </section>
  );
}

function CandidateSentiment({ slug, sentimentData, t }) {
  const topicScores = sentimentData?.by_topic?.[slug];
  const rows = useMemo(() => {
    if (!topicScores || typeof topicScores !== 'object') {
      return [];
    }
    return Object.entries(topicScores)
      .filter(([, value]) => typeof value === 'number' && Number.isFinite(value))
      .map(([topicId, score]) => ({
        topic: toTopicLabel(topicId),
        score: Number(score.toFixed(3)),
      }));
  }, [topicScores]);

  return (
    <section className="candidate-card">
      <h2>{t('sentiment_label')}</h2>
      {rows.length === 0 ? (
        <p className="candidate-muted">{t('no_sentiment_data')}</p>
      ) : (
        <div className="candidate-sentiment-chart">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={rows} layout="vertical" margin={{ top: 8, right: 12, bottom: 8, left: 12 }}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis type="number" domain={[-1, 1]} />
              <YAxis type="category" width={120} dataKey="topic" />
              <Tooltip formatter={(value) => (typeof value === 'number' ? value.toFixed(2) : value)} />
              <Bar dataKey="score" fill={CANDIDATE_COLORS[slug] || '#4A5568'} radius={[0, 4, 4, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}
    </section>
  );
}

function CandidateArticles({ slug, articles, lang, t }) {
  const recentArticles = useMemo(
    () =>
      articles
        .filter(
          (article) =>
            Array.isArray(article?.candidates_mentioned) &&
            article.candidates_mentioned.includes(slug) &&
            typeof article.title === 'string' &&
            typeof article.url === 'string',
        )
        .sort((a, b) => {
          const aTime = new Date(a.published_at || 0).getTime();
          const bTime = new Date(b.published_at || 0).getTime();
          return bTime - aTime;
        })
        .slice(0, 5),
    [articles, slug],
  );

  return (
    <section className="candidate-card">
      <h2>{t('recent_news')}</h2>
      {recentArticles.length === 0 ? (
        <p className="candidate-muted">{t('recent_news_empty')}</p>
      ) : (
        <ul className="candidate-article-list">
          {recentArticles.map((article) => (
            <li key={article.id || article.url}>
              <a href={article.url} rel="noopener noreferrer" target="_blank">
                {article.title}
              </a>
              <p className="candidate-muted">
                {t('source_label')}: {article.source || '--'} · {toDateLabel(article.published_at, lang)}
              </p>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

function CandidatePollSnapshot({ slug, polls, lang, t }) {
  const latestPoll = useMemo(
    () =>
      [...polls]
        .filter((poll) => typeof poll?.published_at === 'string' && Array.isArray(poll?.results))
        .sort((a, b) => new Date(b.published_at).getTime() - new Date(a.published_at).getTime())[0],
    [polls],
  );
  const result = latestPoll?.results?.find(
    (entry) => entry?.candidate_slug === slug && typeof entry?.percentage === 'number',
  );

  return (
    <section className="candidate-card">
      <h2>{t('latest_poll')}</h2>
      {!latestPoll || !result ? (
        <p className="candidate-muted">{t('no_poll_data')}</p>
      ) : (
        <>
          <p className="candidate-poll-value">{t('poll_percentage', { percentage: Number(result.percentage.toFixed(1)) })}</p>
          <p className="candidate-muted">
            {t('poll_meta', {
              institute: latestPoll.institute || '--',
              date: toDateLabel(latestPoll.published_at, lang),
            })}
          </p>
        </>
      )}
    </section>
  );
}

function CandidateTSELink({ candidate, t }) {
  if (!candidate.tse_registration_url) {
    return null;
  }

  return (
    <section className="candidate-card">
      <h2>{t('tse_registration')}</h2>
      <a href={candidate.tse_registration_url} rel="noopener noreferrer" target="_blank">
        {t('tse_link_text')}
      </a>
    </section>
  );
}

export default function CandidatePage() {
  const { slug } = useParams();
  const { t, i18n } = useTranslation(['candidates', 'common']);
  const { data: candidatesData, loading: loadingCandidates, error: errorCandidates } = useData('candidates');
  const { data: articlesData, loading: loadingArticles, error: errorArticles } = useData('articles');
  const { data: sentimentData, loading: loadingSentiment, error: errorSentiment } = useData('sentiment');
  const { data: pollsData, loading: loadingPolls, error: errorPolls } = useData('polls');
  const language = i18n.language === 'en-US' ? 'en-US' : 'pt-BR';

  const candidates = useMemo(() => normalizeCandidates(candidatesData), [candidatesData]);
  const articles = useMemo(() => normalizeArticles(articlesData), [articlesData]);
  const polls = useMemo(() => normalizePolls(pollsData), [pollsData]);
  const candidate = useMemo(
    () => candidates.find((entry) => typeof entry?.slug === 'string' && entry.slug === slug) || null,
    [candidates, slug],
  );
  const fallbackSlug = typeof slug === 'string' ? slug : '';
  const fallbackName = toCandidateDisplayName(fallbackSlug);
  const fallbackStructuredData = {
    '@context': 'https://schema.org',
    '@type': ['Person', 'ProfilePage'],
    name: fallbackName || t('title'),
    description: t('loading'),
    affiliation: { '@type': 'Organization', name: '--' },
    url: `${BASE_URL}/candidato/${fallbackSlug}`,
  };

  if (loadingCandidates || loadingArticles || loadingSentiment || loadingPolls) {
    return (
      <section className="candidate-page">
        <Helmet>
          <title>{`${fallbackName || t('title')} | ${t('common:brand')}`}</title>
          <meta name="description" content={t('loading')} />
          <script type="application/ld+json">{JSON.stringify(fallbackStructuredData)}</script>
        </Helmet>
        <StructuredDataScript payload={fallbackStructuredData} />
        <article className="feed-state-card candidate-state-card">
          <span className="candidate-spinner" aria-hidden="true" />
          <span>{t('loading')}</span>
        </article>
        <MethodologyBadge />
      </section>
    );
  }

  if (errorCandidates || errorArticles || errorSentiment || errorPolls) {
    return (
      <section className="candidate-page">
        <Helmet>
          <title>{`${fallbackName || t('title')} | ${t('common:brand')}`}</title>
          <meta name="description" content={t('error')} />
          <script type="application/ld+json">{JSON.stringify(fallbackStructuredData)}</script>
        </Helmet>
        <StructuredDataScript payload={fallbackStructuredData} />
        <article className="feed-state-card">{t('error')}</article>
        <MethodologyBadge />
      </section>
    );
  }

  if (!candidate) {
    return (
      <section className="candidate-page">
        <Helmet>
          <title>{`${fallbackName || t('title')} | ${t('common:brand')}`}</title>
          <meta name="description" content={t('not_found')} />
          <script type="application/ld+json">{JSON.stringify(fallbackStructuredData)}</script>
        </Helmet>
        <StructuredDataScript payload={fallbackStructuredData} />
        <article className="feed-state-card">{t('not_found')}</article>
        <Link className="candidate-back-link" to="/candidatos">
          {t('back_to_candidates')}
        </Link>
        <MethodologyBadge />
      </section>
    );
  }

  const description = language === 'en-US' ? candidate.bio_en : candidate.bio_pt;
  const structuredData = {
    '@context': 'https://schema.org',
    '@type': ['Person', 'ProfilePage'],
    name: candidate.full_name,
    description,
    affiliation: { '@type': 'Organization', name: candidate.party },
    url: `${BASE_URL}/candidato/${candidate.slug}`,
  };

  return (
    <section className="candidate-page">
      <Helmet>
        <title>{`${candidate.name} | ${t('title')} | ${t('common:brand')}`}</title>
        <meta name="description" content={description} />
        <script type="application/ld+json">{JSON.stringify(structuredData)}</script>
      </Helmet>
      <StructuredDataScript payload={structuredData} />

      <p className="candidate-breadcrumb">
        <Link to="/candidatos">{t('back_to_candidates')}</Link>
      </p>

      <CandidateHero candidate={candidate} t={t} />

      <div className="candidate-layout">
        <div className="candidate-main">
          <CandidateBio candidate={candidate} lang={language} t={t} />
          <CandidateSentiment slug={candidate.slug} sentimentData={sentimentData} t={t} />
          <CandidateArticles slug={candidate.slug} articles={articles} lang={language} t={t} />
        </div>
        <aside className="candidate-sidebar">
          <CandidatePollSnapshot slug={candidate.slug} polls={polls} lang={language} t={t} />
          <CandidateTSELink candidate={candidate} t={t} />
          <MethodologyBadge />
        </aside>
      </div>
    </section>
  );
}
