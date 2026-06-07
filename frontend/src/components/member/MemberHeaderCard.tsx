/**
 * MemberHeaderCard — persistent member identity card shown above the tab nav.
 *
 * Portrait + name + meta line (age · sex · primary goal) on the left; status
 * pills (active injury, churn risk, sent-today) on the right. The centered
 * pill tab bar lives directly beneath this card in the Dashboard.
 */

import type { MemberSummary } from "../../lib/api";
import { memberArt } from "../../lib/imagery";
import { useCopilotDock } from "../../state/copilot";

interface Props {
  member: MemberSummary;
  goalText?: string | null;
  injuryLabel?: string | null;
}

const CHURN_PILL: Record<string, string> = {
  low: "border-emerald-200 bg-emerald-50 text-emerald-700",
  moderate: "border-amber-200 bg-amber-50 text-amber-700",
  elevated: "border-orange-200 bg-orange-50 text-orange-700",
  high: "border-clay/30 bg-clay/5 text-clay",
};

export function MemberHeaderCard({ member, goalText, injuryLabel }: Props) {
  const art = memberArt(member.member_id);
  const { openInbox } = useCopilotDock();
  const churnClass = CHURN_PILL[member.churn_risk_level] ?? "border-line bg-sand text-ink-soft";

  const meta = [
    member.age ? `${member.age}` : null,
    member.sex,
    goalText,
  ]
    .filter(Boolean)
    .join(" · ");

  return (
    <div className="flex items-center gap-5 rounded-2xl border border-line bg-surface px-6 py-5">
      {/* Portrait */}
      <span
        className="flex h-16 w-16 flex-shrink-0 items-center justify-center overflow-hidden rounded-full text-lg font-semibold text-white"
        style={{ background: art.gradient }}
      >
        <img
          src={art.portrait}
          alt=""
          className="h-full w-full object-cover"
          onError={(e) => {
            e.currentTarget.style.display = "none";
            e.currentTarget.parentElement!.textContent = member.name.charAt(0);
          }}
        />
      </span>

      {/* Identity */}
      <div className="min-w-0 flex-1">
        <h2 className="font-display text-2xl font-light leading-tight text-ink">
          {member.name}
        </h2>
        {meta && <p className="mt-1 truncate text-sm text-ink-soft">{meta}</p>}
      </div>

      {/* Status pills */}
      <div className="flex flex-shrink-0 flex-wrap items-center justify-end gap-2">
        {injuryLabel && (
          <span className="rounded-full border border-clay/30 bg-clay/5 px-3 py-1 text-xs font-medium text-clay">
            {injuryLabel}
          </span>
        )}
        <span className={`rounded-full border px-3 py-1 text-xs font-medium ${churnClass}`}>
          churn · {member.churn_risk_level}
        </span>
        {member.workout_sent_today && (
          <span className="rounded-full border border-emerald-200 bg-emerald-50 px-3 py-1 text-xs font-medium text-emerald-700">
            ✓ sent today
          </span>
        )}

        {/* Mail — opens the trainer↔client Inbox */}
        <button
          type="button"
          onClick={() => openInbox()}
          title="Client messages"
          aria-label="Open client inbox"
          className="ml-1 flex h-9 w-9 items-center justify-center rounded-full border border-line text-ink-soft transition-colors hover:border-ink hover:text-ink"
        >
          <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
            <rect x="3" y="5" width="18" height="14" rx="2" />
            <path d="m3 7 9 6 9-6" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </button>
      </div>
    </div>
  );
}
