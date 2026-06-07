/**
 * useMembers — fetches the member list and seeds the active-member context.
 *
 * Called once at dashboard mount.  The active-member context is the shared
 * source of truth used by all other hooks and panels.
 */

import { useEffect, useState } from "react";
import { fetchMembers } from "../lib/api";
import { useActiveMember } from "../state/activeMember";

interface UseMembersResult {
  isLoading: boolean;
  error: string | null;
}

export function useMembers(): UseMembersResult {
  const { setMembers } = useActiveMember();
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setIsLoading(true);
    fetchMembers()
      .then((list) => {
        if (!cancelled) {
          setMembers(list);
          setError(null);
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Failed to load members");
        }
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [setMembers]);

  return { isLoading, error };
}
