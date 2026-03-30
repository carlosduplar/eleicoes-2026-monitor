import { useState } from 'react';
import { useTranslation } from 'react-i18next';

import { useData } from '@/hooks/useData';

function formatBRL(value) {
  if (typeof value !== 'number' || !Number.isFinite(value)) {
    return '--';
  }
  return new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL', maximumFractionDigits: 0 }).format(value);
}

function CandidatePhoto({ photoUrl, fullName }) {
  if (!photoUrl) {
    return (
      <div className="candidate-photo-placeholder">
        <span>{fullName?.charAt(0) || '?'}</span>
      </div>
    );
  }

  return (
    <img
      src={photoUrl}
      alt={`Foto de ${fullName}`}
      className="candidate-photo"
      onError={(e) => {
        e.target.style.display = 'none';
        e.target.nextSibling.style.display = 'flex';
      }}
    />
  );
}

function DeclaredAssets({ assets, t }) {
  if (!assets || !assets.total_value) {
    return null;
  }

  return (
    <div className="gov-data-assets-block">
      <h4>{t('tse_declared_assets')}</h4>
      <p className="gov-data-assets-total">
        <strong>{formatBRL(assets.total_value)}</strong>
        <span className="candidate-muted"> ({assets.count} bens declarados)</span>
      </p>
      {assets.assets && assets.assets.length > 0 && (
        <ul className="gov-data-assets-list">
          {assets.assets.slice(0, 5).map((asset, idx) => (
            // eslint-disable-next-line react/no-array-index-key
            <li key={idx}>
              <span className="asset-description">{asset.description}</span>
              <span className="asset-value">{formatBRL(asset.value)}</span>
            </li>
          ))}
          {assets.assets.length > 5 && (
            <li className="asset-more">{t('tse_assets_more', { count: assets.assets.length - 5 })}</li>
          )}
        </ul>
      )}
    </div>
  );
}

function FichaLimpaBadge({ status, t }) {
  if (!status) {
    return null;
  }

  const isClean = status.is_clean;
  const badgeClass = isClean ? 'ficha-limpa-clean' : 'ficha-limpa-not-clean';
  const label = isClean ? t('tse_ficha_limpa_clean') : t('tse_ficha_limpa_not_clean');

  return (
    <div className={`gov-data-ficha-limpa-badge ${badgeClass}`}>
      <span className="ficha-limpa-icon">{isClean ? '✓' : '!'}</span>
      <span className="ficha-limpa-label">{label}</span>
      {status.status_description && (
        <span className="ficha-limpa-desc candidate-muted">({status.status_description})</span>
      )}
    </div>
  );
}

function TSEPanel({ slug, tseData, t }) {
  const record = tseData?.candidates?.[slug];
  const p2022 = record?.presidential_2022;
  const disclaimer = tseData?.disclaimer_pt ?? tseData?.disclaimer_en ?? '';

  if (!record) {
    return <p className="candidate-muted">{t('gov_data_loading')}</p>;
  }

  return (
    <div className="gov-data-tse-panel">
      {record.photo_url && (
        <div className="gov-data-photo-container">
          <CandidatePhoto photoUrl={record.photo_url} fullName={record.full_name} />
        </div>
      )}

      <FichaLimpaBadge status={record.ficha_limpa_status} t={t} />

      <DeclaredAssets assets={record.declared_assets} t={t} />

      {p2022 ? (
        <div className="gov-data-result-block">
          <h3>{t('tse_2022_result')}</h3>
          <p>
            <strong>{p2022.nome_urna}</strong> — {p2022.partido} (n.º {p2022.numero})
          </p>
          <p>{t('tse_first_round_pct', { pct: p2022.first_round_pct })}</p>
          {p2022.second_round_pct && (
            <p>{t('tse_second_round_pct', { pct: p2022.second_round_pct })}</p>
          )}
          {p2022.eleito && (
            <span className="gov-data-elected-badge">{t('tse_elected')}</span>
          )}
        </div>
      ) : (
        <p className="candidate-muted">{t('tse_not_ran')}</p>
      )}

      {record.tse_registration_url && (
        <p className="gov-data-registration-link">
          <a
            href={record.tse_registration_url}
            target="_blank"
            rel="noopener noreferrer"
            className="gov-data-source-link"
          >
            {t('tse_link_text')}
          </a>
        </p>
      )}

      {disclaimer && (
        <p className="gov-data-disclaimer candidate-muted">{disclaimer}</p>
      )}
      <p className="gov-data-source-row">
        <a
          href={record.source_url || 'https://divulgacandcontas.tse.jus.br'}
          target="_blank"
          rel="noopener noreferrer"
          className="gov-data-source-link"
        >
          {tseData.source ?? 'TSE DivulgaCandContas'}
        </a>
      </p>
    </div>
  );
}

function TransparenciaPanel({ slug, transData, t }) {
  const record = transData?.candidates?.[slug];
  const disclaimer = transData?.disclaimer_pt ?? transData?.disclaimer_en ?? '';

  if (!record) {
    return <p className="candidate-muted">{t('gov_data_loading')}</p>;
  }

  const pep = record.pep;
  const emendas = record.emendas;

  return (
    <div className="gov-data-trans-panel">
      <div className="gov-data-pep-row">
        <span className={`gov-data-pep-badge${pep?.found ? ' gov-data-pep-badge--found' : ''}`}>
          {pep?.found ? t('pep_found') : t('pep_not_found')}
        </span>
      </div>
      <p className="gov-data-disclaimer candidate-muted">{t('pep_disclaimer')}</p>

      <h3 style={{ marginTop: '1rem' }}>Emendas Parlamentares</h3>
      {emendas?.total_count > 0 ? (
        <div className="gov-data-emendas-summary">
          <p>{t('emendas_count', { count: emendas.total_count })}</p>
          <p>{t('emendas_total_committed', { value: formatBRL(emendas.total_empenhado_brl) })}</p>
          <p>{t('emendas_total_paid', { value: formatBRL(emendas.total_pago_brl) })}</p>
          {emendas.records.length > 0 && (
            <table className="gov-data-emendas-table">
              <thead>
                <tr>
                  <th>Ano</th>
                  <th>Acao</th>
                  <th>Empenhado</th>
                  <th>Pago</th>
                </tr>
              </thead>
              <tbody>
                {emendas.records.slice(0, 10).map((row, i) => (
                  // eslint-disable-next-line react/no-array-index-key
                  <tr key={i}>
                    <td>{row.ano ?? '--'}</td>
                    <td>{row.acao ?? '--'}</td>
                    <td>{formatBRL(row.empenhado_brl)}</td>
                    <td>{formatBRL(row.pago_brl)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      ) : (
        <p className="candidate-muted">{t('no_emendas')}</p>
      )}

      {disclaimer && (
        <p className="gov-data-disclaimer candidate-muted" style={{ marginTop: '0.75rem' }}>{disclaimer}</p>
      )}
      <p className="gov-data-source-row">
        <a
          href={record.source_url || 'https://portaldatransparencia.gov.br'}
          target="_blank"
          rel="noopener noreferrer"
          className="gov-data-source-link"
        >
          {t('gov_data_source_link')}
        </a>
      </p>
    </div>
  );
}

export default function CandidateGovData({ slug }) {
  const { t } = useTranslation('candidates');
  const [activeTab, setActiveTab] = useState('tse');
  const { data: tseData, loading: loadingTse, error: errorTse } = useData('tse_data');
  const { data: transData, loading: loadingTrans, error: errorTrans } = useData('transparencia_data');

  const loading = loadingTse || loadingTrans;
  const error = errorTse || errorTrans;

  if (loading) {
    return (
      <section className="candidate-card">
        <p className="candidate-muted">{t('gov_data_loading')}</p>
      </section>
    );
  }

  if (error) {
    return (
      <section className="candidate-card">
        <p className="candidate-muted">{t('gov_data_error')}</p>
      </section>
    );
  }

  return (
    <section className="candidate-card gov-data-card">
      <div className="gov-data-tabs" role="tablist">
        <button
          role="tab"
          type="button"
          aria-selected={activeTab === 'tse'}
          className={`gov-data-tab-btn${activeTab === 'tse' ? ' active' : ''}`}
          onClick={() => setActiveTab('tse')}
        >
          {t('gov_data_tab_tse')}
        </button>
        <button
          role="tab"
          type="button"
          aria-selected={activeTab === 'transparencia'}
          className={`gov-data-tab-btn${activeTab === 'transparencia' ? ' active' : ''}`}
          onClick={() => setActiveTab('transparencia')}
        >
          {t('gov_data_tab_transparencia')}
        </button>
      </div>

      <div role="tabpanel" className="gov-data-tab-panel">
        {activeTab === 'tse' ? (
          <TSEPanel slug={slug} tseData={tseData} t={t} />
        ) : (
          <TransparenciaPanel slug={slug} transData={transData} t={t} />
        )}
      </div>
    </section>
  );
}
