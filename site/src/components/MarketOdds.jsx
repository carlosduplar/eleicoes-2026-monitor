import { useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import {
  CartesianGrid,
  LineChart,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';

import { useData } from '@/hooks/useData';
import { CANDIDATE_COLORS } from '@/utils/candidateColors';

import MethodologyBadge from './MethodologyBadge';

const CANDIDATE_LABELS = {
  lula: 'Lula',
  'flavio-bolsonaro': 'Flávio Bolsonaro',
  'renan-santos': 'Renan Santos',
  caiado: 'Ronaldo Caiado',
  'augusto-cury': 'Augusto Cury',
  zema: 'Romeu Zema',
  'edmilson-costa': 'Edmilson Costa',
  'hertz-dias': 'Hertz Dias',
  'samara-martins': 'Samara Martins',
  'wilson-grassi': 'Wilson Grassi',
  'clariana-barao': 'Clariana Barão',
  'rui-costa-pimenta': 'Rui Costa Pimenta',
  'pablo-marcal': 'Pablo Marçal',
};

function formatLastUpdated(isoString) {
  if (!isoString) return '';
  const date = new Date(isoString);
  if (Number.isNaN(date.valueOf())) return '';
  const pad = (n) => String(n).padStart(2, '0');
  const h = pad(date.getUTCHours());
  const m = pad(date.getUTCMinutes());
  const d = pad(date.getUTCDate());
  const mo = pad(date.getUTCMonth() + 1);
  return `${d}/${mo} ${h}:${m} UTC`;
}

/**
 * @typedef {{ last_updated?: string, series?: Array<Record<string, number | string>> }} MarketsHistory
 */

function normalizeHistoryPayload(payload) {
  if (!payload || typeof payload !== 'object' || !Array.isArray(payload.series)) {
    return [];
  }
  return payload.series.filter(
    (row) => row && typeof row === 'object' && typeof row.date === 'string',
  );
}

function getHistoryCandidates(rows) {
  const seen = new Set();
  for (const row of rows) {
    for (const key of Object.keys(row)) {
      if (key !== 'date' && typeof row[key] === 'number') {
        seen.add(key);
      }
    }
  }
  return Array.from(seen);
}

function formatHistoryDateLabel(dateIso, locale) {
  const day = dateIso.slice(8, 10);
  const month = dateIso.slice(5, 7);
  return locale.startsWith('en') ? `${month}/${day}` : `${day}/${month}`;
}

function buildHistoryRows(rows, locale) {
  return rows.map((row) => {
    const { date, ...values } = row;
    return { dateLabel: formatHistoryDateLabel(date, locale), ...values };
  });
}

function MarketHistoryChart({ mounted, rows, candidates, locale, t }) {
  if (!mounted || rows.length === 0 || candidates.length === 0) {
    return <div className="chart-boot-placeholder" style={{ width: '100%', height: 360 }} aria-hidden="true" />;
  }

  const chartRows = buildHistoryRows(rows, locale);

  return (
    <div style={{ width: '100%', height: 360 }}>
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={chartRows} margin={{ top: 12, right: 20, bottom: 12, left: 0 }}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="dateLabel" />
          <YAxis
            domain={[0, 100]}
            label={{ value: t?.('markets.probability_label') ?? 'Probabilidade (%)', angle: -90, position: 'insideLeft' }}
            tickFormatter={(v) => `${v}%`}
          />
          <Tooltip formatter={(value, name) => [`${value}%`, name]} />
          {candidates.map((slug) => (
            <Line
              key={slug}
              type="monotone"
              dataKey={slug}
              name={CANDIDATE_LABELS[slug] || slug}
              stroke={CANDIDATE_COLORS[slug] || '#4A5568'}
              strokeWidth={2}
              dot={chartRows.length < 10}
              connectNulls
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

function MarketOdds() {
  const { t, i18n } = useTranslation ? useTranslation('common') : { t: (k) => k, i18n: { language: 'pt-BR' } };
  const { data: historyData, loading, error } = useData('markets_history');
  const [chartMounted, setChartMounted] = useState(false);
  useEffect(() => {
    setChartMounted(true);
  }, []);
  const locale = i18n?.language === 'en-US' ? 'en-US' : 'pt-BR';
  const historyRows = useMemo(() => normalizeHistoryPayload(historyData), [historyData]);
  const historyCandidates = useMemo(() => getHistoryCandidates(historyRows), [historyRows]);

  if (loading) {
    return (
      <section className="sentiment-stack">
        <article className="feed-state-card">{t?.('markets.loading') ?? 'Carregando odds...'}</article>
        <MethodologyBadge />
      </section>
    );
  }

  if (error) {
    return (
      <section className="sentiment-stack">
        <article className="feed-state-card">{t?.('markets.error') ?? 'Erro ao carregar odds.'}</article>
        <MethodologyBadge />
      </section>
    );
  }

  if (historyRows.length === 0 || historyCandidates.length === 0) {
    return (
      <section className="sentiment-stack">
        <article className="feed-state-card">{t?.('markets.empty') ?? 'Sem dados de mercados disponiveis.'}</article>
        <MethodologyBadge />
      </section>
    );
  }

  const updated = historyData && typeof historyData === 'object' ? historyData.last_updated : '';
  const lastUpdated = formatLastUpdated(updated);

  return (
    <section className="sentiment-stack">
      <article className="sentiment-card">
        <div className="sentiment-head">
          <h1>{t?.('markets.history_title') ?? 'Probabilidade histórica'}</h1>
          {lastUpdated && (
            <span className="sentiment-updated">
              {t?.('markets.last_updated') ?? 'Atualizado'} {lastUpdated}
            </span>
          )}
        </div>
        <MarketHistoryChart
          mounted={chartMounted}
          rows={historyRows}
          candidates={historyCandidates}
          locale={locale}
          t={t}
        />
        <p className="sentiment-disclaimer">
          {t?.('markets.source') ?? 'Fonte'} <a href="https://polymarket.com" target="_blank" rel="noopener noreferrer">Polymarket</a>
          {' | '}
          {t?.('markets.disclaimer') ?? 'Precos implicam probabilidades e nao representam intencoes de voto. Use com cautela.'}
        </p>
      </article>
      <MethodologyBadge />
    </section>
  );
}

export default MarketOdds;
