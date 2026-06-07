/**
 * VariantChooser — single generated session card.
 *
 * The generator now produces ONE workout (the coach sets modality via the
 * prompt), so this renders a single plan with:
 *   - header (label · duration · exercise count)
 *   - StimulusGauges (how the session leans strength / conditioning / mobility)
 *   - PlanDisplay (ordered exercises + sequencing rationale + sequence_logic)
 *   - footer actions: Send to Canvas · Send to Client · Regenerate (with an
 *     optional "adjust" tweak that re-runs aware of THIS session).
 *
 * Regenerate takes the previously generated session into account (backend
 * /api/generate/regenerate) so the new plan is a fresh, distinct variation.
 */

import { useState } from "react";
import type { WorkoutVariant } from "../../lib/api";
import { PlanDisplay } from "./PlanDisplay";
import { StimulusGauges } from "./StimulusGauges";
import { SendWorkoutModal } from "./SendWorkoutModal";
import { pushToCanvas } from "../../state/canvas";

interface VariantChooserProps {
  variants: WorkoutVariant[];
  /** Regenerate a fresh variation; optional adjustment tweaks it */
  onRegenerate: (adjustment?: string) => void;
  /** Called after "Send to Canvas" so Dashboard can switch to the Creative tab */
  onSendToCanvas?: () => void;
  /** Called after workout is sent to refresh member list */
  onWorkoutSent?: () => void;
  generatorLoading?: boolean;
  memberId?: string;
  memberName?: string;
}

export function VariantChooser({
  variants,
  onRegenerate,
  onSendToCanvas,
  onWorkoutSent,
  generatorLoading = false,
  memberId,
  memberName,
}: VariantChooserProps) {
  const [showSendModal, setShowSendModal] = useState(false);
  const [adjust, setAdjust] = useState("");

  const variant = variants[0] ?? null;
  if (!variant) return null;

  const exerciseCount =
    variant.plan.warmup.length +
    variant.plan.main.length +
    variant.plan.cooldown.length;

  const handleSendToCanvas = () => {
    // Map each plan section to its canvas column (warmup / main / cooldown).
    pushToCanvas({
      warmup: variant.plan.warmup,
      main: variant.plan.main,
      cooldown: variant.plan.cooldown,
    });
    if (onSendToCanvas) onSendToCanvas();
  };

  const handleRegenerate = () => {
    onRegenerate(adjust.trim() || undefined);
  };

  return (
    <div className="overflow-hidden rounded-2xl border border-line bg-surface">
      {/* Header */}
      <div className="flex items-start justify-between gap-4 border-b border-line px-6 py-5">
        <div className="min-w-0">
          <p className="eyebrow mb-1.5">Generated session</p>
          <h4 className="font-display text-2xl font-light leading-tight text-ink">
            {variant.plan.stimulus || variant.label}
          </h4>
        </div>
        <span className="flex-shrink-0 whitespace-nowrap pt-1 text-xs text-ink-faint">
          {variant.plan.total_minutes} min · {exerciseCount} exercises
        </span>
      </div>

      {/* Gauges */}
      <div className="border-b border-line px-6 py-5">
        <StimulusGauges dist={variant.plan.stimulus_distribution} />
      </div>

      {/* Plan body */}
      <div className="px-6 py-5">
        <PlanDisplay
          plan={variant.plan}
          loadCapPct={variant.provenance.load_tolerance_pct}
        />
      </div>

      {/* Footer actions */}
      <div className="border-t border-line bg-canvas/60 px-6 py-4">
        <div className="flex flex-wrap items-center gap-2.5">
          <button
            type="button"
            onClick={handleSendToCanvas}
            className="rounded-full border border-line px-4 py-2 text-xs font-medium text-ink-soft transition-colors hover:border-ink hover:text-ink"
          >
            Send to Canvas
          </button>

          {memberId && memberName && (
            <button
              type="button"
              onClick={() => setShowSendModal(true)}
              className="rounded-full bg-sage px-4 py-2 text-xs font-semibold text-white transition-opacity hover:opacity-90"
            >
              Send to Client
            </button>
          )}

          <span className="flex-1" />

          {/* Optional adjust tweak + Regenerate */}
          <input
            type="text"
            value={adjust}
            onChange={(e) => setAdjust(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !generatorLoading) handleRegenerate();
            }}
            disabled={generatorLoading}
            placeholder="Adjust (optional) — e.g. more posterior chain"
            className="h-9 w-56 rounded-full border border-line bg-surface px-4 text-xs text-ink placeholder-ink-faint focus:border-ink focus:outline-none disabled:opacity-60"
          />
          <button
            type="button"
            onClick={handleRegenerate}
            disabled={generatorLoading}
            className="flex items-center gap-1.5 rounded-full bg-ink px-4 py-2 text-xs font-semibold text-canvas transition-colors hover:bg-clay disabled:cursor-not-allowed disabled:opacity-60"
          >
            {generatorLoading ? (
              <>
                <span className="h-3 w-3 animate-spin rounded-full border-2 border-canvas/40 border-t-canvas" />
                Regenerating…
              </>
            ) : (
              "Regenerate"
            )}
          </button>
        </div>
      </div>

      {/* Send modal */}
      {memberId && memberName && (
        <SendWorkoutModal
          memberId={memberId}
          memberName={memberName}
          variant={variant}
          isOpen={showSendModal}
          onClose={() => setShowSendModal(false)}
          onSent={() => {
            if (onWorkoutSent) onWorkoutSent();
          }}
        />
      )}
    </div>
  );
}
