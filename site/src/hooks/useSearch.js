import { useEffect, useState } from 'react';

/** @typedef {import('../../../docs/schemas/types').Article} Article */

const VERTEX_SEARCH_URL = (import.meta.env.VITE_VERTEX_SEARCH_URL || '').trim();
const MAX_RESULTS = 20;

function toTimestamp(value) {
  const parsed = Date.parse(value || '');
  return Number.isNaN(parsed) ? 0 : parsed;
}

/**
 * Local fallback filter: case-insensitive term matching against
 * article.title, article.summaries["pt-BR"], article.summaries["en-US"],
 * and article.candidates_mentioned[].
 *
 * Returns up to 20 results sorted by published_at descending.
 *
 * @param {string} query - Search terms (space-separated).
 * @param {Article[]} articles - Full article corpus.
 * @returns {Article[]} Filtered and sorted results.
 */
function filterLocal(query, articles) {
  const terms = query
    .toLowerCase()
    .split(/\s+/)
    .map((term) => term.trim())
    .filter(Boolean);

  if (terms.length === 0) {
    return [];
  }

  return (Array.isArray(articles) ? articles : [])
    .filter((article) => {
      const summaries = article?.summaries && typeof article.summaries === 'object' ? article.summaries : {};
      const candidates = Array.isArray(article?.candidates_mentioned) ? article.candidates_mentioned : [];
      const fields = [
        article?.title || '',
        summaries['pt-BR'] || '',
        summaries['en-US'] || '',
        ...candidates.map((candidate) => String(candidate || '')),
      ].map((value) => String(value).toLowerCase());

      return terms.every((term) => fields.some((field) => field.includes(term)));
    })
    .sort((left, right) => toTimestamp(right?.published_at) - toTimestamp(left?.published_at))
    .slice(0, MAX_RESULTS);
}

/**
 * Vertex AI Search API call.
 *
 * @param {string} query - Encoded search query.
 * @param {AbortSignal} signal - AbortController signal for cancellation.
 * @returns {Promise<Article[]>} Results from Vertex Search.
 * @throws {Error} On network failure or non-OK response.
 */
async function searchVertex(query, signal) {
  const url = new URL(VERTEX_SEARCH_URL);
  url.searchParams.set('query', query);
  url.searchParams.set('pageSize', String(MAX_RESULTS));

  const response = await fetch(url.toString(), { signal });
  if (!response.ok) {
    throw new Error(`Vertex request failed: ${response.status}`);
  }

  const payload = await response.json();
  const rawResults = Array.isArray(payload?.results)
    ? payload.results
    : Array.isArray(payload?.documents)
      ? payload.documents
      : [];

  return rawResults
    .map((entry) => {
      const document = entry?.document && typeof entry.document === 'object' ? entry.document : entry;
      if (!document || typeof document !== 'object') {
        return null;
      }
      if (document.struct_data && typeof document.struct_data === 'object') {
        return document.struct_data;
      }
      if (document.structData && typeof document.structData === 'object') {
        return document.structData;
      }
      if (typeof document.title === 'string') {
        return document;
      }
      return null;
    })
    .filter((article) => article && typeof article === 'object')
    .slice(0, MAX_RESULTS);
}

/**
 * useSearch — semantic search with local fallback.
 *
 * If VITE_VERTEX_SEARCH_URL is set, uses Vertex AI Search API.
 * Falls back to client-side filtering if Vertex is unavailable or unconfigured.
 *
 * @param {string} query - Search query string.
 * @param {Article[]} articles - Local article corpus from useData.
 * @returns {{ results: Article[], loading: boolean, error: Error|null, isVertexSearch: boolean }}
 */
const EMPTY_RESULTS = [];

export function useSearch(query, articles) {
  const [results, setResults] = useState(EMPTY_RESULTS);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [isVertexSearch, setIsVertexSearch] = useState(false);

  useEffect(() => {
    const normalizedQuery = typeof query === 'string' ? query.trim() : '';
    if (!normalizedQuery) {
      setResults((prev) => (prev.length === 0 ? prev : EMPTY_RESULTS));
      setLoading(false);
      setError(null);
      setIsVertexSearch(false);
      return undefined;
    }

    if (!VERTEX_SEARCH_URL) {
      setResults(filterLocal(normalizedQuery, articles));
      setLoading(false);
      setError(null);
      setIsVertexSearch(false);
      return undefined;
    }

    const abortController = new AbortController();
    setLoading(true);
    setError(null);
    setIsVertexSearch(true);

    const run = async () => {
      try {
        const vertexResults = await searchVertex(normalizedQuery, abortController.signal);
        if (abortController.signal.aborted) {
          return;
        }
        setResults(vertexResults);
        setLoading(false);
        setError(null);
        setIsVertexSearch(true);
      } catch (_error) {
        if (abortController.signal.aborted) {
          return;
        }
        setResults(filterLocal(normalizedQuery, articles));
        setLoading(false);
        setError(null);
        setIsVertexSearch(false);
      }
    };

    void run();
    return () => {
      abortController.abort();
    };
  }, [articles, query]);

  return { results, loading, error, isVertexSearch };
}

