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

function buildRows(transData) {
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

const SORT_KEYS = ['full_name', 'pep', 'emendas_count', 'empenhado', 'pago'];

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

export default function FinanciamentoPage() {
  const { t } = useTranslation(['common', 'candidates']);
  const { data: transData, loading, error } = useData('transparencia_data');
  const [sort, setSort] = useState({ key: 'empenhado', asc: false });

  const rows = useMemo(() => buildRows(transData), [transData]);

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

  function handleSort(key) {
    setSort((prev) => ({
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

  if (error || !transData) {
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

      <div className="financiamento-table-wrapper">
        <table className="financiamento-table">
          <thead>
            <tr>
              <SortableHeader
                label={t('common:financiamento.col_candidate')}
                sortKey="full_name"
                currentSort={sort}
                onSort={handleSort}
              />
              <SortableHeader
                label={t('common:financiamento.col_pep')}
                sortKey="pep"
                currentSort={sort}
                onSort={handleSort}
              />
              <SortableHeader
                label={t('common:financiamento.col_emendas')}
                sortKey="emendas_count"
                currentSort={sort}
                onSort={handleSort}
              />
              <SortableHeader
                label={t('common:financiamento.col_empenhado')}
                sortKey="empenhado"
                currentSort={sort}
                onSort={handleSort}
              />
              <SortableHeader
                label={t('common:financiamento.col_pago')}
                sortKey="pago"
                currentSort={sort}
                onSort={handleSort}
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
      </div>

      <div className="financiamento-sources">
        <p className="candidate-muted">{t('common:financiamento.source_transparencia')}</p>
        <p className="candidate-muted">{t('common:financiamento.source_tse')}</p>
      </div>
    </section>
  );
}
