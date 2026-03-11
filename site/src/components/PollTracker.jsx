import { useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';

import { useData } from '@/hooks/useData';
import { CANDIDATE_COLORS } from '@/utils/candidateColors';

import MethodologyBadge from './MethodologyBadge';

/**
 * @typedef {'pt-BR' | 'en-US'} AppLocale
 * @typedef {{
 *   candidate_slug: string,
 *   candidate_name: string,
 *   percentage: number,
 *   variation?: number | null
 * }} PollResult
 * @typedef {{
 *   id: string,
 *   institute: string,
 *   published_at: string,
 *   collected_at: string,
 *   type: 'estimulada' | 'espontanea',
 *   sample_size?: number,
 *   margin_of_error?: number,
 *   confidence_level?: number,
 *   tse_registration?: string | null,
 *   source_url?: string,
 *   results: PollResult[]
 * }} Poll
 * @typedef {{ dateLabel: string, dateIso: string } & Record<string, string | number>} PollChartRow
 */

const ALL_INSTITUTES = '__ALL__';

function normalizePollPayload(payload) {
  /** @type {unknown[]} */
  const items = Array.isArray(payload) ? payload : payload?.polls;
  if (!Array.isArray(items)) {
    return [];
  }

  /** @type {Poll[]} */
  const polls = [];
  items.forEach((item) => {
    if (!item || typeof item !== 'object') {
      return;
    }
    const raw = /** @type {Record<string, unknown>} */ (item);
    if (
      typeof raw.id !== 'string' ||
      typeof raw.institute !== 'string' ||
      typeof raw.published_at !== 'string' ||
      typeof raw.collected_at !== 'string' ||
      (raw.type !== 'estimulada' && raw.type !== 'espontanea') ||
      !Array.isArray(raw.results)
    ) {
      return;
    }
    const results = raw.results
      .filter((entry) => entry && typeof entry === 'object')
      .map((entry) => /** @type {Record<string, unknown>} */ (entry))
      .filter(
        (entry) =>
          typeof entry.candidate_slug === 'string' &&
          typeof entry.candidate_name === 'string' &&
          typeof entry.percentage === 'number',
      )
      .map((entry) => ({
        candidate_slug: /** @type {string} */ (entry.candidate_slug),
        candidate_name: /** @type {string} */ (entry.candidate_name),
        percentage: /** @type {number} */ (entry.percentage),
        variation: typeof entry.variation === 'number' || entry.variation === null ? entry.variation : undefined,
      }));

    polls.push({
      id: raw.id,
      institute: raw.institute,
      published_at: raw.published_at,
      collected_at: raw.collected_at,
      type: raw.type,
      results,
      sample_size: typeof raw.sample_size === 'number' ? raw.sample_size : undefined,
      margin_of_error: typeof raw.margin_of_error === 'number' ? raw.margin_of_error : undefined,
      confidence_level: typeof raw.confidence_level === 'number' ? raw.confidence_level : undefined,
      tse_registration:
        typeof raw.tse_registration === 'string' || raw.tse_registration === null ? raw.tse_registration : undefined,
      source_url: typeof raw.source_url === 'string' ? raw.source_url : undefined,
    });
  });

  return polls;
}

function getInstituteOptions(polls) {
  return Array.from(new Set(polls.map((poll) => poll.institute))).sort((a, b) => a.localeCompare(b));
}

function formatDateLabel(publishedAt, locale) {
  const date = new Date(publishedAt);
  if (Number.isNaN(date.valueOf())) {
    return publishedAt.slice(0, 10);
  }
  const day = `${date.getUTCDate()}`.padStart(2, '0');
  const month = `${date.getUTCMonth() + 1}`.padStart(2, '0');
  return locale === 'en-US' ? `${month}/${day}` : `${day}/${month}`;
}

function buildCandidateSeries(polls) {
  const bySlug = new Map();
  polls.forEach((poll) => {
    poll.results.forEach((result) => {
      if (!bySlug.has(result.candidate_slug)) {
        bySlug.set(result.candidate_slug, result.candidate_name);
      }
    });
  });

  return Array.from(bySlug.entries()).map(([slug, label]) => ({
    slug,
    label,
    color: CANDIDATE_COLORS[slug] || '#4A5568',
  }));
}

function buildChartRows(polls, selectedInstitute, locale) {
  /** @type {Map<string, Record<string, { sum: number, count: number }>>} */
  const byDate = new Map();
  polls
    .filter((poll) => selectedInstitute === ALL_INSTITUTES || poll.institute === selectedInstitute)
    .forEach((poll) => {
      const dateIso = poll.published_at.slice(0, 10);
      if (!byDate.has(dateIso)) {
        byDate.set(dateIso, {});
      }
      const candidates = byDate.get(dateIso);
      if (!candidates) {
        return;
      }
      poll.results.forEach((result) => {
        if (!candidates[result.candidate_slug]) {
          candidates[result.candidate_slug] = { sum: 0, count: 0 };
        }
        candidates[result.candidate_slug].sum += result.percentage;
        candidates[result.candidate_slug].count += 1;
      });
    });

  return Array.from(byDate.entries())
    .sort((a, b) => a[0].localeCompare(b[0]))
    .map(([dateIso, entries]) => {
      /** @type {PollChartRow} */
      const row = {
        dateIso,
        dateLabel: formatDateLabel(`${dateIso}T00:00:00Z`, locale),
      };
      Object.entries(entries).forEach(([slug, value]) => {
        row[slug] = Number((value.sum / value.count).toFixed(2));
      });
      return row;
    });
}

function PollTracker() {
  const { t, i18n } = useTranslation('common');
  const { data, loading, error } = useData('polls');
  const [selectedInstitute, setSelectedInstitute] = useState(ALL_INSTITUTES);
  const locale = i18n.language === 'en-US' ? 'en-US' : 'pt-BR';
  const polls = useMemo(() => normalizePollPayload(data), [data]);
  const instituteOptions = useMemo(() => getInstituteOptions(polls), [polls]);
  const chartRows = useMemo(() => buildChartRows(polls, selectedInstitute, locale), [polls, selectedInstitute, locale]);
  const candidateSeries = useMemo(() => buildCandidateSeries(polls), [polls]);
  const dotVisible = chartRows.length < 5;

  if (loading) {
    return (
      <section className="sentiment-stack">
        <article className="feed-state-card">{t('polls.loading')}</article>
        <MethodologyBadge />
      </section>
    );
  }

  if (error) {
    return (
      <section className="sentiment-stack">
        <article className="feed-state-card">{t('polls.error')}</article>
        <MethodologyBadge />
      </section>
    );
  }

  if (polls.length === 0 || chartRows.length === 0 || candidateSeries.length === 0) {
    return (
      <section className="sentiment-stack">
        <article className="feed-state-card">{t('polls.empty')}</article>
        <MethodologyBadge />
      </section>
    );
  }

  return (
    <section className="sentiment-stack">
      <article className="sentiment-card">
        <div className="sentiment-head">
          <h1>{t('polls.title')}</h1>
          <label htmlFor="poll-institute-filter">
            <span className="sr-only">{t('polls.institute_label')}</span>
            <select
              id="poll-institute-filter"
              className="sentiment-toggle"
              value={selectedInstitute}
              onChange={(event) => setSelectedInstitute(event.target.value)}
            >
              <option value={ALL_INSTITUTES}>{t('polls.filter_all')}</option>
              {instituteOptions.map((institute) => (
                <option key={institute} value={institute}>
                  {institute}
                </option>
              ))}
            </select>
          </label>
        </div>
        <div style={{ width: '100%', height: 400 }}>
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={chartRows} margin={{ top: 12, right: 20, bottom: 12, left: 0 }}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="dateLabel" />
              <YAxis
                domain={[0, 100]}
                label={{ value: t('polls.percentage_label'), angle: -90, position: 'insideLeft' }}
              />
              <Tooltip
                formatter={(value, name) => [`${value}%`, name]}
                labelFormatter={(value, rows) => {
                  const entry = rows?.[0]?.payload;
                  return entry?.dateIso || value;
                }}
              />
              <Legend verticalAlign="bottom" />
              {candidateSeries.map((candidate) => (
                <Line
                  key={candidate.slug}
                  type="monotone"
                  dataKey={candidate.slug}
                  name={candidate.label}
                  stroke={candidate.color}
                  strokeWidth={2}
                  dot={dotVisible}
                  connectNulls
                />
              ))}
            </LineChart>
          </ResponsiveContainer>
        </div>
        <p className="sentiment-disclaimer">
          <strong>{t('polls.institute_label')}:</strong>{' '}
          {selectedInstitute === ALL_INSTITUTES ? t('polls.filter_all') : selectedInstitute}
          {' | '}
          {t('polls.methodology_note')}
        </p>
      </article>
      <MethodologyBadge />
    </section>
  );
}

export default PollTracker;
