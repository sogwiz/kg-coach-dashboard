/**
 * MorningBrief — renders coach_brief.morning_tasks with icons by type.
 */

import type { MorningTask } from "../../lib/api";

interface Props {
  tasks: MorningTask[];
  generatedFor?: string;
}

// Map task types to icon characters and colours
const TYPE_STYLES: Record<
  string,
  { icon: string; bg: string; iconColor: string }
> = {
  celebrate: {
    icon: "★",
    bg: "bg-emerald-50 border-emerald-200",
    iconColor: "text-emerald-600",
  },
  review_risk: {
    icon: "!",
    bg: "bg-amber-50 border-amber-200",
    iconColor: "text-amber-600",
  },
  check_in: {
    icon: "?",
    bg: "bg-sky-50 border-sky-200",
    iconColor: "text-sky-600",
  },
  action: {
    icon: "→",
    bg: "bg-indigo-50 border-indigo-200",
    iconColor: "text-indigo-600",
  },
  note: {
    icon: "i",
    bg: "bg-slate-50 border-slate-200",
    iconColor: "text-slate-500",
  },
};

const DEFAULT_STYLE = {
  icon: "·",
  bg: "bg-slate-50 border-slate-200",
  iconColor: "text-slate-500",
};

export function MorningBrief({ tasks, generatedFor }: Props) {
  if (tasks.length === 0) {
    return (
      <div className="bg-white rounded-xl border border-slate-200 p-4">
        <h3 className="text-sm font-semibold text-slate-700 mb-2">
          Morning Brief
        </h3>
        <p className="text-sm text-slate-400">No tasks today.</p>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-xl border border-slate-200 p-4">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-semibold text-slate-700">Morning Brief</h3>
        {generatedFor && (
          <span className="text-xs text-slate-400">{generatedFor}</span>
        )}
      </div>

      <ul className="space-y-2">
        {tasks.map((task, idx) => {
          const style = TYPE_STYLES[task.type] ?? DEFAULT_STYLE;
          return (
            <li
              key={idx}
              className={`flex items-start gap-3 rounded-lg border p-3 ${style.bg}`}
            >
              <span
                className={`flex-shrink-0 w-5 h-5 rounded-full flex items-center justify-center text-xs font-bold ${style.iconColor}`}
                aria-hidden="true"
              >
                {style.icon}
              </span>
              <p className="text-sm text-slate-700 leading-snug">{task.text}</p>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
