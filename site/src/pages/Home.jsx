import { useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';

import MethodologyBadge from '@/components/MethodologyBadge';
import NewsFeed from '@/components/NewsFeed';
import SourceFilter from '@/components/SourceFilter';
import { useData } from '@/hooks/useData';
import { CANDIDATE_COLORS } from '@/utils/candidateColors';

const MAX_POLL_PREVIEW_ITEMS = 4;
const MAX_CANDIDATE_PREVIEW_ITEMS = 5;

function normalizePolls(payload) {
  if (Array.isArray(payload)) {
    return payload;
  }
  if (payload && Array.isArray(payload.polls)) {
    return payload.polls;
  }
  return [];
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

function formatPollDate(value, language) {
  if (!value) {
    return '--';
  }
  const parsedDate = new Date(value);
  if (Number.isNaN(parsedDate.getTime())) {
    return '--';
  }
  const locale = language === 'en-US' ? 'en-US' : 'pt-BR';
  return new Intl.DateTimeFormat(locale, {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
  }).format(parsedDate);
}

function Home() {
  const { t, i18n } = useTranslation(['common', 'candidates']);
  const [selectedCategory, setSelectedCategory] = useState('all');
  const { data: pollsPayload, loading: pollsLoading, error: pollsError } = useData('polls');
  const { data: candidatesPayload, loading: candidatesLoading, error: candidatesError } = useData('candidates');

  const polls = useMemo(() => normalizePolls(pollsPayload), [pollsPayload]);
  const candidates = useMemo(() => normalizeCandidates(candidatesPayload), [candidatesPayload]);

  const latestPoll = useMemo(() => {
    return (
      [...polls]
        .filter(
          (poll) =>
            poll &&
            typeof poll === 'object' &&
            typeof poll.published_at === 'string' &&
            !Number.isNaN(new Date(poll.published_at).getTime()) &&
            Array.isArray(poll.results),
        )
        .sort((a, b) => new Date(b.published_at).getTime() - new Date(a.published_at).getTime())[0] || null
    );
  }, [polls]);

  const pollPreviewResults = useMemo(() => {
    if (!latestPoll || !Array.isArray(latestPoll.results)) {
      return [];
    }
    return latestPoll.results
      .filter(
        (result) =>
          result &&
          typeof result === 'object' &&
          typeof result.candidate_name === 'string' &&
          typeof result.percentage === 'number',
      )
      .map((result) => ({
        ...result,
        percentage: Math.max(0, Math.min(100, result.percentage)),
      }))
      .sort((a, b) => b.percentage - a.percentage)
      .slice(0, MAX_POLL_PREVIEW_ITEMS);
  }, [latestPoll]);

  const candidatePreview = useMemo(() => {
    return candidates
      .filter(
        (candidate) =>
          candidate &&
          typeof candidate === 'object' &&
          typeof candidate.slug === 'string' &&
          typeof candidate.name === 'string',
      )
      .slice(0, MAX_CANDIDATE_PREVIEW_ITEMS);
  }, [candidates]);

  const language = i18n.language === 'en-US' ? 'en-US' : 'pt-BR';
  const pollDateLabel = latestPoll ? formatPollDate(latestPoll.published_at, language) : '--';
  const latestPollInstitute = latestPoll?.institute || t('feed.unknown_source');

  return (
    <div className="home-grid">
      <section>
        <SourceFilter selectedCategory={selectedCategory} onSelectCategory={setSelectedCategory} />
        <NewsFeed selectedCategory={selectedCategory} />
      </section>
      <aside className="home-sidebar">
        <article className="sidebar-card">
          <h3>{t('home.sidebar.latest_poll.title')}</h3>
          {pollsLoading && <p>{t('polls.loading')}</p>}
          {!pollsLoading && pollsError && <p className="error-state">{t('polls.error')}</p>}
          {!pollsLoading && !pollsError && pollPreviewResults.length === 0 && <p>{t('polls.empty')}</p>}
          {!pollsLoading && !pollsError && pollPreviewResults.length > 0 && (
            <>
              <p className="sidebar-poll-meta">{t('home.sidebar.latest_poll.meta', { institute: latestPollInstitute, date: pollDateLabel })}</p>
              {pollPreviewResults.map((result) => {
                const color = CANDIDATE_COLORS[result.candidate_slug] || '#4A5568';
                return (
                  <div
                    className="poll-bar"
                    key={`${latestPoll?.id || latestPoll?.published_at}-${result.candidate_slug || result.candidate_name}`}
                  >
                    <span className="poll-name">{result.candidate_name}</span>
                    <div className="poll-track">
                      <div className="poll-fill" style={{ width: `${result.percentage}%`, background: color }} />
                    </div>
                    <span className="poll-pct">{`${Math.round(result.percentage)}%`}</span>
                  </div>
                );
              })}
              <Link className="link-accent" to="/pesquisas">
                {t('home.sidebar.latest_poll.link')}
              </Link>
            </>
          )}
        </article>
        <article className="sidebar-card">
          <h3>{t('home.sidebar.quiz.title')}</h3>
          <p>{t('home.sidebar.quiz.body')}</p>
          <Link className="cta-btn" to="/quiz">
            {t('home.sidebar.quiz.cta')}
          </Link>
        </article>
        <article className="sidebar-card">
          <h3>{t('home.sidebar.candidates.title')}</h3>
          {candidatesLoading && <p>{t('candidates:loading')}</p>}
          {!candidatesLoading && candidatesError && <p className="error-state">{t('candidates:error')}</p>}
          {!candidatesLoading && !candidatesError && candidatePreview.length === 0 && <p>{t('candidates:not_found')}</p>}
          {!candidatesLoading && !candidatesError && candidatePreview.length > 0 && (
            <>
              {candidatePreview.map((candidate) => (
                <Link className="cand-link" key={candidate.slug} to={`/candidato/${candidate.slug}`}>
                  <span className="cand-avatar" style={{ backgroundColor: candidate.color || CANDIDATE_COLORS[candidate.slug] || '#4A5568' }}>
                    {candidate.name.slice(0, 1).toUpperCase()}
                  </span>
                  <span>{candidate.name}</span>
                  {candidate.party ? <span className="cand-party">({candidate.party})</span> : null}
                </Link>
              ))}
              <Link className="link-accent" to="/candidatos">
                {t('home.sidebar.candidates.link')}
              </Link>
            </>
          )}
        </article>
        <MethodologyBadge />
      </aside>
    </div>
  );
}

export default Home;
