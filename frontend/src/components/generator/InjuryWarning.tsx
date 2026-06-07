/**
 * InjuryWarning — banner shown when no check-in has been recorded today.
 *
 * Displays the date of the last check-in (if any) and offers an "Update"
 * action that opens the check-in modal via the onCheckIn callback.
 */

import type { InjuryState } from "../../lib/api";

interface InjuryWarningProps {
  /** The most recent injury state (may be from a previous day). */
  lastCheckIn: InjuryState | null;
  /** Whether the check-in is stale (from the backend trace_summary or hook). */
  staleCheckIn: boolean;
  /** Called when the coach clicks "Update check-in". */
  onCheckIn: () => void;
}

function formatDate(isoStr: string): string {
  const d = new Date(isoStr);
  return d.toLocaleDateString(undefined, {
    weekday: "short",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function InjuryWarning({
  lastCheckIn,
  staleCheckIn,
  onCheckIn,
}: InjuryWarningProps) {
  if (!staleCheckIn) return null;

  return (
    <div className="flex items-center gap-3 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm">
      <span className="text-amber-500 text-base leading-none">!</span>
      <p className="flex-1 text-amber-800">
        {lastCheckIn
          ? <>Using last check-in from <strong>{formatDate(lastCheckIn.recorded_at)}</strong>. Results may not reflect today's condition.</>
          : <>No injury check-in on record. Generate will use baseline restrictions.</>}
      </p>
      <button
        onClick={onCheckIn}
        className="flex-shrink-0 rounded-md border border-amber-400 bg-amber-100 px-3 py-1 text-xs font-medium text-amber-800 hover:bg-amber-200 transition-colors"
      >
        Update check-in
      </button>
    </div>
  );
}
