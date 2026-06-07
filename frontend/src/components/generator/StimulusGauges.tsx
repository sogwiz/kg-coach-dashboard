/**
 * StimulusGauges — thermometer-style readouts of how strongly a generated
 * session leans toward each stimulus (strength / conditioning / mobility).
 *
 * Values are independent 0-100 readings emitted by the structuring LLM. Since
 * the coach now sets modality via the prompt (single workout), these gauges
 * give immediate feedback on how the session is catered across stimuli.
 */

import type { StimulusDistribution } from "../../lib/api";

const ROWS: { key: keyof StimulusDistribution; label: string; color: string }[] = [
  { key: "strength", label: "Strength", color: "var(--color-clay)" },
  { key: "conditioning", label: "Conditioning", color: "var(--color-gold)" },
  { key: "mobility", label: "Mobility", color: "var(--color-sage)" },
];

export function StimulusGauges({ dist }: { dist?: StimulusDistribution }) {
  if (!dist) return null;

  return (
    <div>
      <p className="eyebrow mb-3">Stimulus emphasis</p>
      <div className="space-y-2.5">
        {ROWS.map((r) => {
          const v = Math.max(0, Math.min(100, dist[r.key] ?? 0));
          return (
            <div key={r.key} className="flex items-center gap-3">
              <span className="w-24 flex-shrink-0 text-[0.72rem] font-medium text-ink-soft">
                {r.label}
              </span>
              {/* Thermometer track */}
              <div className="relative h-1.5 flex-1 overflow-hidden rounded-full bg-sand">
                <div
                  className="absolute inset-y-0 left-0 rounded-full transition-[width] duration-700 ease-out"
                  style={{ width: `${v}%`, background: r.color }}
                />
              </div>
              <span className="w-8 flex-shrink-0 text-right font-display text-sm font-light text-ink tabular-nums">
                {v}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
