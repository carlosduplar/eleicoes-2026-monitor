import * as ReactHelmetAsync from 'react-helmet-async';
import { useTranslation } from 'react-i18next';

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
  };

  return (
    <>
      <Helmet>
        <title>{`${t('markets.title')} | ${t('brand')}`}</title>
        <meta name="description" content={t('markets.disclaimer')} />
        <script type="application/ld+json">{JSON.stringify(datasetJsonLd)}</script>
      </Helmet>
      <section className="page-section">
        <h1>{t('markets.title')}</h1>
        <p>{t('markets.empty')}</p>
        <p className="text-muted">{t('markets.disclaimer')}</p>
      </section>
    </>
  );
}

export default MarketsPage;
