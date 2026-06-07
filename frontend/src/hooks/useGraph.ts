/**
 * useGraph — fetches /api/graph (optionally member-aware) and memoizes the result.
 *
 * When memberId changes, refetches with the new member's filtering annotations.
 * The graph payload is memoized for the current memberId.
 */

import { useState, useEffect, useRef } from "react";
import type { GraphPayload } from "../lib/api";
import { fetchGraph } from "../lib/api";

export interface UseGraphResult {
  payload: GraphPayload | null;
  isLoading: boolean;
  error: string | null;
  refetch: () => void;
}

export function useGraph(memberId?: string | null): UseGraphResult {
  const [payload, setPayload] = useState<GraphPayload | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fetchKey = useRef(0);

  const load = () => {
    const key = ++fetchKey.current;
    setIsLoading(true);
    setError(null);

    fetchGraph(memberId)
      .then((data) => {
        if (fetchKey.current !== key) return; // stale
        setPayload(data);
      })
      .catch((err) => {
        if (fetchKey.current !== key) return;
        setError(err instanceof Error ? err.message : String(err));
      })
      .finally(() => {
        if (fetchKey.current === key) setIsLoading(false);
      });
  };

  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(load, [memberId]);

  return { payload, isLoading, error, refetch: load };
}
