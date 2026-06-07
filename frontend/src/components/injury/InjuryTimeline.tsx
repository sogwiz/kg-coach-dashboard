/**
 * InjuryTimeline — "Check-in History (Last 14 Days)".
 *
 * A dual-axis recovery snapshot:
 *   - a pain line (0-10) across 14 distinct days, with dots colored by that
 *     day's inflammation severity
 *   - an inflammation row beneath: one cell per day, color-coded by severity
 *     (empty cell = no check-in that day, so check-in frequency reads at a glance)
 *   - hover any day for a tooltip: pain score, inflammation, and the log note
 *   - a trend badge (improving / stable / worsening)
 */

import { useMemo, useState } from "react";
import type { InjuryState } from "../../lib/api";

// Severity → color (none green → severe red)
const SEV_COLOR: Record<string, string> = {
  none: "#10b981", // emerald-500
  mild: "#f59e0b", // amber-500
  moderate: "#f97316", // orange-500
  severe: "#ef4444", // red-500
};
const SEV_LEVELS = ["none", "mild", "moderate", "severe"] as const;

const DAYS = 14;

interface DayBucket {
  date: Date;
  label: string; // M/D
  dow: string; // S M T W T F S
  state: InjuryState | null;
}

function dateKey(d: Date): string {
  return `${d.getFullYear()}-${d.getMonth()}-${d.getDate()}`;
}

function calcTrend(history: InjuryState[]): "improving" | "stable" | "worsening" {
  if (history.length < 2) return "stable";
  const sorted = [...history].sort(
    (a, b) => new Date(a.recorded_at).getTime() - new Date(b.recorded_at).getTime()
  );
  const delta = sorted[sorted.length - 1].subjective_pain - sorted[0].subjective_pain;
  if (delta <= -1) return "improving";
  if (delta >= 1) return "worsening";
  return "stable";
}

const TREND_STYLES: Record<string, { label: string; cls: string }> = {
  improving: { label: "↑ Improving", cls: "bg-emerald-50 text-emerald-700 border-emerald-200" },
  stable: { label: "→ Stable", cls: "bg-sand text-ink-soft border-line" },
  worsening: { label: "↓ Worsening", cls: "bg-red-50 text-red-700 border-red-200" },
};

const DOW = ["S", "M", "T", "W", "T", "F", "S"];

export function InjuryTimeline({ history }: { history: InjuryState[] }) {
  const [hover, setHover] = useState<number | null>(null);

  const days: DayBucket[] = useMemo(() => {
    // Index check-ins by local date
    const byDate = new Map<string, InjuryState>();
    for (const s of history) {
      const d = new Date(s.recorded_at);
      byDate.set(dateKey(d), s); // last check-in of the day wins
    }
    // Anchor the window on the latest check-in (or today if more recent)
    let end = new Date();
    if (history.length > 0) {
      const latest = history.reduce(
        (mx, s) => Math.max(mx, new Date(s.recorded_at).getTime()),
        0
      );
      end = new Date(Math.max(latest, end.getTime()));
    }
    end.setHours(0, 0, 0, 0);

    const out: DayBucket[] = [];
    for (let i = DAYS - 1; i >= 0; i--) {
      const d = new Date(end);
      d.setDate(end.getDate() - i);
      out.push({
        date: d,
        label: `${d.getMonth() + 1}/${d.getDate()}`,
        dow: DOW[d.getDay()],
        state: byDate.get(dateKey(d)) ?? null,
      });
    }
    return out;
  }, [history]);

  if (history.length === 0) {
    return (
      <div className="rounded-2xl border border-line bg-surface p-5">
        <h4 className="text-sm font-semibold text-ink">Check-in History (Last 14 Days)</h4>
        <p className="mt-2 text-sm text-ink-faint">No check-ins recorded yet.</p>
      </div>
    );
  }

  const trend = TREND_STYLES[calcTrend(history)];
  const checkinCount = days.filter((d) => d.state).length;

  // Pain line points in a 0..100 viewBox (x by index, y inverted by pain/10)
  const pts = days
    .map((d, i) =>
      d.state ? { i, x: (i / (DAYS - 1)) * 100, y: 100 - (d.state.subjective_pain / 10) * 100 } : null
    )
    .filter((p): p is { i: number; x: number; y: number } => p !== null);
  const polyline = pts.map((p) => `${p.x},${p.y}`).join(" ");

  const hoverDay = hover != null ? days[hover] : null;

  return (
    <div className="rounded-2xl border border-line bg-surface p-5">
      {/* Header */}
      <div className="mb-4 flex items-center justify-between">
        <div>
          <h4 className="text-sm font-semibold text-ink">Check-in History</h4>
          <p className="mt-0.5 text-xs text-ink-faint">
            Last 14 days · {checkinCount} check-in{checkinCount === 1 ? "" : "s"}
          </p>
        </div>
        <span className={`rounded-full border px-2.5 py-1 text-xs font-medium ${trend.cls}`}>
          {trend.label}
        </span>
      </div>

      <div className="relative">
        {/* Tooltip */}
        {hoverDay && (
          <div
            className="pointer-events-none absolute -top-2 z-10 -translate-x-1/2 -translate-y-full whitespace-nowrap rounded-lg bg-ink px-3 py-2 text-xs text-canvas shadow-lg"
            style={{ left: `${(hover! / (DAYS - 1)) * 100}%` }}
          >
            <div className="font-semibold">{hoverDay.label}</div>
            {hoverDay.state ? (
              <>
                <div className="mt-0.5 flex items-center gap-1.5">
                  <span
                    className="inline-block h-2 w-2 rounded-full"
                    style={{ background: SEV_COLOR[hoverDay.state.inflammation] }}
                  />
                  pain {hoverDay.state.subjective_pain}/10 · {hoverDay.state.inflammation}
                </div>
                {hoverDay.state.notes && (
                  <div className="mt-1 max-w-[16rem] whitespace-normal text-canvas/70">
                    {hoverDay.state.notes}
                  </div>
                )}
              </>
            ) : (
              <div className="mt-0.5 text-canvas/60">No check-in</div>
            )}
          </div>
        )}

        {/* Pain line chart */}
        <div className="flex">
          {/* y-axis */}
          <div className="mr-2 flex h-20 w-4 flex-col justify-between py-0.5 text-[9px] text-ink-faint">
            <span>10</span>
            <span>5</span>
            <span>0</span>
          </div>

          <div className="relative h-20 flex-1">
            {/* gridlines */}
            <div className="absolute inset-0 flex flex-col justify-between">
              {[0, 1, 2].map((g) => (
                <div key={g} className="border-t border-line/60" />
              ))}
            </div>
            {/* line */}
            <svg
              className="absolute inset-0 h-full w-full overflow-visible"
              viewBox="0 0 100 100"
              preserveAspectRatio="none"
            >
              {pts.length > 1 && (
                <polyline
                  points={polyline}
                  fill="none"
                  stroke="var(--color-clay)"
                  strokeWidth="2"
                  vectorEffect="non-scaling-stroke"
                  strokeLinejoin="round"
                  strokeLinecap="round"
                />
              )}
            </svg>
            {/* dots (HTML so they stay round), colored by inflammation severity */}
            {pts.map((p) => {
              const st = days[p.i].state!;
              return (
                <span
                  key={p.i}
                  className="absolute h-2.5 w-2.5 -translate-x-1/2 -translate-y-1/2 rounded-full ring-2 ring-surface"
                  style={{
                    left: `${p.x}%`,
                    top: `${p.y}%`,
                    background: SEV_COLOR[st.inflammation],
                  }}
                />
              );
            })}
          </div>
        </div>

        {/* Inflammation row — one cell per day, color = severity */}
        <div className="ml-6 mt-2 grid grid-cols-[repeat(14,minmax(0,1fr))] gap-0.5">
          {days.map((d, i) => (
            <div
              key={i}
              className="h-2 rounded-sm"
              style={{
                background: d.state ? SEV_COLOR[d.state.inflammation] : undefined,
                border: d.state ? undefined : "1px dashed var(--color-line)",
              }}
            />
          ))}
        </div>

        {/* Day labels (weekday) */}
        <div className="ml-6 mt-1 grid grid-cols-[repeat(14,minmax(0,1fr))] gap-0.5 text-center text-[9px] text-ink-faint">
          {days.map((d, i) => (
            <span key={i}>{d.dow}</span>
          ))}
        </div>

        {/* Hover hit-columns spanning the chart + rows */}
        <div className="absolute inset-0 ml-6 grid grid-cols-[repeat(14,minmax(0,1fr))]">
          {days.map((_, i) => (
            <div
              key={i}
              onMouseEnter={() => setHover(i)}
              onMouseLeave={() => setHover((h) => (h === i ? null : h))}
            />
          ))}
        </div>
      </div>

      {/* Legend */}
      <div className="mt-4 flex items-center gap-3 border-t border-line pt-3">
        <span className="text-[11px] text-ink-faint">Inflammation:</span>
        {SEV_LEVELS.map((lvl) => (
          <span key={lvl} className="flex items-center gap-1 text-[11px] text-ink-soft">
            <span className="h-2 w-2 rounded-full" style={{ background: SEV_COLOR[lvl] }} />
            {lvl}
          </span>
        ))}
      </div>
    </div>
  );
}
