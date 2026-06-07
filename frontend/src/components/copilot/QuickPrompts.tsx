/**
 * QuickPrompts — palette of common questions the TRAINER asks the copilot.
 *
 * The copilot is a trainer↔AI assistant: the coach consults it ABOUT the active
 * client. Prompts are therefore phrased in the third person ("How's Jordan's
 * knee healing?"), never the client's first person ("How's my knee?"), and are
 * interpolated with the active client's name + injury region so the voice is
 * unambiguous.
 */

interface QuickPromptsProps {
  onSelect: (prompt: string) => void;
  disabled?: boolean;
  /** Active client's name (first name preferred) — used to phrase the prompts. */
  clientName?: string | null;
  /** Active injury region, e.g. "left knee". When set, injury prompts appear. */
  injury?: string | null;
}

export function QuickPrompts({
  onSelect,
  disabled = false,
  clientName,
  injury,
}: QuickPromptsProps) {
  // First name keeps the chips short; fall back to a neutral third-person noun.
  const who = (clientName?.trim().split(" ")[0]) || "this client";
  const their = clientName?.trim() ? `${who}'s` : "their";

  const basePrompts = [
    `How's ${their} adherence?`,
    `Plot ${their} sleep`,
    `${who === "this client" ? "Their" : `${who}'s`} churn risk?`,
    `Show ${their} latest labs`,
    `How's ${their} recovery (HRV/sleep)?`,
    `What are ${their} goals?`,
    `Show ${their} recent workouts`,
  ];

  const injuryPrompts = injury
    ? [
        `How's ${their} ${injury} healing?`,
        `What's ${their} current healing phase?`,
        `What should ${who} train today given the ${injury}?`,
      ]
    : [];

  const prompts = [...basePrompts, ...injuryPrompts];

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
