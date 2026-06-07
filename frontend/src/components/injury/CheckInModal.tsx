/**
 * CheckInModal — multi-step injury check-in flow.
 *
 * Step 1: Inflammation level (none/mild/moderate/severe)
 * Step 2: Pain triggers — checkboxes for flexion/extension/rotation/load/impact
 * Step 3: Subjective pain slider 0-10
 * Step 4: Load tolerance slider 0-100%
 * Step 5: Optional notes + submit
 */

import { useState } from "react";
import type { InjuryStateCreate, MovementType } from "../../lib/api";

interface Props {
  injuryRegion: string;
  onSubmit: (state: InjuryStateCreate) => Promise<void>;
  onClose: () => void;
}

type InflammationLevel = "none" | "mild" | "moderate" | "severe";
const INFLAMMATION_LEVELS: InflammationLevel[] = ["none", "mild", "moderate", "severe"];
const MOVEMENT_TYPES: MovementType[] = [
  "flexion",
  "extension",
  "rotation",
  "load",
  "impact",
];

const PAIN_EMOJI: Record<number, string> = {
  0: "😊",
  1: "🙂",
  2: "😐",
  3: "😕",
  4: "😟",
  5: "😣",
  6: "😩",
  7: "😰",
  8: "😱",
  9: "😭",
  10: "🔥",
};

const INFLAMMATION_STYLES: Record<
  InflammationLevel,
  { selected: string; unselected: string; label: string; desc: string }
> = {
  none: {
    selected: "bg-emerald-600 text-white border-emerald-600",
    unselected: "bg-white text-slate-700 border-slate-300 hover:border-emerald-400",
    label: "None",
    desc: "No swelling or warmth",
  },
  mild: {
    selected: "bg-amber-500 text-white border-amber-500",
    unselected: "bg-white text-slate-700 border-slate-300 hover:border-amber-400",
    label: "Mild",
    desc: "Slight puffiness",
  },
  moderate: {
    selected: "bg-orange-500 text-white border-orange-500",
    unselected: "bg-white text-slate-700 border-slate-300 hover:border-orange-400",
    label: "Moderate",
    desc: "Noticeable swelling",
  },
  severe: {
    selected: "bg-red-600 text-white border-red-600",
    unselected: "bg-white text-slate-700 border-slate-300 hover:border-red-400",
    label: "Severe",
    desc: "Significant swelling / heat",
  },
};

const TOTAL_STEPS = 5;

export function CheckInModal({ injuryRegion, onSubmit, onClose }: Props) {
  const [step, setStep] = useState(1);
  const [inflammation, setInflammation] = useState<InflammationLevel>("none");
  const [painOn, setPainOn] = useState<Set<MovementType>>(new Set());
  const [subjectivePain, setSubjectivePain] = useState(3);
  const [loadTolerance, setLoadTolerance] = useState(70);
  const [notes, setNotes] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  const toggleMovement = (mt: MovementType) => {
    setPainOn((prev) => {
      const next = new Set(prev);
      if (next.has(mt)) next.delete(mt);
      else next.add(mt);
      return next;
    });
  };

  const handleSubmit = async () => {
    setIsSubmitting(true);
    setSubmitError(null);
    try {
      await onSubmit({
        inflammation,
        pain_on: Array.from(painOn),
        subjective_pain: subjectivePain,
        load_tolerance_pct: loadTolerance / 100,
        notes: notes.trim() || undefined,
      });
      onClose();
    } catch (err) {
      setSubmitError(
        err instanceof Error ? err.message : "Submission failed"
      );
    } finally {
      setIsSubmitting(false);
    }
  };

  const canNext = step < TOTAL_STEPS;
  const canBack = step > 1;

  return (
    // Backdrop
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
      onClick={(e) => e.target === e.currentTarget && onClose()}
    >
      <div className="w-full max-w-md bg-white rounded-2xl shadow-xl overflow-hidden">
        {/* Header */}
        <div className="bg-indigo-600 px-6 py-4">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-white font-semibold">Injury Check-In</h2>
              <p className="text-indigo-200 text-sm">{injuryRegion}</p>
            </div>
            <button
              onClick={onClose}
              className="text-indigo-200 hover:text-white transition-colors"
              aria-label="Close"
            >
              ✕
            </button>
          </div>

          {/* Step indicator */}
          <div className="flex items-center gap-1 mt-3">
            {Array.from({ length: TOTAL_STEPS }, (_, i) => (
              <div
                key={i}
                className={`h-1 flex-1 rounded-full transition-colors ${
                  i < step ? "bg-white" : "bg-indigo-400"
                }`}
              />
            ))}
          </div>
          <p className="text-indigo-200 text-xs mt-1">
            Step {step} of {TOTAL_STEPS}
          </p>
        </div>

        {/* Body */}
        <div className="px-6 py-5 min-h-48">
          {/* Step 1: Inflammation */}
          {step === 1 && (
            <div>
              <h3 className="text-base font-semibold text-slate-800 mb-1">
                Inflammation level
              </h3>
              <p className="text-sm text-slate-500 mb-4">
                How much swelling or warmth do you feel around the {injuryRegion}?
              </p>
              <div className="grid grid-cols-2 gap-3">
                {INFLAMMATION_LEVELS.map((level) => {
                  const s = INFLAMMATION_STYLES[level];
                  const isSelected = inflammation === level;
                  return (
                    <button
                      key={level}
                      onClick={() => setInflammation(level)}
                      className={`rounded-xl border-2 p-3 text-left transition-all ${
                        isSelected ? s.selected : s.unselected
                      }`}
                    >
                      <p className="font-semibold text-sm">{s.label}</p>
                      <p
                        className={`text-xs mt-0.5 ${
                          isSelected ? "opacity-80" : "text-slate-400"
                        }`}
                      >
                        {s.desc}
                      </p>
                    </button>
                  );
                })}
              </div>
            </div>
          )}

          {/* Step 2: Pain triggers */}
          {step === 2 && (
            <div>
              <h3 className="text-base font-semibold text-slate-800 mb-1">
                Pain triggers
              </h3>
              <p className="text-sm text-slate-500 mb-4">
                Which movements provoke pain today? Select all that apply.
              </p>
              <div className="space-y-2">
                {MOVEMENT_TYPES.map((mt) => {
                  const checked = painOn.has(mt);
                  return (
                    <label
                      key={mt}
                      className={`flex items-center gap-3 rounded-lg border-2 px-4 py-3 cursor-pointer transition-all ${
                        checked
                          ? "border-indigo-500 bg-indigo-50"
                          : "border-slate-200 hover:border-indigo-300"
                      }`}
                    >
                      <input
                        type="checkbox"
                        checked={checked}
                        onChange={() => toggleMovement(mt)}
                        className="w-4 h-4 accent-indigo-600"
                      />
                      <span className="text-sm font-medium text-slate-700 capitalize">
                        {mt}
                      </span>
                    </label>
                  );
                })}
              </div>
              {painOn.size === 0 && (
                <p className="mt-3 text-xs text-emerald-600 bg-emerald-50 rounded-lg px-3 py-2">
                  No pain triggers — great sign!
                </p>
              )}
            </div>
          )}

          {/* Step 3: Subjective pain */}
          {step === 3 && (
            <div>
              <h3 className="text-base font-semibold text-slate-800 mb-1">
                Subjective pain level
              </h3>
              <p className="text-sm text-slate-500 mb-6">
                On a scale from 0 (no pain) to 10 (worst imaginable), how does
                the {injuryRegion} feel right now?
              </p>

              <div className="text-center mb-4">
                <span className="text-5xl" role="img" aria-label={`Pain level ${subjectivePain}`}>
                  {PAIN_EMOJI[subjectivePain]}
                </span>
                <p className="mt-2 text-3xl font-bold text-indigo-600">
                  {subjectivePain}
                  <span className="text-lg text-slate-400 font-normal">/10</span>
                </p>
              </div>

              <input
                type="range"
                min={0}
                max={10}
                step={1}
                value={subjectivePain}
                onChange={(e) => setSubjectivePain(Number(e.target.value))}
                className="w-full accent-indigo-600"
              />
              <div className="flex justify-between mt-1 text-xs text-slate-400">
                <span>0 — No pain</span>
                <span>10 — Worst pain</span>
              </div>
            </div>
          )}

          {/* Step 4: Load tolerance */}
          {step === 4 && (
            <div>
              <h3 className="text-base font-semibold text-slate-800 mb-1">
                Load tolerance
              </h3>
              <p className="text-sm text-slate-500 mb-6">
                What percentage of your normal training intensity feels safe
                today? This caps the planned workout intensity.
              </p>

              <div className="text-center mb-4">
                <p className="text-4xl font-bold text-indigo-600">
                  {loadTolerance}
                  <span className="text-xl text-slate-400 font-normal">%</span>
                </p>
                <p className="text-sm text-slate-500 mt-1">of normal intensity</p>
              </div>

              <input
                type="range"
                min={0}
                max={100}
                step={5}
                value={loadTolerance}
                onChange={(e) => setLoadTolerance(Number(e.target.value))}
                className="w-full accent-indigo-600"
              />
              <div className="flex justify-between mt-1 text-xs text-slate-400">
                <span>0% — Rest only</span>
                <span>100% — Full load</span>
              </div>
            </div>
          )}

          {/* Step 5: Notes + submit */}
          {step === 5 && (
            <div>
              <h3 className="text-base font-semibold text-slate-800 mb-1">
                Additional notes
              </h3>
              <p className="text-sm text-slate-500 mb-4">
                Any other observations about how you feel today? (Optional)
              </p>
              <textarea
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                placeholder="e.g. Morning stiffness that eases with movement..."
                rows={3}
                className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-900 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-indigo-500 resize-none"
              />

              {/* Summary */}
              <div className="mt-4 bg-slate-50 rounded-lg p-3 space-y-1 text-xs text-slate-600">
                <p>
                  <span className="font-medium">Inflammation:</span>{" "}
                  <span className="capitalize">{inflammation}</span>
                </p>
                <p>
                  <span className="font-medium">Pain triggers:</span>{" "}
                  {painOn.size > 0
                    ? Array.from(painOn).join(", ")
                    : "none"}
                </p>
                <p>
                  <span className="font-medium">Subjective pain:</span>{" "}
                  {subjectivePain}/10
                </p>
                <p>
                  <span className="font-medium">Load tolerance:</span>{" "}
                  {loadTolerance}%
                </p>
              </div>

              {submitError && (
                <p className="mt-3 text-sm text-red-600 bg-red-50 rounded-lg px-3 py-2">
                  {submitError}
                </p>
              )}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-6 pb-5 flex items-center justify-between gap-3">
          <button
            onClick={canBack ? () => setStep((s) => s - 1) : onClose}
            className="text-sm text-slate-500 hover:text-slate-700 font-medium"
          >
            {canBack ? "Back" : "Cancel"}
          </button>

          {canNext ? (
            <button
              onClick={() => setStep((s) => s + 1)}
              className="bg-indigo-600 hover:bg-indigo-700 text-white font-medium rounded-lg px-5 py-2 text-sm transition-colors"
            >
              Next
            </button>
          ) : (
            <button
              onClick={handleSubmit}
              disabled={isSubmitting}
              className="bg-indigo-600 hover:bg-indigo-700 disabled:opacity-60 text-white font-medium rounded-lg px-5 py-2 text-sm transition-colors"
            >
              {isSubmitting ? "Saving..." : "Save check-in"}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
