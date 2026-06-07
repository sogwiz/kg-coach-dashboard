/**
 * AdherenceChart — Recharts line chart of weekly_completion_pct.
 */

import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
} from "recharts";

interface DataPoint {
  week_of: string;
  pct: number;
}

interface AdherenceChartProps {
  data: DataPoint[];
}

export function AdherenceChart({ data }: AdherenceChartProps) {
  if (!data || data.length === 0) {
    return (
      <div className="flex items-center justify-center h-32 text-slate-400 text-sm">
        No adherence data available.
      </div>
    );
  }

  // Sort oldest to newest
  const sorted = [...data].sort((a, b) =>
    a.week_of.localeCompare(b.week_of)
  );

  return (
    <div>
      <p className="text-xs font-medium text-slate-600 mb-2">
        Weekly Adherence (%)
      </p>
      <ResponsiveContainer width="100%" height={160}>
        <LineChart data={sorted} margin={{ top: 4, right: 8, bottom: 4, left: -24 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
          <XAxis
            dataKey="week_of"
            tick={{ fontSize: 10, fill: "#94a3b8" }}
            tickFormatter={(v: string) => v.slice(5)} // MM-DD
          />
          <YAxis
            domain={[0, 100]}
            tick={{ fontSize: 10, fill: "#94a3b8" }}
            tickFormatter={(v: number) => `${v}%`}
          />
          <Tooltip
            formatter={(v) => [`${v}%`, "Adherence"]}
            labelFormatter={(l) => `Week of ${l}`}
            contentStyle={{ fontSize: 12 }}
          />
          <ReferenceLine y={80} stroke="#22c55e" strokeDasharray="4 4" />
          <Line
            type="monotone"
            dataKey="pct"
            stroke="#6366f1"
            strokeWidth={2}
            dot={{ r: 3, fill: "#6366f1" }}
            activeDot={{ r: 5 }}
          />
        </LineChart>
      </ResponsiveContainer>
      <p className="text-xs text-slate-400 mt-1">Green line = 80% target</p>
    </div>
  );
}
