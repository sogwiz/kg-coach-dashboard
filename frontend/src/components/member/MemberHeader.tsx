/**
 * MemberHeader — name, avatar, quick stats for the selected member.
 *
 * Shows: name, age/sex, active injury, adherence (last week pct), churn risk badge.
 */

import type { MemberSummary } from "../../lib/api";

interface Props {
  member: MemberSummary;
  adherencePct?: number | null;
}

const CHURN_BADGE: Record<
  string,
  { bg: string; text: string; label: string }
> = {
  elevated: { bg: "bg-amber-100", text: "text-amber-700", label: "Elevated churn risk" },
  high: { bg: "bg-red-100", text: "text-red-700", label: "High churn risk" },
  low: { bg: "bg-emerald-100", text: "text-emerald-700", label: "Low churn risk" },
  moderate: { bg: "bg-orange-100", text: "text-orange-700", label: "Moderate churn risk" },
};

export function MemberHeader({ member, adherencePct }: Props) {
  const churn = CHURN_BADGE[member.churn_risk_level] ?? {
    bg: "bg-slate-100",
    text: "text-slate-600",
    label: member.churn_risk_level,
  };

  return (
    <div className="flex items-center gap-4 p-4 bg-white rounded-xl border border-slate-200">
      {/* Avatar */}
      <div className="flex-shrink-0 w-12 h-12 rounded-full bg-indigo-600 flex items-center justify-center">
        <span className="text-white font-bold text-lg">
          {member.name.charAt(0)}
        </span>
      </div>

      {/* Name + meta */}
      <div className="flex-1 min-w-0">
        <h2 className="text-lg font-semibold text-slate-900 truncate">
          {member.name}
        </h2>
        <p className="text-sm text-slate-500">
          {member.age}yo {member.sex}
          {member.active_injury ? (
            <span className="ml-2 text-slate-400">· {member.active_injury}</span>
          ) : null}
        </p>
      </div>

      {/* Quick stats */}
      <div className="flex items-center gap-3 flex-shrink-0">
        {adherencePct !== null && adherencePct !== undefined && (
          <div className="text-center">
            <p className="text-xl font-bold text-slate-900">
              {Math.round(adherencePct)}%
            </p>
            <p className="text-xs text-slate-500">Adherence</p>
          </div>
        )}
        <span
          className={`inline-flex items-center rounded-full px-3 py-1 text-xs font-medium ${churn.bg} ${churn.text}`}
        >
          {churn.label}
        </span>
      </div>
    </div>
  );
}
