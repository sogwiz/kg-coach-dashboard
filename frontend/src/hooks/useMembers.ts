/**
 * useMembers — fetches the member list and seeds the active-member context.
 *
 * Called once at dashboard mount.  The active-member context is the shared
 * source of truth used by all other hooks and panels.
 */

import { useEffect, useState, useCallback } from "react";
import { fetchMembers } from "../lib/api";
import { useActiveMember } from "../state/activeMember";

interface UseMembersResult {
  isLoading: boolean;
  error: string | null;
  refresh: () => Promise<void>;
}

export function useMembers(): UseMembersResult {
  const { setMembers } = useActiveMember();
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadMembers = useCallback(async () => {
    setIsLoading(true);
    try {
      const list = await fetchMembers();
      setMembers(list);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load members");
    } finally {
      setIsLoading(false);
    }
  }, [setMembers]);

  useEffect(() => {
    loadMembers();
  }, [loadMembers]);

  const refresh = useCallback(async () => {
    await loadMembers();
  }, [loadMembers]);

  return { isLoading, error, refresh };
}
