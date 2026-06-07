/**
 * HealingPhaseIndicator — visual progress through the four healing phases.
 *
 * Shows acute → subacute → remodeling → return-to-activity with the current
 * phase highlighted.
 */

export type HealingPhase = "acute" | "subacute" | "remodeling" | "rta";

interface Props {
  currentPhase: HealingPhase;
  daysSinceOnset: number;
}

const PHASES: Array<{
  id: HealingPhase;
  label: string;
  shortLabel: string;
  range: string;
}> = [
  { id: "acute", label: "Acute", shortLabel: "Acute", range: "0-7 days" },
  { id: "subacute", label: "Sub-acute", shortLabel: "Sub-acute", range: "7-21 days" },
  { id: "remodeling", label: "Remodeling", shortLabel: "Remodeling", range: "21-90 days" },
  { id: "rta", label: "Return to Activity", shortLabel: "RTA", range: "90+ days" },
];

const PHASE_ORDER: Record<HealingPhase, number> = {
  acute: 0,
  subacute: 1,
  remodeling: 2,
  rta: 3,
};

export function HealingPhaseIndicator({ currentPhase, daysSinceOnset }: Props) {
  const currentIdx = PHASE_ORDER[currentPhase];

  return (
    <div>
      <div className="flex items-center gap-0 relative">
        {PHASES.map((phase, idx) => {
          const isPast = idx < currentIdx;
          const isActive = idx === currentIdx;

          return (
            <div key={phase.id} className="flex-1 flex flex-col items-center relative">
              {/* Connector line (before each step except the first) */}
              {idx > 0 && (
                <div
                  className={`absolute left-0 top-3 h-0.5 w-1/2 -translate-x-full ${
                    isPast || isActive ? "bg-indigo-500" : "bg-slate-200"
                  }`}
                />
              )}
              {/* Connector line (after each step except the last) */}
              {idx < PHASES.length - 1 && (
                <div
                  className={`absolute right-0 top-3 h-0.5 w-1/2 translate-x-full ${
                    isPast ? "bg-indigo-500" : "bg-slate-200"
                  }`}
                />
              )}

              {/* Dot */}
              <div
                className={`relative z-10 w-6 h-6 rounded-full flex items-center justify-center border-2 ${
                  isActive
                    ? "bg-indigo-600 border-indigo-600"
                    : isPast
                    ? "bg-indigo-400 border-indigo-400"
                    : "bg-white border-slate-300"
                }`}
              >
                {isPast && (
                  <svg
                    className="w-3 h-3 text-white"
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                    strokeWidth={3}
                  >
                    <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                  </svg>
                )}
                {isActive && (
                  <div className="w-2 h-2 rounded-full bg-white" />
                )}
              </div>

              {/* Label */}
              <p
                className={`mt-1.5 text-xs text-center leading-tight ${
                  isActive
                    ? "text-indigo-700 font-semibold"
                    : isPast
                    ? "text-indigo-400"
                    : "text-slate-400"
                }`}
              >
                {phase.shortLabel}
              </p>
              <p className="text-xs text-slate-400 text-center hidden sm:block">
                {phase.range}
              </p>
            </div>
          );
        })}
      </div>

      <p className="mt-3 text-xs text-slate-500 text-center">
        Day {daysSinceOnset} since onset &mdash; currently in{" "}
        <strong className="text-indigo-700">
          {PHASES.find((p) => p.id === currentPhase)?.label ?? currentPhase}
        </strong>{" "}
        phase
      </p>
    </div>
  );
}
