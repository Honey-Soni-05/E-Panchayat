/**
 * Small data-fetching hooks.
 *
 * Deliberately not a library — the app needs three things: fetch on mount,
 * expose loading and error states, and refetch after a mutation. What matters
 * is that `error` is surfaced in the UI rather than warned to a console, which
 * is how the old sync failures stayed invisible for so long.
 */

import { useCallback, useEffect, useRef, useState } from 'react';

import { ApiError } from './api';

export const errorMessage = (err: unknown): string => {
  if (err instanceof ApiError) return err.message;
  if (err instanceof Error) return err.message;
  return 'Something went wrong.';
};

interface QueryState<T> {
  data: T | null;
  loading: boolean;
  error: string | null;
  refetch: () => void;
}

/**
 * Runs `fetcher` on mount and whenever `deps` change.
 * Pass a stable dependency array, exactly like useEffect.
 */
export function useQuery<T>(fetcher: () => Promise<T>, deps: unknown[] = []): QueryState<T> {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [tick, setTick] = useState(0);

  // Keeps the latest fetcher without making it a dependency, so callers can
  // pass an inline arrow function without causing an infinite loop.
  const fetcherRef = useRef(fetcher);
  fetcherRef.current = fetcher;

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);

    fetcherRef
      .current()
      .then((result) => {
        if (!cancelled) setData(result);
      })
      .catch((err) => {
        if (!cancelled) setError(errorMessage(err));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, tick]);

  const refetch = useCallback(() => setTick((n) => n + 1), []);

  return { data, loading, error, refetch };
}

interface MutationState<TArgs extends unknown[], TResult> {
  run: (...args: TArgs) => Promise<TResult | null>;
  saving: boolean;
  error: string | null;
  clearError: () => void;
}

/**
 * Wraps a write. `run` resolves to the result, or null when it failed —
 * the error is in `error` either way, so a component can render it.
 */
export function useMutation<TArgs extends unknown[], TResult>(
  action: (...args: TArgs) => Promise<TResult>,
  onSuccess?: (result: TResult) => void,
): MutationState<TArgs, TResult> {
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const actionRef = useRef(action);
  actionRef.current = action;
  const successRef = useRef(onSuccess);
  successRef.current = onSuccess;

  const run = useCallback(async (...args: TArgs): Promise<TResult | null> => {
    setSaving(true);
    setError(null);
    try {
      const result = await actionRef.current(...args);
      successRef.current?.(result);
      return result;
    } catch (err) {
      setError(errorMessage(err));
      return null;
    } finally {
      setSaving(false);
    }
  }, []);

  return { run, saving, error, clearError: () => setError(null) };
}
