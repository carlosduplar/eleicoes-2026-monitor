import { useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';

import { useData } from '@/hooks/useData';
import { CANDIDATE_COLORS } from '@/utils/candidateColors';

import MethodologyBadge from './MethodologyBadge';

const VIEW_BY_TOPIC = 'by_topic';
const VIEW_BY_SOURCE = 'by_source';
const CANDIDATE_ORDER = Object.keys(CANDIDATE_COLORS);

function formatLabel(slug) {
  return slug
    .split(/[-_]/g)
    .map((part) => {
      if (part.length === 0) {
        return part;
      }
      if (part.toLowerCase() === 'jr') {
        return 'Jr';
      }
      return `${part[0].toUpperCase()}${part.slice(1)}`;
    })
    .join(' ');
}

function collectColumns(viewData) {
  const columns = new Set();
  Object.values(viewData || {}).forEach((candidateEntry) => {
    if (candidateEntry && typeof candidateEntry === 'object') {
      Object.keys(candidateEntry).forEach((columnKey) => columns.add(columnKey));
    }
  });
  return Array.from(columns);
}

function getSentimentClass(score) {
  if (score < -0.3) {
    return 'is-negative';
  }
  if (score > 0.3) {
    return 'is-positive';
  }
  return 'is-neutral';
}

function SentimentDashboard() {
  const { t, i18n } = useTranslation('common');
  const { data, loading, error } = useData('sentiment');
  const [viewMode, setViewMode] = useState(VIEW_BY_TOPIC);

  const viewData = data?.[viewMode];
  const columns = useMemo(() => collectColumns(viewData), [viewData]);
  const hasRows = CANDIDATE_ORDER.length > 0;
  const hasColumns = columns.length > 0;
  const isEmpty = !viewData || Object.keys(viewData).length === 0 || !hasRows || !hasColumns;
  const disclaimer = i18n.language === 'en-US' ? data?.disclaimer_en : data?.disclaimer_pt;

  if (loading) {
    return (
      <section className="sentiment-stack">
        <article className="sentiment-card">
          <div className="sentiment-head">
            <h1>{t('sentiment.title')}</h1>
            <div className="sentiment-toggle-group" role="group" aria-label={t('nav.sentimento')}>
              <button className="sentiment-toggle active" type="button">
                {t('sentiment.by_topic')}
              </button>
              <button className="sentiment-toggle" type="button">
                {t('sentiment.by_source')}
              </button>
            </div>
          </div>
          <p className="sentiment-loading-copy">{t('sentiment.loading')}</p>
          <div className="sentiment-skeleton-grid" aria-hidden="true">
            {Array.from({ length: 6 }).map((_, rowIndex) => (
              <div className="sentiment-skeleton-row" key={`skeleton-row-${rowIndex}`}>
                <span className="sentiment-skeleton-line sentiment-skeleton-candidate" />
                {Array.from({ length: 6 }).map((__, cellIndex) => (
                  <span className="sentiment-skeleton-line sentiment-skeleton-cell" key={cellIndex} />
                ))}
              </div>
            ))}
          </div>
        </article>
        <MethodologyBadge />
      </section>
    );
  }

  if (error) {
    return (
      <section className="sentiment-stack">
        <article className="feed-state-card">{t('sentiment.error')}</article>
        <MethodologyBadge />
      </section>
    );
  }

  if (isEmpty) {
    return (
      <section className="sentiment-stack">
        <article className="feed-state-card">{t('sentiment.empty')}</article>
        <MethodologyBadge />
      </section>
    );
  }

  return (
    <section className="sentiment-stack">
      <article className="sentiment-card">
        <div className="sentiment-head">
          <h1>{t('sentiment.title')}</h1>
          <div className="sentiment-toggle-group" role="group" aria-label={t('nav.sentimento')}>
            <button
              className={`sentiment-toggle ${viewMode === VIEW_BY_TOPIC ? 'active' : ''}`}
              onClick={() => setViewMode(VIEW_BY_TOPIC)}
              type="button"
            >
              {t('sentiment.by_topic')}
            </button>
            <button
              className={`sentiment-toggle ${viewMode === VIEW_BY_SOURCE ? 'active' : ''}`}
              onClick={() => setViewMode(VIEW_BY_SOURCE)}
              type="button"
            >
              {t('sentiment.by_source')}
            </button>
          </div>
        </div>
        {disclaimer ? (
          <p className="sentiment-disclaimer">
            <strong>{t('sentiment.disclaimer_label')}</strong> {disclaimer}
          </p>
        ) : null}
        <div className="sentiment-table-wrap">
          <table className="sentiment-table">
            <thead>
              <tr>
                <th>{t('nav.candidatos')}</th>
                {columns.map((columnKey) => (
                  <th key={columnKey}>{formatLabel(columnKey)}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {CANDIDATE_ORDER.map((candidateSlug) => {
                const candidateScores = viewData?.[candidateSlug];
                return (
                  <tr key={candidateSlug}>
                    <td>
                      <div className="sentiment-candidate-cell">
                        <span
                          className="sentiment-candidate-dot"
                          style={{ backgroundColor: CANDIDATE_COLORS[candidateSlug] }}
                        />
                        <span>{formatLabel(candidateSlug)}</span>
                      </div>
                    </td>
                    {columns.map((columnKey) => {
                      const rawValue = candidateScores?.[columnKey];
                      const hasNumericValue = typeof rawValue === 'number' && Number.isFinite(rawValue);
                      const cellClass = hasNumericValue
                        ? `sentiment-value ${getSentimentClass(rawValue)}`
                        : 'sentiment-value is-missing';
                      return (
                        <td key={`${candidateSlug}-${columnKey}`}>
                          <span className={cellClass}>
                            {hasNumericValue ? rawValue.toFixed(1) : '\u2014'}
                          </span>
                        </td>
                      );
                    })}
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </article>
      <MethodologyBadge />
    </section>
  );
}

export default SentimentDashboard;
