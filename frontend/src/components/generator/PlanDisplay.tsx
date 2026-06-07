/**
 * PlanDisplay — renders a structured WorkoutPlan.
 *
 * Shows:
 *  - Session-level header: stimulus / target_adaptation / sequence_logic narrative
 *  - Warmup / Main / Cooldown as ordered lists (sorted by exercise.order)
 *  - Each exercise: sets/reps/rest, sequencing_role chip, rationale, expandable
 *    "why here" (sequencing_rationale)
 *  - Connector arrows between consecutive exercises to reinforce order
 *  - Intensity-cap badge when load_tolerance_pct < 1 (from provenance)
 */

import { useState } from "react";
import type { WorkoutPlan, PlannedExercise, SequencingRole } from "../../lib/api";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const ROLE_COLOR: Record<SequencingRole, string> = {
  activation:  "bg-sky-100 text-sky-700",
  primer:      "bg-violet-100 text-violet-700",
  compound:    "bg-indigo-100 text-indigo-700",
  accessory:   "bg-slate-100 text-slate-600",
  conditioning:"bg-orange-100 text-orange-700",
  cooldown:    "bg-green-100 text-green-700",
};

const ROLE_LABEL: Record<SequencingRole, string> = {
  activation:  "Activation",
  primer:      "Primer",
  compound:    "Compound",
  accessory:   "Accessory",
  conditioning:"Conditioning",
  cooldown:    "Cooldown",
};

function formatRepsOrDuration(ex: PlannedExercise): string {
  if (ex.reps != null) return `${ex.sets} × ${ex.reps} reps`;
  if (ex.duration_seconds != null) {
    const s = ex.duration_seconds;
    return s >= 60
      ? `${ex.sets} × ${Math.floor(s / 60)}m${s % 60 > 0 ? `${s % 60}s` : ""}`
      : `${ex.sets} × ${s}s`;
  }
  return `${ex.sets} sets`;
}

function formatRest(sec: number): string {
  if (sec === 0) return "no rest";
  if (sec < 60) return `${sec}s rest`;
  const m = Math.floor(sec / 60);
  const s = sec % 60;
  return s > 0 ? `${m}m${s}s rest` : `${m}m rest`;
}

// ---------------------------------------------------------------------------
// ExerciseCard
// ---------------------------------------------------------------------------

interface ExerciseCardProps {
  exercise: PlannedExercise;
  loadCapPct: number;  // 1.0 = no cap
  isLast: boolean;
}

function ExerciseCard({ exercise: ex, loadCapPct, isLast }: ExerciseCardProps) {
  const [expanded, setExpanded] = useState(false);
  const isLoadCapped = loadCapPct < 1.0 && ex.sequencing_role === "compound";

  return (
    <li className="relative">
      <div className="flex gap-3 rounded-xl border border-slate-200 bg-white p-4 hover:border-slate-300 transition-colors">
        {/* Order number */}
        <div className="flex-shrink-0 w-7 h-7 rounded-full bg-indigo-50 flex items-center justify-center">
          <span className="text-xs font-bold text-indigo-600">{ex.order}</span>
        </div>

        <div className="flex-1 min-w-0">
          {/* Name row */}
          <div className="flex flex-wrap items-start gap-2 mb-1.5">
            <h5 className="font-semibold text-sm text-slate-800 leading-tight">
              {ex.name}
            </h5>
            <span
              className={`text-xs font-medium px-2 py-0.5 rounded-full ${ROLE_COLOR[ex.sequencing_role]}`}
            >
              {ROLE_LABEL[ex.sequencing_role]}
            </span>
            {isLoadCapped && (
              <span className="text-xs font-medium px-2 py-0.5 rounded-full bg-amber-100 text-amber-700">
                Load cap {Math.round(loadCapPct * 100)}%
              </span>
            )}
          </div>

          {/* Sets / reps / rest */}
          <p className="text-xs text-slate-500 mb-2">
            {formatRepsOrDuration(ex)}
            {" · "}
            {formatRest(ex.rest_seconds)}
          </p>

          {/* Rationale */}
          {ex.rationale && (
            <p className="text-xs text-slate-600 leading-relaxed mb-2">
              {ex.rationale}
            </p>
          )}

          {/* Expandable sequencing rationale */}
          {ex.sequencing_rationale && (
            <div>
              <button
                type="button"
                onClick={() => setExpanded((v) => !v)}
                className="text-xs text-indigo-500 hover:text-indigo-700 font-medium flex items-center gap-1 transition-colors"
              >
                {expanded ? "Hide" : "Why here?"}
                <span
                  className={`transition-transform duration-200 ${expanded ? "rotate-180" : ""}`}
                >
                  v
                </span>
              </button>
              {expanded && (
                <p className="mt-2 text-xs text-indigo-700 bg-indigo-50 rounded-lg px-3 py-2 leading-relaxed">
                  {ex.sequencing_rationale}
                </p>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Connector arrow between exercises (not on last item) */}
      {!isLast && (
        <div className="flex justify-center my-1">
          <span className="text-slate-300 text-lg leading-none select-none">|</span>
        </div>
      )}
    </li>
  );
}

// ---------------------------------------------------------------------------
// Section
// ---------------------------------------------------------------------------

interface SectionProps {
  title: string;
  exercises: PlannedExercise[];
  loadCapPct: number;
  accentClass: string;
}

function Section({ title, exercises, loadCapPct, accentClass }: SectionProps) {
  if (exercises.length === 0) return null;

  const sorted = [...exercises].sort((a, b) => a.order - b.order);

  return (
    <div className="space-y-1">
      <h4 className={`text-xs font-bold uppercase tracking-wide mb-3 ${accentClass}`}>
        {title}
      </h4>
      <ol className="list-none space-y-0">
        {sorted.map((ex, idx) => (
          <ExerciseCard
            key={ex.exercise_id + ex.order}
            exercise={ex}
            loadCapPct={loadCapPct}
            isLast={idx === sorted.length - 1}
          />
        ))}
      </ol>
    </div>
  );
}

// ---------------------------------------------------------------------------
// PlanDisplay
// ---------------------------------------------------------------------------

interface PlanDisplayProps {
  plan: WorkoutPlan;
  loadCapPct: number;
}

export function PlanDisplay({ plan, loadCapPct }: PlanDisplayProps) {
  return (
    <div className="space-y-6">
      {/* Why this session was designed this way */}
      <div className="rounded-2xl border border-line bg-sand/40 p-5 space-y-4">
        <p className="eyebrow text-clay">Why this session</p>

        {/* The prominent design-rationale paragraph */}
        {plan.design_rationale && (
          <p className="text-sm leading-relaxed text-ink">{plan.design_rationale}</p>
        )}

        {(plan.stimulus || plan.target_adaptation) && (
          <div className="grid gap-3 sm:grid-cols-2">
            {plan.stimulus && (
              <div>
                <span className="eyebrow">Stimulus</span>
                <p className="mt-0.5 text-sm font-medium text-ink">{plan.stimulus}</p>
              </div>
            )}
            {plan.target_adaptation && (
              <div>
                <span className="eyebrow">Target adaptation</span>
                <p className="mt-0.5 text-sm text-ink-soft">{plan.target_adaptation}</p>
              </div>
            )}
          </div>
        )}

        {plan.sequence_logic && (
          <div className="border-t border-line pt-3">
            <span className="eyebrow">Ordering strategy</span>
            <p className="mt-0.5 text-sm leading-relaxed text-ink-soft">
              {plan.sequence_logic}
            </p>
          </div>
        )}

        <p className="text-xs text-ink-faint">
          Estimated duration: <strong className="text-ink-soft">{plan.total_minutes} min</strong>
          {loadCapPct < 1.0 && (
            <span className="ml-3 inline-flex items-center gap-1 rounded-full bg-clay/10 px-2 py-0.5 text-xs font-medium text-clay">
              Intensity capped at {Math.round(loadCapPct * 100)}%
            </span>
          )}
        </p>
      </div>

      {/* Exercise sections */}
      <Section
        title="Warm-up"
        exercises={plan.warmup}
        loadCapPct={loadCapPct}
        accentClass="text-sky-600"
      />
      <Section
        title="Main"
        exercises={plan.main}
        loadCapPct={loadCapPct}
        accentClass="text-indigo-600"
      />
      <Section
        title="Cool-down"
        exercises={plan.cooldown}
        loadCapPct={loadCapPct}
        accentClass="text-green-600"
      />
    </div>
  );
}
