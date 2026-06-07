/**
 * InjuryStatusCard — healing phase badge, days since onset, last check-in,
 * and a "Needs check-in" badge when no check-in today.
 */

import type { Injury, InjuryState } from "../../lib/api";
import { HealingPhaseIndicator, type HealingPhase } from "./HealingPhaseIndicator";

interface Props {
  injury: Injury;
  currentState: InjuryState | null;
  needsCheckIn: boolean;
  onCheckIn: () => void;
}

function computePhase(onsetDate: string): HealingPhase {
  const onset = new Date(onsetDate);
  const days = Math.floor((Date.now() - onset.getTime()) / 86_400_000);
  if (days < 7) return "acute";
  if (days < 21) return "subacute";
  if (days < 90) return "remodeling";
  return "rta";
}

function daysSince(onsetDate: string): number {
  const onset = new Date(onsetDate);
  return Math.floor((Date.now() - onset.getTime()) / 86_400_000);
}

function formatRelative(iso: string): string {
  const d = new Date(iso);
  const diffMs = Date.now() - d.getTime();
  const diffH = Math.floor(diffMs / 3_600_000);
  const diffM = Math.floor(diffMs / 60_000);
  if (diffM < 1) return "just now";
  if (diffM < 60) return `${diffM}m ago`;
  if (diffH < 24) return `${diffH}h ago`;
  const diffD = Math.floor(diffH / 24);
  return `${diffD}d ago`;
}

const INFLAMMATION_BADGE: Record<string, { bg: string; text: string }> = {
  none: { bg: "bg-emerald-100", text: "text-emerald-700" },
  mild: { bg: "bg-amber-100", text: "text-amber-700" },
  moderate: { bg: "bg-orange-100", text: "text-orange-700" },
  severe: { bg: "bg-red-100", text: "text-red-700" },
};

export function InjuryStatusCard({
  injury,
  currentState,
  needsCheckIn,
  onCheckIn,
}: Props) {
  const effectiveOnset = injury.onset_date ?? injury.since;
  const phase = computePhase(effectiveOnset);
  const days = daysSince(effectiveOnset);
  const inflamm = currentState
    ? INFLAMMATION_BADGE[currentState.inflammation] ?? { bg: "bg-slate-100", text: "text-slate-600" }
    : null;

  return (
    <div className="bg-white rounded-xl border border-slate-200 p-4 space-y-4">
      {/* Header row */}
      <div className="flex items-start justify-between gap-2">
        <div>
          <h3 className="text-sm font-semibold text-slate-800">
            {injury.region}
          </h3>
          {injury.diagnosis && (
            <p className="text-xs text-slate-500 mt-0.5 leading-snug">
              {injury.diagnosis}
            </p>
          )}
        </div>

        <div className="flex items-center gap-2 flex-shrink-0">
          {needsCheckIn && (
            <span className="inline-flex items-center rounded-full bg-amber-100 px-2.5 py-0.5 text-xs font-medium text-amber-700">
              Needs check-in
            </span>
          )}
          <button
            onClick={onCheckIn}
            className="text-xs font-medium text-indigo-600 hover:text-indigo-800 bg-indigo-50 hover:bg-indigo-100 rounded-lg px-3 py-1.5 transition-colors"
          >
            {needsCheckIn ? "Check in now" : "Update check-in"}
          </button>
        </div>
      </div>

      {/* Last check-in summary */}
      {currentState ? (
        <div className="rounded-lg bg-slate-50 border border-slate-200 p-3 space-y-2">
          <div className="flex items-center justify-between">
            <p className="text-xs font-medium text-slate-600">Last check-in</p>
            <p className="text-xs text-slate-400">
              {formatRelative(currentState.recorded_at)}
            </p>
          </div>

          <div className="flex flex-wrap gap-2 items-center">
            {/* Pain score */}
            <span className="text-xs bg-indigo-50 text-indigo-700 rounded px-2 py-0.5 font-medium">
              Pain {currentState.subjective_pain}/10
            </span>

            {/* Inflammation */}
            {inflamm && (
              <span
                className={`text-xs rounded px-2 py-0.5 font-medium ${inflamm.bg} ${inflamm.text}`}
              >
                {currentState.inflammation} inflammation
              </span>
            )}

            {/* Load tolerance */}
            <span className="text-xs bg-slate-100 text-slate-600 rounded px-2 py-0.5">
              Load {Math.round(currentState.load_tolerance_pct * 100)}%
            </span>
          </div>

          {/* Pain triggers */}
          {currentState.pain_on.length > 0 && (
            <div className="flex flex-wrap gap-1">
              <span className="text-xs text-slate-500">Pain on:</span>
              {currentState.pain_on.map((t) => (
                <span
                  key={t}
                  className="text-xs bg-red-50 text-red-600 rounded px-1.5 py-0.5"
                >
                  {t}
                </span>
              ))}
            </div>
          )}

          {currentState.notes && (
            <p className="text-xs text-slate-500 italic">
              &ldquo;{currentState.notes}&rdquo;
            </p>
          )}
        </div>
      ) : (
        <p className="text-sm text-slate-400 bg-slate-50 rounded-lg p-3">
          No check-ins recorded yet.
        </p>
      )}

      {/* Healing phase progress */}
      <div className="pt-2 border-t border-slate-100">
        <HealingPhaseIndicator currentPhase={phase} daysSinceOnset={days} />
      </div>
    </div>
  );
}
