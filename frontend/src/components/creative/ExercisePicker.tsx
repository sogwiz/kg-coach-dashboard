/**
 * ExercisePicker — browse and search the exercise catalog to add exercises
 * to the Creative Canvas.
 *
 * Fetches GET /api/exercises with optional ?search= and ?member_id=.
 * Exercises flagged contraindicated:true show a warning indicator.
 */

import { useState } from "react";
import { useExercises } from "../../hooks/useExercises";
import type { ExerciseItem } from "../../lib/api";

interface ExercisePickerProps {
  memberId: string | null;
  onAdd: (exercise: ExerciseItem) => void;
}

export function ExercisePicker({ memberId, onAdd }: ExercisePickerProps) {
  const [search, setSearch] = useState("");
  const { exercises, loading, error } = useExercises(memberId, search);

  return (
    <div className="flex flex-col gap-3">
      {/* Search input */}
      <div className="relative">
        <input
          type="text"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search exercises…"
          className="w-full text-sm border border-slate-200 rounded-lg px-3 py-2 pr-8 focus:outline-none focus:ring-2 focus:ring-indigo-300 placeholder:text-slate-300"
        />
        {search && (
          <button
            type="button"
            onClick={() => setSearch("")}
            className="absolute right-2 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 text-xs"
          >
            ✕
          </button>
        )}
      </div>

      {/* Status */}
      {error && (
        <p className="text-xs text-red-500 px-1">{error}</p>
      )}
      {loading && (
        <p className="text-xs text-slate-400 px-1">Loading exercises…</p>
      )}

      {/* Exercise list */}
      {!loading && !error && (
        <div className="flex flex-col gap-1 max-h-80 overflow-y-auto pr-1">
          {exercises.length === 0 ? (
            <p className="text-xs text-slate-400 px-1 py-2 text-center">
              No exercises found{search ? ` for "${search}"` : ""}.
            </p>
          ) : (
            exercises.map((ex) => (
              <ExercisePickerRow
                key={ex.id}
                exercise={ex}
                onAdd={() => onAdd(ex)}
              />
            ))
          )}
        </div>
      )}

      {!loading && exercises.length > 0 && (
        <p className="text-[10px] text-slate-400 text-right">
          {exercises.length} exercise{exercises.length !== 1 ? "s" : ""}
          {memberId ? " (member-aware)" : ""}
        </p>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Row
// ---------------------------------------------------------------------------

interface ExercisePickerRowProps {
  exercise: ExerciseItem;
  onAdd: () => void;
}

function ExercisePickerRow({ exercise, onAdd }: ExercisePickerRowProps) {
  return (
    <div
      className={`flex items-start gap-2 rounded-lg px-3 py-2 border transition-colors ${
        exercise.contraindicated
          ? "border-amber-200 bg-amber-50"
          : "border-transparent hover:border-slate-200 hover:bg-slate-50"
      }`}
    >
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-1.5 flex-wrap">
          <span className="text-xs font-semibold text-slate-800">
            {exercise.name}
          </span>
          {exercise.contraindicated && (
            <span className="text-[10px] font-bold px-1.5 py-0.5 rounded-full bg-amber-100 text-amber-700 border border-amber-300">
              ⚠ contraindicated
            </span>
          )}
        </div>
        {exercise.movement_patterns.length > 0 && (
          <p className="text-[10px] text-slate-400 mt-0.5 truncate">
            {exercise.movement_patterns.slice(0, 3).join(" · ")}
          </p>
        )}
        {exercise.muscle_groups.length > 0 && (
          <p className="text-[10px] text-slate-400 truncate">
            {exercise.muscle_groups.slice(0, 3).join(", ")}
          </p>
        )}
      </div>
      <button
        type="button"
        onClick={onAdd}
        className="flex-shrink-0 text-xs font-semibold text-indigo-600 hover:text-indigo-800 px-2 py-1 rounded-lg hover:bg-indigo-50 transition-colors"
      >
        + Add
      </button>
    </div>
  );
}
