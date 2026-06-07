/**
 * useInjury — injury state management for a single member + injury.
 *
 * Fetches the 14-day history and exposes a checkIn action.
 * needsCheckIn is true when no check-in has been recorded today.
 */

import { useState, useEffect, useCallback } from "react";
import {
  fetchMember,
  fetchInjuryHistory,
  postInjuryCheckIn,
  type Injury,
  type InjuryState,
  type InjuryStateCreate,
} from "../lib/api";

interface UseInjuryResult {
  injury: Injury | null;
  currentState: InjuryState | null;
  history: InjuryState[];
  checkIn: (state: InjuryStateCreate) => Promise<void>;
  needsCheckIn: boolean;
  isLoading: boolean;
  error: string | null;
  refresh: () => void;
}

function isToday(isoDateStr: string): boolean {
  const d = new Date(isoDateStr);
  const today = new Date();
  return (
    d.getFullYear() === today.getFullYear() &&
    d.getMonth() === today.getMonth() &&
    d.getDate() === today.getDate()
  );
}

export function useInjury(
  memberId: string | null,
  injuryId: string | null
): UseInjuryResult {
  const [injury, setInjury] = useState<Injury | null>(null);
  const [history, setHistory] = useState<InjuryState[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [refreshKey, setRefreshKey] = useState(0);

  const refresh = useCallback(() => setRefreshKey((k) => k + 1), []);

  // Load injury metadata from the member context
  useEffect(() => {
    if (!memberId || !injuryId) return;
    let cancelled = false;

    setIsLoading(true);
    setError(null);

    Promise.all([
      fetchMember(memberId),
      fetchInjuryHistory(memberId, injuryId, 14),
    ])
      .then(([member, hist]) => {
        if (cancelled) return;
        const found = member.injuries.find((i) => i.id === injuryId) ?? null;
        setInjury(found);
        setHistory(hist);
      })
      .catch((err) => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Failed to load injury");
        }
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [memberId, injuryId, refreshKey]);

  const checkIn = useCallback(
    async (state: InjuryStateCreate) => {
      if (!memberId || !injuryId) return;
      const newState = await postInjuryCheckIn(memberId, injuryId, state);
      setHistory((prev) => [newState, ...prev]);
      setInjury((prev) =>
        prev
          ? { ...prev, states: [newState, ...prev.states] }
          : prev
      );
    },
    [memberId, injuryId]
  );

  // Compute derived values
  const allStates = [
    ...(injury?.states ?? []),
    ...history,
  ];

  // Deduplicate by recorded_at, newest first
  const seen = new Set<string>();
  const dedupedStates = allStates
    .filter((s) => {
      if (seen.has(s.recorded_at)) return false;
      seen.add(s.recorded_at);
      return true;
    })
    .sort(
      (a, b) =>
        new Date(b.recorded_at).getTime() - new Date(a.recorded_at).getTime()
    );

  const currentState = dedupedStates[0] ?? null;
  const needsCheckIn = !dedupedStates.some((s) => isToday(s.recorded_at));

  return {
    injury,
    currentState,
    history: dedupedStates,
    checkIn,
    needsCheckIn,
    isLoading,
    error,
    refresh,
  };
}
