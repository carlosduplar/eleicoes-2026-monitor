import { useEffect, useState } from 'react';

import { getInitialData } from '@/utils/bootData';

const memoryCache = new Map();
const buildDataUrl = (filename) => {
  const encodedFilename = encodeURIComponent(filename);
  if (import.meta.env.DEV) {
    return `/data/${encodedFilename}.json`;
  }
  return `${import.meta.env.BASE_URL}data/${encodedFilename}.json`;
};

export function useData(filename) {
  const initialData = getInitialData(filename);
  const [data, setData] = useState(() => memoryCache.get(filename) ?? initialData ?? null);
  const [loading, setLoading] = useState(() => !memoryCache.has(filename) && initialData === undefined);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (memoryCache.has(filename)) {
      setData(memoryCache.get(filename));
      setLoading(false);
      return undefined;
    }

    // Boot data is already rendered server-side. Other datasets are final;
    // articles only get a silent background refresh for the full corpus.
    if (initialData !== undefined) {
      if (filename !== 'articles') {
        setLoading(false);
        return undefined;
      }
      let refreshing = false;
      const load = async () => {
        try {
          const response = await fetch(buildDataUrl(filename));
          if (!response.ok || refreshing) {
            return;
          }
          const payload = await response.json();
          memoryCache.set(filename, payload);
          if (!refreshing) {
            setData(payload);
          }
        } catch {
          // Keep boot data on refresh failure.
        }
      };
      void load();
      return () => {
        refreshing = true;
      };
    }

    let disposed = false;

    const load = async () => {
      setLoading(true);
      setError(null);
      try {
        const response = await fetch(buildDataUrl(filename));
        if (!response.ok) {
          throw new Error(`Request failed: ${response.status}`);
        }
        const payload = await response.json();
        memoryCache.set(filename, payload);
        if (!disposed) {
          setData(payload);
          setLoading(false);
        }
      } catch (fetchError) {
        if (!disposed) {
          setError(fetchError);
          setLoading(false);
        }
      }
    };

    void load();
    return () => {
      disposed = true;
    };
  }, [filename]);

  return { data, loading, error };
}
