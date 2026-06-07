/**
 * MemberSwitcher — client roster in the left rail.
 *
 * Populated from GET /api/members via the active-member context. Switching
 * re-keys all hooks (injury, generator, copilot) to the selected member_id.
 * Each entry uses the member's portrait; a quiet dot marks today's send.
 */

import { useActiveMember } from "../../state/activeMember";
import { memberArt } from "../../lib/imagery";

const CHURN_DOT: Record<string, string> = {
  elevated: "bg-orange-500",
  high: "bg-clay",
  low: "bg-emerald-500",
  moderate: "bg-amber-500",
};

export function MemberSwitcher() {
  const { members, activeMember, switchMember } = useActiveMember();

  if (members.length === 0) {
    return <div className="px-3 py-2 text-xs text-ink-faint">Loading…</div>;
  }

  return (
    <div className="space-y-1">
      {members.map((m) => {
        const isActive = activeMember?.member_id === m.member_id;
        const art = memberArt(m.member_id);
        return (
          <button
            key={m.member_id}
            onClick={() => switchMember(m.member_id)}
            className={`group w-full rounded-xl px-3 py-2.5 text-left transition-colors ${
              isActive ? "bg-sand" : "hover:bg-sand/60"
            }`}
          >
            <div className="flex items-center gap-3">
              {/* Portrait avatar */}
              <span
                className="relative flex h-9 w-9 flex-shrink-0 items-center justify-center overflow-hidden rounded-full text-xs font-semibold text-white"
                style={{ background: art.gradient }}
              >
                <img
                  src={art.portrait}
                  alt=""
                  className="h-full w-full object-cover"
                  onError={(e) => {
                    e.currentTarget.style.display = "none";
                    e.currentTarget.parentElement!.textContent = m.name.charAt(0);
                  }}
                />
                {m.workout_sent_today && (
                  <span
                    className="absolute -bottom-0.5 -right-0.5 h-3.5 w-3.5 rounded-full bg-emerald-500 ring-2 ring-canvas"
                    title="Workout sent today"
                  />
                )}
              </span>

              <div className="min-w-0 flex-1">
                <p
                  className={`truncate text-sm ${
                    isActive ? "font-medium text-ink" : "text-ink-soft"
                  }`}
                >
                  {m.name}
                </p>
                <div className="mt-0.5 flex items-center gap-1.5">
                  <span
                    className={`h-1.5 w-1.5 rounded-full ${
                      CHURN_DOT[m.churn_risk_level] ?? "bg-ink-faint"
                    }`}
                  />
                  <span className="text-[0.7rem] text-ink-faint">
                    {m.churn_risk_level} risk
                  </span>
                </div>
              </div>

              {/* Active marker */}
              <span
                className={`h-1.5 w-1.5 rounded-full bg-clay transition-opacity ${
                  isActive ? "opacity-100" : "opacity-0"
                }`}
              />
            </div>
          </button>
        );
      })}
    </div>
  );
}
