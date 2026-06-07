/**
 * BiomarkersCard — KPI cards for RHR, HRV, and weight trend.
 */

interface BiomarkersCardProps {
  restingHr: number;
  hrv: number;
  weightTrend?: Array<{ date: string; kg: number }>;
}

function KpiCard({
  label,
  value,
  unit,
  status,
}: {
  label: string;
  value: string | number;
  unit: string;
  status?: "good" | "warning" | "neutral";
}) {
  const statusColors = {
    good: "text-green-600",
    warning: "text-amber-600",
    neutral: "text-slate-700",
  };
  const color = statusColors[status ?? "neutral"];

  return (
    <div className="bg-slate-50 rounded-lg p-3 flex flex-col gap-0.5">
      <p className="text-xs text-slate-500">{label}</p>
      <p className={`text-lg font-semibold ${color}`}>
        {value}
        <span className="text-xs font-normal text-slate-400 ml-1">{unit}</span>
      </p>
    </div>
  );
}

export function BiomarkersCard({
  restingHr,
  hrv,
  weightTrend,
}: BiomarkersCardProps) {
  const hrStatus: "good" | "warning" | "neutral" =
    restingHr < 60 ? "good" : restingHr < 80 ? "neutral" : "warning";
  const hrvStatus: "good" | "warning" | "neutral" =
    hrv >= 50 ? "good" : hrv >= 30 ? "neutral" : "warning";

  let weightDisplay = "—";
  let weightTrend7d = "";
  if (weightTrend && weightTrend.length >= 2) {
    const latest = weightTrend[weightTrend.length - 1];
    const earliest = weightTrend[0];
    const diff = latest.kg - earliest.kg;
    weightDisplay = `${latest.kg.toFixed(1)}`;
    weightTrend7d = diff > 0 ? `+${diff.toFixed(1)}` : diff.toFixed(1);
  } else if (weightTrend && weightTrend.length === 1) {
    weightDisplay = `${weightTrend[0].kg.toFixed(1)}`;
  }

  return (
    <div>
      <p className="text-xs font-medium text-slate-600 mb-2">Biomarkers</p>
      <div className="grid grid-cols-3 gap-2">
        <KpiCard
          label="Resting HR"
          value={Math.round(restingHr)}
          unit="bpm"
          status={hrStatus}
        />
        <KpiCard
          label="HRV"
          value={Math.round(hrv)}
          unit="ms"
          status={hrvStatus}
        />
        <KpiCard
          label="Weight"
          value={weightDisplay}
          unit={`kg ${weightTrend7d ? `(${weightTrend7d})` : ""}`}
          status="neutral"
        />
      </div>
    </div>
  );
}
