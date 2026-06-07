/**
 * DecisionTrace — renders the backend decision_trace (list of DecisionStep).
 *
 * Shows an ordered, collapsible list of pipeline steps:
 *   1. resolve_prompt (deterministic)
 *   2. load_constraints (deterministic)
 *   3. part_of_traversal (deterministic)
 *   4. movement_type_exclusion (deterministic)
 *   5. equipment_gate (deterministic)
 *   6. llm_structuring (llm)
 *
 * Each step is expandable to reveal inputs/outputs.
 * If a LangSmith run URL is present in the llm_structuring outputs, it is
 * rendered as a link.
 */

import { useState } from "react";
import type { DecisionStep } from "../../lib/api";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const STEP_LABELS: Record<string, string> = {
  resolve_prompt:          "Resolve prompt concepts",
  load_constraints:        "Load member constraints",
  part_of_traversal:       "SNOMED part-of traversal",
  movement_type_exclusion: "Movement-type exclusion",
  equipment_gate:          "Equipment gate",
  llm_structuring:         "LLM structuring",
};

/** Format a phase wall-clock time for the tiny in-trace timing line. */
function formatDuration(ms: number): string {
  return ms >= 1000 ? `${(ms / 1000).toFixed(2)} s` : `${ms.toFixed(1)} ms`;
}

const KIND_BADGE: Record<"deterministic" | "llm", string> = {
  deterministic: "bg-slate-100 text-slate-600",
  llm:           "bg-violet-100 text-violet-700",
};

function humaniseKey(key: string): string {
  return key.replace(/_/g, " ");
}

function formatValue(val: unknown): string {
  if (val === null || val === undefined) return "—";
  if (Array.isArray(val)) return val.length === 0 ? "[]" : val.join(", ");
  if (typeof val === "object") return JSON.stringify(val, null, 2);
  return String(val);
}

// ---------------------------------------------------------------------------
// StepRow
// ---------------------------------------------------------------------------

interface StepRowProps {
  step: DecisionStep;
  index: number;
}

function StepRow({ step, index }: StepRowProps) {
  const [open, setOpen] = useState(false);

  const label = STEP_LABELS[step.name] ?? step.name.replace(/_/g, " ");
  const langsmithUrl =
    step.kind === "llm"
      ? (step.outputs["langsmith_url"] as string | undefined) ?? null
      : null;
  const langsmithProject =
    step.kind === "llm"
      ? (step.outputs["langsmith_project"] as string | undefined) ?? null
      : null;

  return (
    <li className="rounded-xl border border-slate-200 bg-white overflow-hidden">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-center gap-3 px-4 py-3 text-left hover:bg-slate-50 transition-colors"
      >
        {/* Step number */}
        <div className="w-5 h-5 rounded-full bg-indigo-100 flex items-center justify-center flex-shrink-0">
          <span className="text-xs font-bold text-indigo-600">{index + 1}</span>
        </div>

        {/* Label + kind */}
        <div className="flex-1 min-w-0">
          <span className="text-sm font-medium text-slate-700">{label}</span>
        </div>

        <span
          className={`text-xs font-medium px-2 py-0.5 rounded-full flex-shrink-0 ${KIND_BADGE[step.kind]}`}
        >
          {step.kind}
        </span>

        <span
          className={`text-slate-400 text-sm transition-transform duration-200 flex-shrink-0 ${open ? "rotate-180" : ""}`}
        >
          v
        </span>
      </button>

      {open && (
        <div className="border-t border-slate-100 px-4 py-4 space-y-4">
          {/* Detail */}
          <p className="text-xs text-slate-600 leading-relaxed">{step.detail}</p>

          {/* Phase wall-clock time — very small, expanded view only */}
          {step.duration_ms != null && (
            <p className="text-[10px] text-slate-400 tabular-nums -mt-2">
              phase time · {formatDuration(step.duration_ms)}
            </p>
          )}

          <div className="grid grid-cols-2 gap-4">
            {/* Inputs */}
            {Object.keys(step.inputs).length > 0 && (
              <div>
                <h6 className="text-xs font-bold text-slate-500 uppercase tracking-wide mb-2">
                  Inputs
                </h6>
                <dl className="space-y-1">
                  {Object.entries(step.inputs).map(([k, v]) => (
                    <div key={k} className="text-xs">
                      <dt className="font-medium text-slate-500 capitalize">
                        {humaniseKey(k)}
                      </dt>
                      <dd className="text-slate-700 font-mono text-xs break-all">
                        {formatValue(v)}
                      </dd>
                    </div>
                  ))}
                </dl>
              </div>
            )}

            {/* Outputs */}
            {Object.keys(step.outputs).length > 0 && (
              <div>
                <h6 className="text-xs font-bold text-slate-500 uppercase tracking-wide mb-2">
                  Outputs
                </h6>
                <dl className="space-y-1">
                  {Object.entries(step.outputs)
                    .filter(([k]) => k !== "langsmith_url" && k !== "langsmith_project")
                    .map(([k, v]) => (
                      <div key={k} className="text-xs">
                        <dt className="font-medium text-slate-500 capitalize">
                          {humaniseKey(k)}
                        </dt>
                        <dd className="text-slate-700 font-mono text-xs break-all">
                          {formatValue(v)}
                        </dd>
                      </div>
                    ))}
                </dl>
              </div>
            )}
          </div>

          {/* LangSmith link */}
          {(langsmithUrl || langsmithProject) && (
            <div className="rounded-lg bg-violet-50 border border-violet-200 px-3 py-2 text-xs flex items-center gap-2">
              <span className="text-violet-500 font-medium">LangSmith trace:</span>
              {langsmithUrl ? (
                <a
                  href={langsmithUrl}
                  target="_blank"
                  rel="noreferrer"
                  className="text-violet-700 underline underline-offset-2 hover:text-violet-900"
                >
                  View run
                </a>
              ) : (
                <span className="text-violet-700">
                  Project: <strong>{langsmithProject}</strong>
                </span>
              )}
            </div>
          )}
        </div>
      )}
    </li>
  );
}

// ---------------------------------------------------------------------------
// DecisionTrace
// ---------------------------------------------------------------------------

interface DecisionTraceProps {
  steps: DecisionStep[];
}

export function DecisionTrace({ steps }: DecisionTraceProps) {
  const [open, setOpen] = useState(false);

  if (steps.length === 0) return null;

  const deterministicCount = steps.filter((s) => s.kind === "deterministic").length;
  const llmCount = steps.filter((s) => s.kind === "llm").length;

  return (
    <div className="rounded-xl border border-slate-200 bg-white overflow-hidden">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-center justify-between px-4 py-3 hover:bg-slate-50 transition-colors"
      >
        <div className="flex items-center gap-2">
          <span className="text-xs font-semibold text-slate-700">
            Decision trace
          </span>
          <span className="text-xs bg-slate-100 text-slate-600 px-2 py-0.5 rounded-full font-medium">
            {deterministicCount} deterministic
          </span>
          <span className="text-xs bg-violet-100 text-violet-700 px-2 py-0.5 rounded-full font-medium">
            {llmCount} LLM
          </span>
        </div>
        <span className={`text-slate-400 text-sm transition-transform duration-200 ${open ? "rotate-180" : ""}`}>
          v
        </span>
      </button>

      {open && (
        <div className="border-t border-slate-100 px-4 py-4">
          <ol className="space-y-2">
            {steps.map((step, idx) => (
              <StepRow key={step.name} step={step} index={idx} />
            ))}
          </ol>
        </div>
      )}
    </div>
  );
}
