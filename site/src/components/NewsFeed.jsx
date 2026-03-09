import { useTranslation } from 'react-i18next';

import { useData } from '@/hooks/useData';
import MethodologyBadge from './MethodologyBadge';

const statusToClass = {
  raw: 'status-raw',
  validated: 'status-validated',
  curated: 'status-curated',
};

function normalizeArticles(payload) {
  if (Array.isArray(payload)) {
    return payload;
  }
  if (payload && Array.isArray(payload.articles)) {
    return payload.articles;
  }
  return [];
}

function toSourceCategory(article) {
  if (article?.source && typeof article.source === 'object' && article.source.category) {
    return article.source.category;
  }
  if (typeof article?.source_category === 'string') {
    return article.source_category;
  }
  return 'mainstream';
}

function toSourceName(article, fallbackLabel) {
  if (typeof article?.source === 'string' && article.source.length > 0) {
    return article.source;
  }
  if (article?.source && typeof article.source === 'object' && article.source.name) {
    return article.source.name;
  }
  return fallbackLabel;
}

function toSummary(article, language, fallbackText) {
  if (!article?.summaries || typeof article.summaries !== 'object') {
    return fallbackText;
  }
  return article.summaries[language] || article.summaries['pt-BR'] || fallbackText;
}

function toPublishedLabel(value, language) {
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
    hour: '2-digit',
    minute: '2-digit',
  }).format(parsedDate);
}

function toMinutesAgo(value) {
  if (!value) {
    return 0;
  }
  const parsedDate = new Date(value);
  if (Number.isNaN(parsedDate.getTime())) {
    return 0;
  }
  const delta = Date.now() - parsedDate.getTime();
  return Math.max(0, Math.floor(delta / 60000));
}

function NewsFeed({ selectedCategory }) {
  const { t, i18n } = useTranslation('common');
  const { data, loading, error } = useData('articles');

  const articles = normalizeArticles(data);
  const visibleArticles = articles.filter((article) => {
    if (selectedCategory === 'all') {
      return true;
    }
    return toSourceCategory(article) === selectedCategory;
  });

  const lastUpdatedAt = Array.isArray(data)
    ? visibleArticles[0]?.collected_at
    : data?.last_updated || visibleArticles[0]?.collected_at;
  const updatedMinutes = toMinutesAgo(lastUpdatedAt);

  if (loading) {
    return (
      <section className="feed-stack">
        <article className="feed-state-card">{t('feed.loading')}</article>
        <MethodologyBadge />
      </section>
    );
  }

  if (error) {
    return (
      <section className="feed-stack">
        <article className="feed-state-card">{t('feed.error')}</article>
        <MethodologyBadge />
      </section>
    );
  }

  if (visibleArticles.length === 0) {
    return (
      <section className="feed-stack">
        <div className="feed-heading">
          <h1>{t('home.feed_title')}</h1>
        </div>
        <article className="feed-state-card">{t('feed.empty')}</article>
        <MethodologyBadge />
      </section>
    );
  }

  return (
    <section className="feed-stack">
      <div className="feed-heading">
        <h1>{t('home.feed_title')}</h1>
        <span>{t('feed.updated_ago', { minutes: updatedMinutes })}</span>
      </div>
      {visibleArticles.map((article) => {
        const sourceCategory = toSourceCategory(article);
        const sourceName = toSourceName(article, t('feed.unknown_source'));
        const summary = toSummary(article, i18n.language, t('feed.analysis_in_progress'));
        const statusKey = article.status || 'raw';
        const isValidated = statusKey === 'validated';
        const isCurated = statusKey === 'curated';
        const statusLabel = isValidated
          ? `\u2713 ${t('feed.validated')}`
          : isCurated
            ? t('feed.curated')
            : t('feed.raw_badge');

        return (
          <article key={article.id || article.url || article.title} className="feed-card">
            <div className="feed-image-placeholder">{t('feed.image_placeholder')}</div>
            <div className="feed-card-content">
              <div className="feed-card-badges">
                <span className="feed-category-badge">{t(`feed.categories.${sourceCategory}`)}</span>
                <span className={`feed-status-badge ${statusToClass[statusKey] || statusToClass.raw}`}>
                  {statusLabel}
                </span>
              </div>
              <h3>{article.title}</h3>
              <p>{summary}</p>
              <div className="feed-meta">
                <span>{sourceName}</span>
                <span aria-hidden="true">{'\u00B7'}</span>
                <span>{toPublishedLabel(article.published_at, i18n.language)}</span>
                <span className="feed-tag">{t(`feed.filters.${sourceCategory}`)}</span>
              </div>
            </div>
          </article>
        );
      })}
      <MethodologyBadge />
    </section>
  );
}

export default NewsFeed;
