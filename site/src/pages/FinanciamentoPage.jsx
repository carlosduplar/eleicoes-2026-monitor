import * as ReactHelmetAsync from 'react-helmet-async';
import { useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';

import { useData } from '@/hooks/useData';

const Helmet = ReactHelmetAsync.Helmet || ReactHelmetAsync.default?.Helmet;

function formatBRL(value) {
  if (typeof value !== 'number' || !Number.isFinite(value) || value === 0) {
    return '—';
  }
  return new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL', maximumFractionDigits: 0 }).format(value);
}

function buildTransRows(transData) {
  if (!transData?.candidates) {
    return [];
  }
  return Object.values(transData.candidates).map((rec) => ({
    slug: rec.slug,
    full_name: rec.full_name,
    pep: rec.pep?.found ?? false,
    emendas_count: rec.emendas?.total_count ?? 0,
    empenhado: rec.emendas?.total_empenhado_brl ?? 0,
    pago: rec.emendas?.total_pago_brl ?? 0,
  }));
}

function buildTseRows(tseData) {
  if (!tseData?.candidates) {
    return [];
  }
  return Object.values(tseData.candidates).map((rec) => ({
    slug: rec.slug,
    full_name: rec.full_name,
    photo_url: rec.photo_url,
    declared_assets: rec.declared_assets?.total_value ?? null,
    assets_count: rec.declared_assets?.count ?? 0,
    ficha_limpa: rec.ficha_limpa_status?.is_clean ?? null,
    tse_url: rec.tse_registration_url,
  }));
}

const TRANS_SORT_KEYS = ['full_name', 'pep', 'emendas_count', 'empenhado', 'pago'];
const TSE_SORT_KEYS = ['full_name', 'declared_assets', 'assets_count', 'ficha_limpa'];

function SortableHeader({ label, sortKey, currentSort, onSort }) {
  const isActive = currentSort.key === sortKey;
  const arrow = isActive ? (currentSort.asc ? ' ▲' : ' ▼') : '';
  return (
    <th>
      <button
        type="button"
        className="financiamento-sort-btn"
        onClick={() => onSort(sortKey)}
        aria-sort={isActive ? (currentSort.asc ? 'ascending' : 'descending') : 'none'}
      >
        {label}{arrow}
      </button>
    </th>
  );
}

function TransparenciaTable({ rows, sort, onSort, t }) {
  const sorted = useMemo(() => {
    const copy = [...rows];
    copy.sort((a, b) => {
      const aVal = a[sort.key];
      const bVal = b[sort.key];
      if (typeof aVal === 'boolean') {
        const diff = (bVal ? 1 : 0) - (aVal ? 1 : 0);
        return sort.asc ? -diff : diff;
      }
      if (typeof aVal === 'number') {
        return sort.asc ? aVal - bVal : bVal - aVal;
      }
      const diff = String(aVal).localeCompare(String(bVal), 'pt-BR');
      return sort.asc ? diff : -diff;
    });
    return copy;
  }, [rows, sort]);

  return (
    <table className="financiamento-table">
      <thead>
        <tr>
          <SortableHeader
            label={t('common:financiamento.col_candidate')}
            sortKey="full_name"
            currentSort={sort}
            onSort={onSort}
          />
          <SortableHeader
            label={t('common:financiamento.col_pep')}
            sortKey="pep"
            currentSort={sort}
            onSort={onSort}
          />
          <SortableHeader
            label={t('common:financiamento.col_emendas')}
            sortKey="emendas_count"
            currentSort={sort}
            onSort={onSort}
          />
          <SortableHeader
            label={t('common:financiamento.col_empenhado')}
            sortKey="empenhado"
            currentSort={sort}
            onSort={onSort}
          />
          <SortableHeader
            label={t('common:financiamento.col_pago')}
            sortKey="pago"
            currentSort={sort}
            onSort={onSort}
          />
        </tr>
      </thead>
      <tbody>
        {sorted.map((row) => (
          <tr key={row.slug}>
            <td>
              <a href={`/candidato/${row.slug}`} className="financiamento-candidate-link">
                {row.full_name}
              </a>
            </td>
            <td>
              <span className={`gov-data-pep-badge${row.pep ? ' gov-data-pep-badge--found' : ''}`}>
                {row.pep ? t('candidates:pep_found') : t('candidates:pep_not_found')}
              </span>
            </td>
            <td>{row.emendas_count > 0 ? row.emendas_count : '—'}</td>
            <td>{formatBRL(row.empenhado)}</td>
            <td>{formatBRL(row.pago)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function TseTable({ rows, sort, onSort, t }) {
  const sorted = useMemo(() => {
    const copy = [...rows];
    copy.sort((a, b) => {
      const aVal = a[sort.key];
      const bVal = b[sort.key];
      if (typeof aVal === 'boolean') {
        const diff = (bVal ? 1 : 0) - (aVal ? 1 : 0);
        return sort.asc ? -diff : diff;
      }
      if (typeof aVal === 'number' && aVal !== null && bVal !== null) {
        return sort.asc ? aVal - bVal : bVal - aVal;
      }
      const diff = String(aVal || '').localeCompare(String(bVal || ''), 'pt-BR');
      return sort.asc ? diff : -diff;
    });
    return copy;
  }, [rows, sort]);

  return (
    <table className="financiamento-table">
      <thead>
        <tr>
          <SortableHeader
            label={t('common:financiamento.col_candidate')}
            sortKey="full_name"
            currentSort={sort}
            onSort={onSort}
          />
          <SortableHeader
            label={t('candidates:tse_col_assets')}
            sortKey="declared_assets"
            currentSort={sort}
            onSort={onSort}
          />
          <SortableHeader
            label={t('candidates:tse_col_assets_count')}
            sortKey="assets_count"
            currentSort={sort}
            onSort={onSort}
          />
          <SortableHeader
            label={t('candidates:tse_col_ficha_limpa')}
            sortKey="ficha_limpa"
            currentSort={sort}
            onSort={onSort}
          />
        </tr>
      </thead>
      <tbody>
        {sorted.map((row) => (
          <tr key={row.slug}>
            <td>
              <div className="financiamento-candidate-cell">
                {row.photo_url && (
                  <img
                    src={row.photo_url}
                    alt=""
                    className="financiamento-candidate-thumb"
                    loading="lazy"
                  />
                )}
                <a href={`/candidato/${row.slug}`} className="financiamento-candidate-link">
                  {row.full_name}
                </a>
              </div>
            </td>
            <td>{formatBRL(row.declared_assets)}</td>
            <td>{row.assets_count > 0 ? row.assets_count : '—'}</td>
            <td>
              {row.ficha_limpa === null ? (
                '—'
              ) : (
                <span className={`ficha-limpa-badge${row.ficha_limpa ? '' : ' not-clean'}`}>
                  {row.ficha_limpa ? t('candidates:tse_ficha_limpa_clean') : t('candidates:tse_ficha_limpa_not_clean')}
                </span>
              )}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export default function FinanciamentoPage() {
  const { t } = useTranslation(['common', 'candidates']);
  const { data: transData, loading: loadingTrans, error: errorTrans } = useData('transparencia_data');
  const { data: tseData, loading: loadingTse, error: errorTse } = useData('tse_data');
  const [activeTab, setActiveTab] = useState('transparencia');
  const [transSort, setTransSort] = useState({ key: 'empenhado', asc: false });
  const [tseSort, setTseSort] = useState({ key: 'declared_assets', asc: false });

  const transRows = useMemo(() => buildTransRows(transData), [transData]);
  const tseRows = useMemo(() => buildTseRows(tseData), [tseData]);

  const loading = loadingTrans || loadingTse;
  const error = errorTrans || errorTse;

  function handleTransSort(key) {
    setTransSort((prev) => ({
      key,
      asc: prev.key === key ? !prev.asc : false,
    }));
  }

  function handleTseSort(key) {
    setTseSort((prev) => ({
      key,
      asc: prev.key === key ? !prev.asc : false,
    }));
  }

  const title = t('common:financiamento.title');

  if (loading) {
    return (
      <section className="financiamento-page">
        <Helmet>
          <title>{`${title} | ${t('common:brand')}`}</title>
        </Helmet>
        <h1>{title}</h1>
        <p className="candidate-muted">{t('common:financiamento.loading')}</p>
      </section>
    );
  }

  if (error || (!transData && !tseData)) {
    return (
      <section className="financiamento-page">
        <Helmet>
          <title>{`${title} | ${t('common:brand')}`}</title>
        </Helmet>
        <h1>{title}</h1>
        <p className="candidate-muted">{t('common:financiamento.error')}</p>
      </section>
    );
  }

  return (
    <section className="financiamento-page">
      <Helmet>
        <title>{`${title} | ${t('common:brand')}`}</title>
        <meta name="description" content={t('common:financiamento.disclaimer')} />
      </Helmet>

      <h1>{title}</h1>
      <p className="financiamento-disclaimer candidate-muted">{t('common:financiamento.disclaimer')}</p>

      <div className="financiamento-tabs" role="tablist">
        <button
          role="tab"
          type="button"
          aria-selected={activeTab === 'transparencia'}
          className={`financiamento-tab-btn${activeTab === 'transparencia' ? ' active' : ''}`}
          onClick={() => setActiveTab('transparencia')}
        >
          {t('candidates:gov_data_tab_transparencia')}
        </button>
        <button
          role="tab"
          type="button"
          aria-selected={activeTab === 'tse'}
          className={`financiamento-tab-btn${activeTab === 'tse' ? ' active' : ''}`}
          onClick={() => setActiveTab('tse')}
        >
          {t('candidates:gov_data_tab_tse')}
        </button>
      </div>

      <div className="financiamento-table-wrapper">
        {activeTab === 'transparencia' ? (
          <TransparenciaTable
            rows={transRows}
            sort={transSort}
            onSort={handleTransSort}
            t={t}
          />
        ) : (
          <TseTable
            rows={tseRows}
            sort={tseSort}
            onSort={handleTseSort}
            t={t}
          />
        )}
      </div>

      <div className="financiamento-sources">
        <p className="candidate-muted">{t('common:financiamento.source_transparencia')}</p>
        <p className="candidate-muted">{t('common:financiamento.source_tse')}</p>
      </div>
    </section>
  );
}
