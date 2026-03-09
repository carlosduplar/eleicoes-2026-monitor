import { useEffect, useState } from 'react';

const memoryCache = new Map();

export function useData(filename) {
  const [data, setData] = useState(() => memoryCache.get(filename) ?? null);
  const [loading, setLoading] = useState(!memoryCache.has(filename));
  const [error, setError] = useState(null);

  useEffect(() => {
    if (memoryCache.has(filename)) {
      setData(memoryCache.get(filename));
      setLoading(false);
      return undefined;
    }

    let disposed = false;

    const load = async () => {
      setLoading(true);
      setError(null);
      try {
        const response = await fetch(`/data/${filename}.json`);
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
