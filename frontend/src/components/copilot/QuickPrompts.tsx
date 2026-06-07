/**
 * QuickPrompts — palette of common coach questions.
 */

interface QuickPromptsProps {
  onSelect: (prompt: string) => void;
  disabled?: boolean;
  hasInjury?: boolean;
}

const BASE_PROMPTS = [
  "How's adherence?",
  "Plot sleep",
  "Churn risk?",
  "Show my latest labs",
  "How's my recovery (HRV/sleep)?",
  "What are their goals?",
  "Show recent workouts",
];

const INJURY_PROMPTS = [
  "How's my knee healing?",
  "What's the current healing phase?",
  "What can I do today given my injury?",
];

export function QuickPrompts({ onSelect, disabled = false, hasInjury = false }: QuickPromptsProps) {
  const prompts = hasInjury ? [...BASE_PROMPTS, ...INJURY_PROMPTS] : BASE_PROMPTS;

  return (
    <div className="flex flex-wrap gap-1.5">
      {prompts.map((p) => (
        <button
          key={p}
          type="button"
          disabled={disabled}
          onClick={() => onSelect(p)}
          className="rounded-full border border-indigo-200 bg-indigo-50 px-2.5 py-1 text-xs text-indigo-700 hover:bg-indigo-100 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          {p}
        </button>
      ))}
    </div>
  );
}
