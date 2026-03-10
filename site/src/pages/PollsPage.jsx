import * as ReactHelmetAsync from 'react-helmet-async';
import { useTranslation } from 'react-i18next';

import PollTracker from '@/components/PollTracker';

const Helmet = ReactHelmetAsync.Helmet || ReactHelmetAsync.default?.Helmet;

function PollsPage() {
  const { t, i18n } = useTranslation('common');
  const language = i18n.language === 'en-US' ? 'en-US' : 'pt-BR';
  const datasetJsonLd = {
    '@context': 'https://schema.org',
    '@type': 'Dataset',
    name: t('polls.title'),
    description: t('polls.title'),
    inLanguage: language,
    url: '/pesquisas',
    isBasedOn: '/data/polls.json',
  };

  return (
    <>
      <Helmet>
        <title>{`${t('polls.title')} | ${t('brand')}`}</title>
        <meta name="description" content={t('polls.title')} />
        <script type="application/ld+json">{JSON.stringify(datasetJsonLd)}</script>
      </Helmet>
      <PollTracker />
    </>
  );
}

export default PollsPage;
