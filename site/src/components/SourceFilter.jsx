import { useTranslation } from 'react-i18next';

const sourceFilters = [
  'all',
  'mainstream',
  'politics',
  'magazine',
  'international',
  'institutional',
];

function SourceFilter({ selectedCategory, onSelectCategory }) {
  const { t } = useTranslation('common');

  return (
    <div className="source-filters" aria-label={t('feed.filters.aria_label')}>
      {sourceFilters.map((source) => (
        <button
          key={source}
          type="button"
          className={`source-filter-button ${selectedCategory === source ? 'active' : ''}`}
          onClick={() => onSelectCategory(source)}
        >
          {t(`feed.filters.${source}`)}
        </button>
      ))}
    </div>
  );
}

export default SourceFilter;
