import { useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';

import MethodologyBadge from '@/components/MethodologyBadge';
import { useData } from '@/hooks/useData';
import { CANDIDATE_COLORS } from '@/utils/candidateColors';

function CandidatesPage() {
  const { t } = useTranslation('candidates');
  const { data, loading, error } = useData('candidates');
  const candidates = useMemo(() => {
    if (Array.isArray(data)) {
      return data;
    }
    if (data && Array.isArray(data.candidates)) {
      return data.candidates;
    }
    return [];
  }, [data]);

  if (loading) {
    return (
      <section className="candidate-page">
        <article className="feed-state-card candidate-state-card">
          <span className="candidate-spinner" aria-hidden="true" />
          <span>{t('loading')}</span>
        </article>
        <MethodologyBadge />
      </section>
    );
  }

  if (error) {
    return (
      <section className="candidate-page">
        <article className="feed-state-card">{t('error')}</article>
        <MethodologyBadge />
      </section>
    );
  }

  if (candidates.length === 0) {
    return (
      <section className="candidate-page">
        <article className="feed-state-card">{t('not_found')}</article>
        <MethodologyBadge />
      </section>
    );
  }

  return (
    <section className="candidate-page">
      <h1 className="candidates-title">{t('title')}</h1>
      <div className="candidates-grid">
        {candidates.map((candidate) => {
          const statusKey = (candidate?.status || 'pre-candidate').replace('-', '_');
          const chipColor = candidate?.color || CANDIDATE_COLORS[candidate?.slug] || '#4A5568';
          return (
            <article className="candidate-list-card" key={candidate.slug}>
              <div className="candidate-list-head">
                <span className="candidate-list-dot" style={{ backgroundColor: chipColor }} />
                <div>
                  <h2>{candidate.name}</h2>
                  <p>{candidate.full_name}</p>
                </div>
              </div>
              <p className="candidate-list-party">
                <strong>{t('party_label')}:</strong> {candidate.party}
              </p>
              <span className="candidate-status">{t(statusKey)}</span>
              <Link className="candidate-profile-link" to={`/candidato/${candidate.slug}`}>
                {t('view_profile')}
              </Link>
            </article>
          );
        })}
      </div>
      <MethodologyBadge />
    </section>
  );
}

export default CandidatesPage;
