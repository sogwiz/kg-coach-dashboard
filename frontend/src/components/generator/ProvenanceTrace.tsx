/**
 * ProvenanceTrace — collapsible panel listing filtered-out exercises + reasons.
 *
 * Uses the TraceSummary from the backend (trace_summary field) which includes
 * the shared filter trace across all three variants: safe_count, removed list
 * with reasons (injury-state-based filtering, equipment, dislikes), and
 * load_tolerance_pct.
 */

import { useState } from "react";
import type { TraceSummary } from "../../lib/api";

interface ProvenanceTraceProps {
  traceSummary: TraceSummary;
  healingPhase?: string | null;
  injuryRegion?: string | null;
}

function reasonBadgeClass(reason: string): string {
  const r = reason.toLowerCase();
  if (r.includes("movement type") || r.includes("pain") || r.includes("stresses injured") || r.includes("injury")) {
    return "bg-red-100 text-red-700";
  }
  if (r.includes("equipment")) {
    return "bg-amber-100 text-amber-700";
  }
  if (r.includes("dislike")) {
    return "bg-purple-100 text-purple-700";
  }
  return "bg-slate-100 text-slate-600";
}

export function ProvenanceTrace({
  traceSummary,
  healingPhase,
  injuryRegion,
}: ProvenanceTraceProps) {
  const [open, setOpen] = useState(false);

  const { safe_count, removed_count, load_tolerance_pct, stale_check_in, removed } = traceSummary;

  return (
    <div className="rounded-xl border border-slate-200 bg-white overflow-hidden">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-center justify-between px-4 py-3 hover:bg-slate-50 transition-colors"
      >
        <div className="flex items-center gap-2">
          <span className="text-xs font-semibold text-slate-700">
            Safety filter provenance
          </span>
          <span className="text-xs bg-green-100 text-green-700 px-2 py-0.5 rounded-full font-medium">
            {safe_count} safe
          </span>
          {removed_count > 0 && (
            <span className="text-xs bg-red-100 text-red-700 px-2 py-0.5 rounded-full font-medium">
              {removed_count} filtered
            </span>
          )}
          {load_tolerance_pct < 1.0 && (
            <span className="text-xs bg-amber-100 text-amber-700 px-2 py-0.5 rounded-full font-medium">
              Load cap {Math.round(load_tolerance_pct * 100)}%
            </span>
          )}
          {stale_check_in && (
            <span className="text-xs bg-orange-100 text-orange-700 px-2 py-0.5 rounded-full font-medium">
              Stale check-in
            </span>
          )}
        </div>
        <span className={`text-slate-400 text-sm transition-transform duration-200 ${open ? "rotate-180" : ""}`}>
          v
        </span>
      </button>

      {open && (
        <div className="border-t border-slate-100 px-4 py-4 space-y-4">
          {/* Summary stats */}
          <div className="grid grid-cols-2 gap-3 text-xs text-slate-600">
            <div className="rounded-lg bg-slate-50 px-3 py-2">
              <p className="font-semibold text-slate-500 mb-0.5">Safe exercises</p>
              <p className="font-bold text-slate-800 text-sm">{safe_count}</p>
            </div>
            <div className="rounded-lg bg-slate-50 px-3 py-2">
              <p className="font-semibold text-slate-500 mb-0.5">Filtered out</p>
              <p className="font-bold text-slate-800 text-sm">{removed_count}</p>
            </div>
            {healingPhase && (
              <div className="rounded-lg bg-slate-50 px-3 py-2">
                <p className="font-semibold text-slate-500 mb-0.5">Healing phase</p>
                <p className="font-bold text-slate-800 text-sm capitalize">{healingPhase}</p>
              </div>
            )}
            {injuryRegion && (
              <div className="rounded-lg bg-slate-50 px-3 py-2">
                <p className="font-semibold text-slate-500 mb-0.5">Injury region</p>
                <p className="font-bold text-slate-800 text-sm capitalize">{injuryRegion}</p>
              </div>
            )}
          </div>

          {/* Filtered exercises list */}
          {removed.length > 0 ? (
            <div>
              <h5 className="text-xs font-semibold text-slate-600 mb-2">
                Exercises filtered out
              </h5>
              <ul className="space-y-2">
                {removed.map((item) => (
                  <li
                    key={item.id}
                    className="flex items-start gap-2 rounded-lg border border-slate-100 bg-slate-50 px-3 py-2"
                  >
                    <span className="text-red-400 mt-0.5 flex-shrink-0 text-sm">x</span>
                    <div className="flex-1 min-w-0">
                      <p className="text-xs font-medium text-slate-700">{item.name}</p>
                      <p className="text-xs text-slate-500 leading-relaxed">{item.reason}</p>
                    </div>
                    <span
                      className={`flex-shrink-0 text-xs px-2 py-0.5 rounded-full font-medium ${reasonBadgeClass(item.reason)}`}
                    >
                      {item.reason.toLowerCase().includes("movement type") || item.reason.toLowerCase().includes("stresses injured")
                        ? "Injury"
                        : item.reason.toLowerCase().includes("equipment")
                        ? "Equipment"
                        : item.reason.toLowerCase().includes("dislike")
                        ? "Preference"
                        : "Filtered"}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          ) : (
            <p className="text-xs text-slate-400">
              No exercises were filtered out — all candidates passed the safety gate.
            </p>
          )}
        </div>
      )}
    </div>
  );
}
