/**
 * useExercises — fetches GET /api/exercises with optional search + member_id.
 *
 * Supports:
 *   - Debounced search (250 ms) to avoid hammering the backend on keystroke.
 *   - Member-aware contraindication annotation (passes ?member_id=).
 *   - Refetch when memberId or searchTerm changes.
 */

import { useState, useEffect, useRef } from "react";
import { fetchExercises, type ExerciseItem } from "../lib/api";

interface UseExercisesResult {
  exercises: ExerciseItem[];
  loading: boolean;
  error: string | null;
}

export function useExercises(
  memberId: string | null,
  searchTerm: string
): UseExercisesResult {
  const [exercises, setExercises] = useState<ExerciseItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Debounce timer ref
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    // Cancel pending debounce
    if (timerRef.current !== null) {
      clearTimeout(timerRef.current);
    }

    timerRef.current = setTimeout(async () => {
      setLoading(true);
      setError(null);
      try {
        const result = await fetchExercises({
          search: searchTerm || undefined,
          memberId: memberId ?? undefined,
        });
        setExercises(result.exercises);
      } catch (err) {
        setError(err instanceof Error ? err.message : String(err));
      } finally {
        setLoading(false);
      }
    }, 250);

    return () => {
      if (timerRef.current !== null) clearTimeout(timerRef.current);
    };
  }, [memberId, searchTerm]);

  return { exercises, loading, error };
}
