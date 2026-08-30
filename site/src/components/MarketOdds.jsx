import { useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import {
  BarChart,
  Bar,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';

import { useData } from '@/hooks/useData';
import { CANDIDATE_COLORS } from '@/utils/candidateColors';

import MethodologyBadge from './MethodologyBadge';

/**
 * @typedef {{
 *   id: string,
 *   slug: string,
 *   question: string,
 *   yes_price: number,
 *   no_price: number,
 *   volume: number,
 *   liquidity?: number,
 *   market_url: string,
 *   collected_at: string
 * }} Market
 * @typedef {{ slug: string, label: string, probability: number, color: string }} MarketRow
 */

const CANDIDATE_SLUGS = [
  'lula',
  'flavio-bolsonaro',
  'tarcisio',
  'caiado',
  'zema',
  'ratinho-jr',
  'eduardo-leite',
  'aldo-rebelo',
  'renan-santos',
];

const CANDIDATE_LABELS = {
  lula: 'Lula',
  'flavio-bolsonaro': 'Flávio Bolsonaro',
  tarcisio: 'Tarcísio',
  caiado: 'Caiado',
  zema: 'Zema',
  'ratinho-jr': 'Ratinho Jr',
  'eduardo-leite': 'Eduardo Leite',
  'aldo-rebelo': 'Aldo Rebelo',
  'renan-santos': 'Renan Santos',
};

function stripAccents(value) {
  return value.normalize('NFD').replace(/[\u0300-\u036f]/g, '');
}

function normalizeForMatch(value) {
  return stripAccents(value.toLowerCase());
}

function normalizeMarketPayload(payload) {
  const items = Array.isArray(payload) ? payload : payload?.markets;
  if (!Array.isArray(items)) {
    return [];
  }

  return items.filter(
    (item) =>
      item &&
      typeof item === 'object' &&
      typeof item.yes_price === 'number' &&
      typeof item.id === 'string',
  );
}

function parseCandidateFromQuestion(question) {
  const lower = normalizeForMatch(question);
  // Alias for Ratinho naming variance (Polymarket uses "Ratinho Júnior" vs slug "ratinho-jr")
  if (lower.includes('ratinho') && (lower.includes('junior') || lower.includes('jr'))) {
    return 'ratinho-jr';
  }
  for (const slug of CANDIDATE_SLUGS) {
    const name = normalizeForMatch(slug.replace(/-/g, ' '));
    const parts = name.split(' ');
    if (parts.every((p) => lower.includes(p))) {
      return slug;
    }
  }
  return null;
}

function buildChartRows(markets) {
  const byCandidate = {};
  for (const market of markets) {
    const slug = parseCandidateFromQuestion(market.question);
    if (!slug) continue;
    if (!byCandidate[slug]) {
      byCandidate[slug] = { count: 0, total: 0 };
    }
    byCandidate[slug].count += 1;
    byCandidate[slug].total += market.yes_price;
  }

  return Object.entries(byCandidate)
    .map(([slug, data]) => ({
      slug,
      label: CANDIDATE_LABELS[slug] || slug.replace(/-/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase()),
      probability: Math.round((data.total / data.count) * 100),
      color: CANDIDATE_COLORS[slug] || '#4A5568',
    }))
    .sort((a, b) => b.probability - a.probability);
}

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

function MarketOdds() {
  const { t, i18n } = useTranslation ? useTranslation('common') : { t: (k) => k, i18n: { language: 'pt-BR' } };
  const { data, loading, error } = useData('markets');
  const [chartMounted, setChartMounted] = useState(false);
  useEffect(() => {
    setChartMounted(true);
  }, []);
  const markets = useMemo(() => normalizeMarketPayload(data), [data]);
  const chartRows = useMemo(() => buildChartRows(markets), [markets]);
  const lastUpdated = useMemo(() => {
    const wrapped = Array.isArray(data) ? null : data;
    if (wrapped && typeof wrapped.last_updated === 'string') {
      return formatLastUpdated(wrapped.last_updated);
    }
    if (markets.length === 0) return '';
    const newest = markets.reduce((latest, item) => {
      const ts = item.collected_at;
      if (!ts) return latest;
      return !latest || ts > latest ? ts : latest;
    }, '');
    return formatLastUpdated(newest);
  }, [data, markets]);

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

  if (markets.length === 0 || chartRows.length === 0) {
    return (
      <section className="sentiment-stack">
        <article className="feed-state-card">{t?.('markets.empty') ?? 'Sem dados de mercados disponiveis.'}</article>
        <MethodologyBadge />
      </section>
    );
  }

  return (
    <section className="sentiment-stack">
      <article className="sentiment-card">
        <div className="sentiment-head">
          <h1>{t?.('markets.title') ?? 'Odds dos Mercados'}</h1>
          {lastUpdated && (
            <span className="sentiment-updated">
              {t?.('markets.last_updated') ?? 'Atualizado'} {lastUpdated}
            </span>
          )}
        </div>
        {chartMounted ? (
          <div style={{ width: '100%', height: 400 }}>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={chartRows} margin={{ top: 12, right: 20, bottom: 12, left: 0 }}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="label" />
                <YAxis
                  domain={[0, 100]}
                  label={{ value: t?.('markets.probability_label') ?? 'Probabilidade (%)', angle: -90, position: 'insideLeft' }}
                  tickFormatter={(v) => `${v}%`}
                />
                <Tooltip
                  formatter={(value) => [`${value}%`, t?.('markets.probability') ?? 'Probabilidade']}
                />
                <Bar dataKey="probability" radius={[4, 4, 0, 0]}>
                  {chartRows.map((row) => (
                    <Cell key={row.slug} fill={row.color} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        ) : (
          <div className="chart-boot-placeholder" style={{ width: '100%', height: 400 }} aria-hidden="true" />
        )}
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