/**
 * VariantChooser — renders the 3 returned variants as cards side-by-side.
 *
 * Each card is headed by its optimizes_for / stimulus label.
 * Selecting a card calls POST /api/generate/select; the selected variant then
 * expands into the full PlanDisplay below the chooser.
 */

import type { WorkoutVariant } from "../../lib/api";
import { PlanDisplay } from "./PlanDisplay";

// ---------------------------------------------------------------------------
// Variant accent colours
// ---------------------------------------------------------------------------

const VARIANT_STYLES: Record<
  string,
  { border: string; header: string; badge: string; pill: string }
> = {
  strength: {
    border: "border-indigo-300",
    header: "bg-indigo-600",
    badge:  "bg-indigo-100 text-indigo-700",
    pill:   "bg-indigo-600 text-white hover:bg-indigo-700",
  },
  conditioning: {
    border: "border-orange-300",
    header: "bg-orange-500",
    badge:  "bg-orange-100 text-orange-700",
    pill:   "bg-orange-500 text-white hover:bg-orange-600",
  },
  mobility: {
    border: "border-green-300",
    header: "bg-green-600",
    badge:  "bg-green-100 text-green-700",
    pill:   "bg-green-600 text-white hover:bg-green-700",
  },
};

const DEFAULT_STYLE = {
  border: "border-slate-300",
  header: "bg-slate-500",
  badge:  "bg-slate-100 text-slate-600",
  pill:   "bg-slate-600 text-white hover:bg-slate-700",
};

function variantStyle(variantId: string) {
  return VARIANT_STYLES[variantId] ?? DEFAULT_STYLE;
}

// ---------------------------------------------------------------------------
// VariantCard
// ---------------------------------------------------------------------------

interface VariantCardProps {
  variant: WorkoutVariant;
  isSelected: boolean;
  isSelecting: boolean;
  onSelect: (variantId: string) => void;
}

function VariantCard({
  variant,
  isSelected,
  isSelecting,
  onSelect,
}: VariantCardProps) {
  const s = variantStyle(variant.variant_id);

  return (
    <div
      className={`flex-1 min-w-0 rounded-xl border-2 overflow-hidden transition-all ${
        isSelected ? s.border + " ring-2 ring-offset-1 ring-indigo-300" : "border-slate-200"
      }`}
    >
      {/* Card header */}
      <div className={`${s.header} px-4 py-3`}>
        <p className="text-xs font-bold text-white/70 uppercase tracking-wide">
          {variant.variant_id}
        </p>
        <h4 className="text-sm font-semibold text-white leading-tight mt-0.5">
          {variant.label}
        </h4>
      </div>

      {/* Card body */}
      <div className="p-4 space-y-3 bg-white">
        {/* Optimizes-for pill */}
        <span
          className={`inline-block text-xs font-medium px-2.5 py-1 rounded-full ${s.badge}`}
        >
          {variant.optimizes_for}
        </span>

        {/* Key stats */}
        <div className="grid grid-cols-2 gap-2 text-xs text-slate-600">
          <div>
            <span className="font-semibold text-slate-500">Duration</span>
            <br />
            {variant.plan.total_minutes} min
          </div>
          <div>
            <span className="font-semibold text-slate-500">Exercises</span>
            <br />
            {
              variant.plan.warmup.length +
              variant.plan.main.length +
              variant.plan.cooldown.length
            }{" "}
            total
          </div>
        </div>

        {/* Stimulus teaser */}
        {variant.plan.stimulus && (
          <p className="text-xs text-slate-600 leading-relaxed line-clamp-2">
            {variant.plan.stimulus}
          </p>
        )}

        {/* Select button */}
        <button
          type="button"
          disabled={isSelecting}
          onClick={() => onSelect(variant.variant_id)}
          className={`w-full rounded-lg py-2 text-xs font-semibold transition-colors ${
            isSelected
              ? s.pill + " opacity-90 cursor-default"
              : "border border-slate-200 text-slate-600 hover:border-slate-300 hover:bg-slate-50"
          } disabled:opacity-60`}
        >
          {isSelected ? "Selected" : isSelecting ? "Selecting..." : "Select this variant"}
        </button>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// VariantChooser
// ---------------------------------------------------------------------------

interface VariantChooserProps {
  variants: WorkoutVariant[];
  selectedVariant: WorkoutVariant | null;
  isSelecting: boolean;
  onSelect: (variantId: string) => void;
}

export function VariantChooser({
  variants,
  selectedVariant,
  isSelecting,
  onSelect,
}: VariantChooserProps) {
  return (
    <div className="space-y-6">
      {/* 3 cards side-by-side */}
      <div className="flex gap-4 flex-wrap lg:flex-nowrap">
        {variants.map((v) => (
          <VariantCard
            key={v.variant_id}
            variant={v}
            isSelected={selectedVariant?.variant_id === v.variant_id}
            isSelecting={isSelecting}
            onSelect={onSelect}
          />
        ))}
      </div>

      {/* Expanded plan display for the selected variant */}
      {selectedVariant && (
        <div className="rounded-xl border border-slate-200 bg-slate-50 p-6 space-y-4">
          <div className="flex items-center justify-between">
            <h4 className="text-sm font-semibold text-slate-700">
              {selectedVariant.label} — Full Plan
            </h4>
            <span
              className={`text-xs font-medium px-2.5 py-1 rounded-full ${
                variantStyle(selectedVariant.variant_id).badge
              }`}
            >
              {selectedVariant.variant_id}
            </span>
          </div>

          <PlanDisplay
            plan={selectedVariant.plan}
            loadCapPct={selectedVariant.provenance.load_tolerance_pct}
          />
        </div>
      )}
    </div>
  );
}
