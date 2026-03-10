import * as ReactHelmetAsync from 'react-helmet-async';
import { useTranslation } from 'react-i18next';

import SentimentDashboard from '@/components/SentimentDashboard';

const Helmet = ReactHelmetAsync.Helmet || ReactHelmetAsync.default?.Helmet;

function SentimentPage() {
  const { t, i18n } = useTranslation('common');
  const language = i18n.language === 'en-US' ? 'en-US' : 'pt-BR';
  const datasetJsonLd = {
    '@context': 'https://schema.org',
    '@type': 'Dataset',
    name: t('sentiment.title'),
    description: t('sentiment.title'),
    inLanguage: language,
    url: '/sentimento',
    isBasedOn: '/data/sentiment.json',
  };

  return (
    <>
      <Helmet>
        <title>{`${t('sentiment.title')} | ${t('brand')}`}</title>
        <meta name="description" content={t('sentiment.title')} />
        <script type="application/ld+json">{JSON.stringify(datasetJsonLd)}</script>
      </Helmet>
      <SentimentDashboard />
    </>
  );
}

export default SentimentPage;
