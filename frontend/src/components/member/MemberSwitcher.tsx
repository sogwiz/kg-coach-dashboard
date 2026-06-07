/**
 * MemberSwitcher — segmented control to switch between members.
 *
 * Populated from GET /api/members via the active-member context.
 * Switching re-keys all hooks (injury, generator, copilot) to the selected
 * member_id by updating the shared activeMember state.
 */

import { useActiveMember } from "../../state/activeMember";

const CHURN_COLOR: Record<string, string> = {
  elevated: "text-amber-600",
  high: "text-red-600",
  low: "text-emerald-600",
  moderate: "text-orange-500",
};

export function MemberSwitcher() {
  const { members, activeMember, switchMember } = useActiveMember();

  if (members.length === 0) {
    return (
      <div className="px-3 py-2 text-xs text-slate-400">Loading members…</div>
    );
  }

  return (
    <div className="space-y-1">
      <p className="px-3 text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">
        Members
      </p>
      {members.map((m) => {
        const isActive = activeMember?.member_id === m.member_id;
        return (
          <button
            key={m.member_id}
            onClick={() => switchMember(m.member_id)}
            className={`w-full text-left rounded-lg px-3 py-2 transition-colors ${
              isActive
                ? "bg-indigo-50 text-indigo-700"
                : "text-slate-700 hover:bg-slate-100"
            }`}
          >
            <div className="flex items-center gap-2">
              {/* Avatar */}
              <span
                className={`flex-shrink-0 w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold ${
                  isActive
                    ? "bg-indigo-600 text-white"
                    : "bg-slate-200 text-slate-600"
                }`}
              >
                {m.name.charAt(0)}
              </span>

              <div className="min-w-0">
                <p className="text-sm font-medium truncate">{m.name}</p>
                <p
                  className={`text-xs ${
                    CHURN_COLOR[m.churn_risk_level] ?? "text-slate-400"
                  }`}
                >
                  {m.churn_risk_level} churn risk
                </p>
              </div>
            </div>
          </button>
        );
      })}
    </div>
  );
}
