/**
 * InjuryProgressChart — multi-line chart showing pain level, inflammation,
 * and load tolerance over time from injury check-in history.
 */

import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";
import type { InjuryState } from "../../lib/api";

interface InjuryProgressChartProps {
  history: InjuryState[];
  injuryLabel?: string;
}

const INFLAMMATION_SCORE: Record<string, number> = {
  none: 0,
  mild: 3,
  moderate: 6,
  severe: 10,
};

export function InjuryProgressChart({
  history,
  injuryLabel = "Injury",
}: InjuryProgressChartProps) {
  if (!history || history.length === 0) {
    return (
      <div className="flex items-center justify-center h-32 text-slate-400 text-sm">
        No injury check-in history available.
      </div>
    );
  }

  const sorted = [...history].sort((a, b) =>
    a.recorded_at.localeCompare(b.recorded_at)
  );

  const data = sorted.map((s) => ({
    date: s.recorded_at.slice(0, 10),
    pain: s.subjective_pain,
    inflammation: INFLAMMATION_SCORE[s.inflammation] ?? 0,
    load_tolerance: Math.round(s.load_tolerance_pct * 10), // scale 0-10
  }));

  return (
    <div>
      <p className="text-xs font-medium text-slate-600 mb-2">
        {injuryLabel} — Progress
      </p>
      <ResponsiveContainer width="100%" height={180}>
        <LineChart data={data} margin={{ top: 4, right: 8, bottom: 4, left: -24 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
          <XAxis
            dataKey="date"
            tick={{ fontSize: 10, fill: "#94a3b8" }}
            tickFormatter={(v: string) => v.slice(5)}
          />
          <YAxis domain={[0, 10]} tick={{ fontSize: 10, fill: "#94a3b8" }} />
          <Tooltip
            contentStyle={{ fontSize: 12 }}
            formatter={(v, name) => {
              const val = typeof v === "number" ? v : 0;
              const n = String(name);
              if (n === "load_tolerance") return [`${val * 10}%`, "Load Tolerance"];
              return [val, n === "pain" ? "Subjective Pain" : "Inflammation"];
            }}
          />
          <Legend
            iconSize={10}
            formatter={(v: string) => {
              const labels: Record<string, string> = {
                pain: "Pain (0-10)",
                inflammation: "Inflammation (0-10)",
                load_tolerance: "Load Tolerance (×10%)",
              };
              return labels[v] ?? v;
            }}
            wrapperStyle={{ fontSize: 11 }}
          />
          <Line
            type="monotone"
            dataKey="pain"
            stroke="#ef4444"
            strokeWidth={2}
            dot={{ r: 3 }}
          />
          <Line
            type="monotone"
            dataKey="inflammation"
            stroke="#f59e0b"
            strokeWidth={2}
            dot={{ r: 3 }}
          />
          <Line
            type="monotone"
            dataKey="load_tolerance"
            stroke="#22c55e"
            strokeWidth={2}
            dot={{ r: 3 }}
          />
        </LineChart>
      </ResponsiveContainer>
      <p className="text-xs text-slate-400 mt-1">
        Improving = pain/inflammation down, load tolerance up.
      </p>
    </div>
  );
}
