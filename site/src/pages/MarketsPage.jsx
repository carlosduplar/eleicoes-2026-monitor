import * as ReactHelmetAsync from 'react-helmet-async';
import { useTranslation } from 'react-i18next';

import MarketOdds from '@/components/MarketOdds';

const Helmet = ReactHelmetAsync.Helmet || ReactHelmetAsync.default?.Helmet;

function MarketsPage() {
  const { t, i18n } = useTranslation('common');
  const language = i18n.language === 'en-US' ? 'en-US' : 'pt-BR';
  const datasetJsonLd = {
    '@context': 'https://schema.org',
    '@type': 'Dataset',
    name: t('markets.title'),
    description: t('markets.disclaimer'),
    inLanguage: language,
    url: '/mercados',
    isBasedOn: '/data/markets.json',
  };

  return (
    <>
      <Helmet>
        <title>{`${t('markets.title')} | ${t('brand')}`}</title>
        <meta name="description" content={t('markets.disclaimer')} />
        <script type="application/ld+json">{JSON.stringify(datasetJsonLd)}</script>
      </Helmet>
      <MarketOdds />
    </>
  );
}

export default MarketsPage;
