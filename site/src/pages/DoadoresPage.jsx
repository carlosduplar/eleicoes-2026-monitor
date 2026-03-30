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

function formatNumber(num) {
  if (typeof num !== 'number' || !Number.isFinite(num)) {
    return '—';
  }
  return new Intl.NumberFormat('pt-BR').format(num);
}

function buildCandidateRows(donorsData) {
  if (!donorsData?.candidates) {
    return [];
  }
  return Object.values(donorsData.candidates).map((rec) => ({
    slug: rec.slug,
    sq_candidato: rec.sq_candidato,
    no_2022_race: rec.no_2022_race || false,
    error: rec.error,
    total_donations: rec.summary?.total_donations ?? 0,
    total_amount: rec.summary?.total_amount ?? 0,
    pf_count: rec.summary?.pf_count ?? 0,
    pf_amount: rec.summary?.pf_amount ?? 0,
    pj_count: rec.summary?.pj_count ?? 0,
    pj_amount: rec.summary?.pj_amount ?? 0,
    sector_breakdown: rec.sector_breakdown,
  }));
}

const SORT_KEYS = ['total_amount', 'pf_amount', 'pj_amount', 'total_donations'];

function SortableHeader({ label, sortKey, currentSort, onSort }) {
  const isActive = currentSort.key === sortKey;
  const arrow = isActive ? (currentSort.asc ? ' ▲' : ' ▼') : '';
  return (
    <th>
      <button
        type="button"
        className="doadores-sort-btn"
        onClick={() => onSort(sortKey)}
        aria-sort={isActive ? (currentSort.asc ? 'ascending' : 'descending') : 'none'}
      >
        {label}{arrow}
      </button>
    </th>
  );
}

function SectorBarChart({ sectors, totalAmount, t }) {
  if (!sectors || sectors.length === 0) {
    return (
      <div className="doadores-no-sectors">
        <p className="candidate-muted">{t('doadores_no_sectors')}</p>
      </div>
    );
  }

  const maxAmount = Math.max(...sectors.map((s) => s.total_amount));

  return (
    <div className="doadores-sector-chart">
      <h4>{t('doadores_sector_breakdown')}</h4>
      <div className="sector-bars">
        {sectors.slice(0, 5).map((sector) => {
          const percentage = totalAmount > 0 ? (sector.total_amount / totalAmount) * 100 : 0;
          const barWidth = maxAmount > 0 ? (sector.total_amount / maxAmount) * 100 : 0;

          return (
            <div key={sector.sector_code} className="sector-bar-row">
              <div className="sector-bar-label">
                <span className="sector-name">{sector.sector_name}</span>
                <span className="sector-amount">{formatBRL(sector.total_amount)}</span>
                <span className="sector-percent">({percentage.toFixed(1)}%)</span>
              </div>
              <div className="sector-bar-track">
                <div
                  className="sector-bar-fill"
                  style={{ width: `${barWidth}%` }}
                  aria-label={`${sector.sector_name}: ${formatBRL(sector.total_amount)}`}
                />
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function CandidateDonorTable({ rows, sort, onSort, t }) {
  const sorted = useMemo(() => {
    const copy = [...rows];
    copy.sort((a, b) => {
      const aVal = a[sort.key];
      const bVal = b[sort.key];
      if (typeof aVal === 'number' && typeof bVal === 'number') {
        return sort.asc ? aVal - bVal : bVal - aVal;
      }
      return 0;
    });
    return copy;
  }, [rows, sort]);

  return (
    <table className="doadores-table">
      <thead>
        <tr>
          <th>{t('doadores_col_candidate')}</th>
          <SortableHeader
            label={t('doadores_col_total')}
            sortKey="total_amount"
            currentSort={sort}
            onSort={onSort}
          />
          <SortableHeader
            label={t('doadores_col_pf')}
            sortKey="pf_amount"
            currentSort={sort}
            onSort={onSort}
          />
          <SortableHeader
            label={t('doadores_col_pj')}
            sortKey="pj_amount"
            currentSort={sort}
            onSort={onSort}
          />
          <SortableHeader
            label={t('doadores_col_count')}
            sortKey="total_donations"
            currentSort={sort}
            onSort={onSort}
          />
        </tr>
      </thead>
      <tbody>
        {sorted.map((row) => (
          <tr key={row.slug} className={row.no_2022_race ? 'no-race' : ''}>
            <td>
              <a href={`/candidato/${row.slug}`} className="doadores-candidate-link">
                {row.slug}
              </a>
              {row.no_2022_race && (
                <span className="no-race-badge">{t('doadores_no_2022_race')}</span>
              )}
              {row.error && (
                <span className="error-badge" title={row.error}>!</span>
              )}
            </td>
            <td className="amount-cell">{formatBRL(row.total_amount)}</td>
            <td className="amount-cell">
              {formatBRL(row.pf_amount)}
              <span className="count-sub">({formatNumber(row.pf_count)})</span>
            </td>
            <td className="amount-cell">
              {formatBRL(row.pj_amount)}
              <span className="count-sub">({formatNumber(row.pj_count)})</span>
            </td>
            <td>{formatNumber(row.total_donations)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export default function DoadoresPage() {
  const { t } = useTranslation(['common', 'candidates']);
  const { data: donorsData, loading, error } = useData('donors');
  const [sort, setSort] = useState({ key: 'total_amount', asc: false });
  const [selectedCandidate, setSelectedCandidate] = useState(null);

  const rows = useMemo(() => buildCandidateRows(donorsData), [donorsData]);

  function handleSort(key) {
    setSort((prev) => ({
      key,
      asc: prev.key === key ? !prev.asc : false,
    }));
  }

  const title = t('doadores.title', { ns: 'common' });

  if (loading) {
    return (
      <section className="doadores-page">
        <Helmet>
          <title>{`${title} | ${t('common:brand')}`}</title>
        </Helmet>
        <h1>{title}</h1>
        <p className="candidate-muted">{t('doadores.loading', { ns: 'common' })}</p>
      </section>
    );
  }

  if (error || !donorsData) {
    return (
      <section className="doadores-page">
        <Helmet>
          <title>{`${title} | ${t('common:brand')}`}</title>
        </Helmet>
        <h1>{title}</h1>
        <p className="candidate-muted">{t('doadores.error', { ns: 'common' })}</p>
      </section>
    );
  }

  const selectedRow = rows.find((r) => r.slug === selectedCandidate);

  return (
    <section className="doadores-page">
      <Helmet>
        <title>{`${title} | ${t('common:brand')}`}</title>
        <meta name="description" content={t('doadores.disclaimer', { ns: 'common' })} />
      </Helmet>

      <h1>{title}</h1>
      <p className="doadores-disclaimer candidate-muted">
        {donorsData.disclaimer_pt || donorsData.disclaimer_en || t('doadores.disclaimer', { ns: 'common' })}
      </p>

      <div className="doadores-summary">
        <div className="doadores-stat">
          <span className="stat-value">{formatNumber(donorsData.total_candidates || 0)}</span>
          <span className="stat-label">{t('doadores.stat_candidates', { ns: 'common' })}</span>
        </div>
        <div className="doadores-stat">
          <span className="stat-value">{formatNumber(donorsData.total_donations || 0)}</span>
          <span className="stat-label">{t('doadores.stat_donations', { ns: 'common' })}</span>
        </div>
        <div className="doadores-stat">
          <span className="stat-value">{formatBRL(donorsData.total_amount || 0)}</span>
          <span className="stat-label">{t('doadores.stat_total', { ns: 'common' })}</span>
        </div>
      </div>

      <div className="doadores-table-wrapper">
        <CandidateDonorTable
          rows={rows}
          sort={sort}
          onSort={handleSort}
          t={t}
        />
      </div>

      {selectedRow && selectedRow.sector_breakdown && (
        <div className="doadores-detail-panel">
          <h3>{t('doadores_detail_title', { candidate: selectedRow.slug, ns: 'common' })}</h3>
          <SectorBarChart
            sectors={selectedRow.sector_breakdown.sectors}
            totalAmount={selectedRow.sector_breakdown.total_pj_amount}
            t={t}
          />
        </div>
      )}

      <div className="doadores-sources">
        <p className="candidate-muted">{t('doadores.source_tse', { ns: 'common' })}</p>
        <p className="candidate-muted">{t('doadores.source_brasilapi', { ns: 'common' })}</p>
      </div>
    </section>
  );
}
