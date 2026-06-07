/**
 * VariantChooser (Phase 13 revision) — single-workout view with modality selector.
 *
 * Instead of showing all 3 variants side-by-side, shows ONE workout at a
 * time. A compact modality selector (strength / conditioning / mobility) at
 * the top lets the coach switch which variant is displayed.
 *
 * Selecting a modality calls POST /api/generate/select (records the choice
 * for the Copilot). The selected variant's full PlanDisplay is shown below
 * (ordered exercises + sequencing_role chips + "why here" rationale +
 * sequence_logic + provenance/decision traces — unchanged from Phase 9).
 *
 * "Regenerate" button at the bottom re-runs the generator (passed in as a
 * callback from Dashboard).
 *
 * "Send to Canvas" pushes the currently displayed variant's exercises into
 * the shared creative canvas state and switches to the Creative tab.
 */

import { useState, useEffect } from "react";
import type { WorkoutVariant } from "../../lib/api";
import { PlanDisplay } from "./PlanDisplay";
import { pushToCanvas } from "../../state/canvas";

// ---------------------------------------------------------------------------
// Modality accent colours
// ---------------------------------------------------------------------------

const VARIANT_STYLES: Record<
  string,
  { border: string; header: string; badge: string; activeTab: string; inactiveTab: string }
> = {
  strength: {
    border: "border-indigo-300",
    header: "bg-indigo-600",
    badge: "bg-indigo-100 text-indigo-700",
    activeTab: "bg-indigo-600 text-white",
    inactiveTab: "text-indigo-600 hover:bg-indigo-50 border border-indigo-200",
  },
  conditioning: {
    border: "border-orange-300",
    header: "bg-orange-500",
    badge: "bg-orange-100 text-orange-700",
    activeTab: "bg-orange-500 text-white",
    inactiveTab: "text-orange-600 hover:bg-orange-50 border border-orange-200",
  },
  mobility: {
    border: "border-green-300",
    header: "bg-green-600",
    badge: "bg-green-100 text-green-700",
    activeTab: "bg-green-600 text-white",
    inactiveTab: "text-green-600 hover:bg-green-50 border border-green-200",
  },
};

const DEFAULT_STYLE = {
  border: "border-slate-300",
  header: "bg-slate-500",
  badge: "bg-slate-100 text-slate-600",
  activeTab: "bg-slate-600 text-white",
  inactiveTab: "text-slate-600 hover:bg-slate-50 border border-slate-200",
};

function variantStyle(variantId: string) {
  return VARIANT_STYLES[variantId] ?? DEFAULT_STYLE;
}

// ---------------------------------------------------------------------------
// VariantChooser
// ---------------------------------------------------------------------------

interface VariantChooserProps {
  variants: WorkoutVariant[];
  selectedVariant: WorkoutVariant | null;
  isSelecting: boolean;
  onSelect: (variantId: string) => void;
  onRegenerate: () => void;
  /** Called after "Send to Canvas" so Dashboard can switch to the Creative tab */
  onSendToCanvas?: () => void;
  generatorLoading?: boolean;
}

export function VariantChooser({
  variants,
  selectedVariant,
  isSelecting,
  onSelect,
  onRegenerate,
  onSendToCanvas,
  generatorLoading = false,
}: VariantChooserProps) {
  // The modality currently displayed — defaults to the selected variant (if
  // any) or the first variant returned.
  const [displayedId, setDisplayedId] = useState<string>(
    selectedVariant?.variant_id ?? variants[0]?.variant_id ?? ""
  );

  // Keep displayed in sync when selectedVariant changes externally (e.g. after
  // /api/generate/select returns a different selection).
  useEffect(() => {
    if (selectedVariant?.variant_id) {
      setDisplayedId(selectedVariant.variant_id);
    }
  }, [selectedVariant?.variant_id]);

  const displayedVariant =
    variants.find((v) => v.variant_id === displayedId) ?? variants[0] ?? null;

  if (!displayedVariant) return null;

  const s = variantStyle(displayedVariant.variant_id);

  const handleModalityClick = (variantId: string) => {
    setDisplayedId(variantId);
    // Record choice for the Copilot
    onSelect(variantId);
  };

  const handleSendToCanvas = () => {
    if (!displayedVariant) return;
    // Collect all exercises in order: warmup → main → cooldown
    const allExercises = [
      ...displayedVariant.plan.warmup,
      ...displayedVariant.plan.main,
      ...displayedVariant.plan.cooldown,
    ].sort((a, b) => a.order - b.order);
    pushToCanvas(allExercises);
    if (onSendToCanvas) onSendToCanvas();
  };

  return (
    <div className="space-y-4">
      {/* ------------------------------------------------------------------ */}
      {/* Modality selector — compact pill row                                */}
      {/* ------------------------------------------------------------------ */}
      <div>
        <p className="text-xs text-slate-500 mb-2 font-medium">
          Select modality to view:
        </p>
        <div className="flex gap-2 flex-wrap">
          {variants.map((v) => {
            const vs = variantStyle(v.variant_id);
            const isDisplayed = v.variant_id === displayedId;
            return (
              <button
                key={v.variant_id}
                type="button"
                disabled={isSelecting}
                onClick={() => handleModalityClick(v.variant_id)}
                className={`px-4 py-1.5 rounded-full text-xs font-semibold transition-colors ${
                  isDisplayed ? vs.activeTab : vs.inactiveTab
                } disabled:opacity-60`}
              >
                {v.label}
                {v.variant_id === selectedVariant?.variant_id && (
                  <span className="ml-1.5 opacity-80">✓</span>
                )}
              </button>
            );
          })}
        </div>
        {selectedVariant && (
          <p className="text-[10px] text-slate-400 mt-1.5">
            Copilot-selected:{" "}
            <span className="font-medium text-slate-600">
              {selectedVariant.label}
            </span>
          </p>
        )}
      </div>

      {/* ------------------------------------------------------------------ */}
      {/* Full plan display for the displayed variant                          */}
      {/* ------------------------------------------------------------------ */}
      <div className={`rounded-xl border-2 overflow-hidden ${s.border}`}>
        {/* Plan header */}
        <div className={`${s.header} px-5 py-3 flex items-center justify-between`}>
          <div>
            <p className="text-xs font-bold text-white/70 uppercase tracking-wide">
              {displayedVariant.variant_id}
            </p>
            <h4 className="text-sm font-semibold text-white leading-tight mt-0.5">
              {displayedVariant.label}
            </h4>
          </div>
          <span className="text-xs text-white/80 font-medium">
            {displayedVariant.plan.total_minutes} min ·{" "}
            {displayedVariant.plan.warmup.length +
              displayedVariant.plan.main.length +
              displayedVariant.plan.cooldown.length}{" "}
            exercises
          </span>
        </div>

        {/* Optimizes-for pill */}
        <div className="px-5 pt-4 pb-0">
          <span className={`inline-block text-xs font-medium px-2.5 py-1 rounded-full ${s.badge}`}>
            {displayedVariant.optimizes_for}
          </span>
        </div>

        {/* Plan body */}
        <div className="px-5 pb-5 pt-4">
          <PlanDisplay
            plan={displayedVariant.plan}
            loadCapPct={displayedVariant.provenance.load_tolerance_pct}
          />
        </div>

        {/* ---------------------------------------------------------------- */}
        {/* Footer actions: Send to Canvas + Regenerate                       */}
        {/* ---------------------------------------------------------------- */}
        <div className="px-5 py-4 border-t border-slate-200 bg-slate-50 flex items-center gap-3 flex-wrap">
          {/* Send to Canvas */}
          <button
            type="button"
            onClick={handleSendToCanvas}
            className="flex items-center gap-1.5 px-4 py-2 rounded-lg text-xs font-semibold bg-slate-700 text-white hover:bg-slate-900 transition-colors"
          >
            <svg
              width="12"
              height="12"
              viewBox="0 0 12 12"
              fill="none"
              className="flex-shrink-0"
            >
              <path
                d="M1 6h10M6 1l5 5-5 5"
                stroke="currentColor"
                strokeWidth="1.5"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
            Send to Canvas
          </button>

          <span className="flex-1" />

          {/* Regenerate */}
          <button
            type="button"
            onClick={onRegenerate}
            disabled={generatorLoading || isSelecting}
            className="flex items-center gap-1.5 px-4 py-2 rounded-lg text-xs font-semibold bg-indigo-600 text-white hover:bg-indigo-700 transition-colors disabled:opacity-60 disabled:cursor-not-allowed"
          >
            {generatorLoading ? (
              <>
                <svg
                  className="animate-spin"
                  width="12"
                  height="12"
                  viewBox="0 0 24 24"
                  fill="none"
                >
                  <circle
                    cx="12"
                    cy="12"
                    r="10"
                    stroke="currentColor"
                    strokeWidth="3"
                    strokeDasharray="30 70"
                  />
                </svg>
                Generating…
              </>
            ) : (
              <>
                <svg
                  width="12"
                  height="12"
                  viewBox="0 0 12 12"
                  fill="none"
                >
                  <path
                    d="M10.5 2A5.5 5.5 0 1 1 6.5 1M10.5 2V5M10.5 2H7.5"
                    stroke="currentColor"
                    strokeWidth="1.5"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                </svg>
                Regenerate
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
