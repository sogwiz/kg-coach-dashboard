/**
 * WorkoutSynthesis — shows the ACTUAL training outcome of a coach-built canvas.
 *
 * Renders the deterministic analysis: primary adaptation, a plain-language
 * verdict + an intended-vs-actual tip, the stimulus gauges, an adaptation
 * profile (max-strength → mobility), and a section/sets summary. Lets a coach
 * see that, e.g., their "strength" workout actually reads as hypertrophy.
 */

import type { CanvasAnalysis } from "../../lib/api";
import { StimulusGauges } from "../generator/StimulusGauges";

const ADAPT_ORDER = [
  "max_strength",
  "power",
  "hypertrophy",
  "strength_endurance",
  "conditioning",
  "mobility",
];

const ADAPT_LABEL: Record<string, string> = {
  max_strength: "Max strength",
  power: "Power",
  hypertrophy: "Hypertrophy",
  strength_endurance: "Strength-endurance",
  conditioning: "Conditioning",
  mobility: "Mobility",
};

export function WorkoutSynthesis({
  analysis,
  onClose,
}: {
  analysis: CanvasAnalysis;
  onClose: () => void;
}) {
  return (
    <div className="space-y-5 rounded-2xl border border-line bg-surface p-5">
      <div className="flex items-start justify-between">
        <div>
          <p className="eyebrow mb-1 text-clay">Synthesis · actual outcome</p>
          <h4 className="font-display text-2xl font-light text-ink">
            {analysis.primary_label}
          </h4>
        </div>
        <button
          type="button"
          onClick={onClose}
          aria-label="Close synthesis"
          className="text-ink-faint transition-colors hover:text-ink"
        >
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M6 6l12 12M6 18L18 6" strokeLinecap="round" />
          </svg>
        </button>
      </div>

      <p className="text-sm leading-relaxed text-ink">{analysis.verdict}</p>
      <p className="rounded-lg border border-clay/20 bg-clay/5 px-3 py-2 text-sm text-clay">
        💡 {analysis.tip}
      </p>

      <StimulusGauges dist={analysis.stimulus_distribution} />

      {/* Adaptation profile */}
      <div>
        <p className="eyebrow mb-3">Adaptation profile</p>
        <div className="space-y-2">
          {ADAPT_ORDER.map((k) => {
            const v = analysis.adaptation_scores[k] ?? 0;
            const isPrimary = k === analysis.primary_adaptation;
            return (
              <div key={k} className="flex items-center gap-3">
                <span
                  className={`w-36 flex-shrink-0 text-xs ${
                    isPrimary ? "font-semibold text-ink" : "text-ink-soft"
                  }`}
                >
                  {ADAPT_LABEL[k]}
                </span>
                <div className="relative h-1.5 flex-1 overflow-hidden rounded-full bg-sand">
                  <div
                    className="absolute inset-y-0 left-0 rounded-full transition-[width] duration-500"
                    style={{
                      width: `${v}%`,
                      background: isPrimary ? "var(--color-clay)" : "var(--color-ink-faint)",
                    }}
                  />
                </div>
                <span className="w-8 flex-shrink-0 text-right text-sm tabular-nums text-ink">
                  {v}
                </span>
              </div>
            );
          })}
        </div>
      </div>

      {/* Section + sets summary */}
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1 border-t border-line pt-3 text-xs text-ink-faint">
        <span>{analysis.total_exercises} exercises</span>
        <span>{analysis.total_sets} total sets</span>
        <span>
          Warmup {analysis.per_section.warmup} · Main {analysis.per_section.main} · Cooldown{" "}
          {analysis.per_section.cooldown}
        </span>
      </div>
    </div>
  );
}
