/**
 * AnalyticsPanel — member analytics charts (rehomed from the old Copilot tab).
 *
 * Biomarker KPIs + adherence / sleep / injury-progress charts, derived from the
 * active member's KG2 data. The Copilot itself now lives in the floating dock.
 */

import type { MemberContext, InjuryState } from "../../lib/api";
import { BiomarkersCard } from "../charts/BiomarkersCard";
import { AdherenceChart } from "../charts/AdherenceChart";
import { SleepChart } from "../charts/SleepChart";
import { InjuryProgressChart } from "../charts/InjuryProgressChart";

interface Props {
  memberCtx: MemberContext | null;
  injuryHistory?: InjuryState[];
  injuryLabel?: string;
}

export function AnalyticsPanel({ memberCtx, injuryHistory = [], injuryLabel }: Props) {
  if (!memberCtx) {
    return <p className="text-sm text-ink-faint">Loading analytics…</p>;
  }

  return (
    <div className="space-y-6">
      <div>
        <p className="eyebrow mb-1">Analytics</p>
        <h3 className="font-display text-2xl font-light text-ink">
          {memberCtx.profile.name}'s signals
        </h3>
        <p className="mt-1 text-sm text-ink-soft">
          Biomarkers, adherence, sleep, and recovery — straight from the member graph.
        </p>
      </div>

      <div className="rounded-2xl border border-line bg-surface p-6 space-y-6">
        <BiomarkersCard
          restingHr={memberCtx.biomarkers.resting_hr_bpm}
          hrv={memberCtx.biomarkers.hrv_ms}
          weightTrend={memberCtx.biomarkers.weight_trend_kg}
        />

        <AdherenceChart data={memberCtx.adherence.weekly_completion_pct} />

        <SleepChart sleepHours={memberCtx.biomarkers.sleep_hours_last_7_days} />

        {injuryHistory.length > 0 && (
          <InjuryProgressChart history={injuryHistory} injuryLabel={injuryLabel ?? "Injury"} />
        )}
      </div>
    </div>
  );
}
