/**
 * InjuryTimeline — 14-day history of check-ins showing trend.
 *
 * Renders a sparkline-style bar chart of subjective pain per day and
 * shows a trend label (improving / stable / worsening).
 */

import type { InjuryState } from "../../lib/api";

interface Props {
  history: InjuryState[];
}

function formatDate(iso: string): string {
  const d = new Date(iso);
  return `${d.getMonth() + 1}/${d.getDate()}`;
}

function calcTrend(history: InjuryState[]): "improving" | "stable" | "worsening" {
  if (history.length < 2) return "stable";
  const sorted = [...history].sort(
    (a, b) => new Date(a.recorded_at).getTime() - new Date(b.recorded_at).getTime()
  );
  const oldest = sorted[0].subjective_pain;
  const newest = sorted[sorted.length - 1].subjective_pain;
  const delta = newest - oldest;
  if (delta <= -1) return "improving";
  if (delta >= 1) return "worsening";
  return "stable";
}

const TREND_STYLES: Record<
  string,
  { label: string; bg: string; text: string }
> = {
  improving: { label: "Improving", bg: "bg-emerald-100", text: "text-emerald-700" },
  stable: { label: "Stable", bg: "bg-slate-100", text: "text-slate-600" },
  worsening: { label: "Worsening", bg: "bg-red-100", text: "text-red-700" },
};

const INFLAMMATION_DOT: Record<string, string> = {
  none: "bg-emerald-400",
  mild: "bg-amber-400",
  moderate: "bg-orange-500",
  severe: "bg-red-500",
};

export function InjuryTimeline({ history }: Props) {
  if (history.length === 0) {
    return (
      <div className="bg-white rounded-xl border border-slate-200 p-4">
        <h4 className="text-sm font-semibold text-slate-700 mb-2">
          Check-in History (14 days)
        </h4>
        <p className="text-sm text-slate-400">No check-ins recorded yet.</p>
      </div>
    );
  }

  const sorted = [...history].sort(
    (a, b) => new Date(a.recorded_at).getTime() - new Date(b.recorded_at).getTime()
  );

  const trend = calcTrend(history);
  const trendStyle = TREND_STYLES[trend];
  const maxPain = 10;

  return (
    <div className="bg-white rounded-xl border border-slate-200 p-4">
      <div className="flex items-center justify-between mb-3">
        <h4 className="text-sm font-semibold text-slate-700">
          Check-in History (14 days)
        </h4>
        <span
          className={`text-xs font-medium rounded-full px-2.5 py-0.5 ${trendStyle.bg} ${trendStyle.text}`}
        >
          {trendStyle.label}
        </span>
      </div>

      {/* Bar chart */}
      <div className="flex items-end gap-1 h-16">
        {sorted.map((state, idx) => {
          const height = Math.max(4, (state.subjective_pain / maxPain) * 64);
          return (
            <div
              key={idx}
              className="flex-1 flex flex-col items-center gap-1"
              title={`${formatDate(state.recorded_at)}: pain ${state.subjective_pain}/10, ${state.inflammation} inflammation`}
            >
              <div
                className="w-full rounded-t bg-indigo-300 hover:bg-indigo-400 transition-colors cursor-default"
                style={{ height: `${height}px` }}
              />
              {/* Inflammation dot */}
              <div
                className={`w-2 h-2 rounded-full ${INFLAMMATION_DOT[state.inflammation] ?? "bg-slate-300"}`}
                title={`Inflammation: ${state.inflammation}`}
              />
            </div>
          );
        })}
      </div>

      {/* Axis labels */}
      <div className="flex justify-between mt-1">
        <span className="text-xs text-slate-400">
          {formatDate(sorted[0].recorded_at)}
        </span>
        <span className="text-xs text-slate-400">
          {formatDate(sorted[sorted.length - 1].recorded_at)}
        </span>
      </div>

      {/* Legend */}
      <div className="flex items-center gap-3 mt-2">
        <span className="text-xs text-slate-400">Inflammation:</span>
        {Object.entries(INFLAMMATION_DOT).map(([level, cls]) => (
          <span key={level} className="flex items-center gap-1 text-xs text-slate-500">
            <span className={`w-2 h-2 rounded-full ${cls}`} />
            {level}
          </span>
        ))}
      </div>
    </div>
  );
}
