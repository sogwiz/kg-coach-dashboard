/**
 * SleepChart — Recharts bar chart of sleep_hours_last_7_days.
 */

import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
  Cell,
} from "recharts";

interface SleepChartProps {
  sleepHours: number[];
}

export function SleepChart({ sleepHours }: SleepChartProps) {
  if (!sleepHours || sleepHours.length === 0) {
    return (
      <div className="flex items-center justify-center h-32 text-slate-400 text-sm">
        No sleep data available.
      </div>
    );
  }

  const days = ["6d ago", "5d ago", "4d ago", "3d ago", "2d ago", "Yesterday", "Today"];
  const data = sleepHours.map((hours, i) => ({
    day: days[days.length - sleepHours.length + i] ?? `Day ${i + 1}`,
    hours,
  }));

  return (
    <div>
      <p className="text-xs font-medium text-slate-600 mb-2">
        Sleep — Past 7 Days (hours)
      </p>
      <ResponsiveContainer width="100%" height={160}>
        <BarChart data={data} margin={{ top: 4, right: 8, bottom: 4, left: -24 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
          <XAxis dataKey="day" tick={{ fontSize: 10, fill: "#94a3b8" }} />
          <YAxis
            domain={[0, 10]}
            tick={{ fontSize: 10, fill: "#94a3b8" }}
            tickFormatter={(v: number) => `${v}h`}
          />
          <Tooltip
            formatter={(v) => [`${v}h`, "Sleep"]}
            contentStyle={{ fontSize: 12 }}
          />
          <ReferenceLine y={7} stroke="#22c55e" strokeDasharray="4 4" />
          <Bar dataKey="hours" radius={[3, 3, 0, 0]}>
            {data.map((entry, i) => (
              <Cell
                key={i}
                fill={entry.hours >= 7 ? "#6366f1" : entry.hours >= 6 ? "#f59e0b" : "#ef4444"}
              />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
      <p className="text-xs text-slate-400 mt-1">Green = 7h target. Yellow/red = below target.</p>
    </div>
  );
}
