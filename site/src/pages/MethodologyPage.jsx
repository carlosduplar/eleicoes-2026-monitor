import * as ReactHelmetAsync from 'react-helmet-async';
import { useTranslation } from 'react-i18next';

const Helmet = ReactHelmetAsync.Helmet || ReactHelmetAsync.default?.Helmet;
const PIPELINE_STEPS = ['collection', 'summarization', 'sentiment', 'polls', 'quiz'];

function MethodologyPage() {
  const { t } = useTranslation('methodology');
  const { t: tCommon } = useTranslation('common');
  const limitationItems = t('limitations.items', { returnObjects: true });
  const methodologyJsonLd = {
    '@context': 'https://schema.org',
    '@type': ['AboutPage', 'FAQPage'],
    name: 'Metodologia — Portal Eleicoes BR 2026',
    description: 'Como funciona o pipeline de coleta e analise do portal.',
    url: 'https://eleicoes2026.com.br/metodologia',
  };
  const methodologyJsonLdText = JSON.stringify(methodologyJsonLd);

  return (
    <article className="methodology-page">
      <Helmet>
        <title>{`${t('title')} | ${tCommon('brand')}`}</title>
        <script type="application/ld+json">{methodologyJsonLdText}</script>
      </Helmet>
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: methodologyJsonLdText }} />

      <header className="methodology-section">
        <h1>{t('title')}</h1>
        <p className="methodology-subtitle">{t('subtitle')}</p>
      </header>

      <section className="methodology-section methodology-disclaimer">
        <h2>{t('disclaimer.heading')}</h2>
        <p>{t('disclaimer.body')}</p>
      </section>

      <section className="methodology-section">
        <h2>{t('pipeline.heading')}</h2>
        <div className="methodology-steps">
          {PIPELINE_STEPS.map((step, index) => (
            <div key={step} className="methodology-step">
              <div className="methodology-step-num">{index + 1}</div>
              <div>
                <h3>{t(`pipeline.${step}.label`)}</h3>
                <p>{t(`pipeline.${step}.body`)}</p>
              </div>
            </div>
          ))}
        </div>
      </section>

      <section className="methodology-section">
        <h2>{t('limitations.heading')}</h2>
        <ul className="methodology-limitations">
          {Array.isArray(limitationItems) &&
            limitationItems.map((item) => (
              <li key={item}>
                <span>{item}</span>
              </li>
            ))}
        </ul>
      </section>

      <section className="methodology-section methodology-error-section">
        <h2>{t('error_reporting.heading')}</h2>
        <p>{t('error_reporting.body')}</p>
        <a
          className="methodology-cta"
          href="https://github.com/carlosduplar/eleicoes-2026-monitor/issues"
          target="_blank"
          rel="noopener noreferrer"
        >
          {t('error_reporting.cta')}
        </a>
      </section>

      <p className="methodology-repo">
        <a href={t('repo_link')} target="_blank" rel="noopener noreferrer">
          {t('repo_link')}
        </a>
      </p>
    </article>
  );
}

export default MethodologyPage;
