/**
 * GeneratorPanel — free-text prompt + time-window slider + generate button.
 *
 * Calls POST /api/generate with {prompt, time_window_minutes, member_id} via
 * the useGenerator hook. The coach's prompt determines the session modality —
 * the generator returns a single workout with stimulus gauges.
 */

import { useEffect, useState } from "react";

type Engine = "hybrid" | "llm";

interface GeneratorPanelProps {
  onGenerate: (prompt: string, minutes: number, engine: Engine) => Promise<void>;
  loading: boolean;
  disabled?: boolean;
  /** Pre-fills the session-intent textarea (e.g. constructed from the morning brief). */
  defaultPrompt?: string;
}

const TIME_MIN = 15;
const TIME_MAX = 120;
const TIME_STEP = 5;

export function GeneratorPanel({
  onGenerate,
  loading,
  disabled = false,
  defaultPrompt = "",
}: GeneratorPanelProps) {
  const [prompt, setPrompt] = useState(defaultPrompt);
  const [minutes, setMinutes] = useState(60);
  const [engine, setEngine] = useState<Engine>("hybrid");

  // Pre-fill from the brief; updates when the suggested prompt changes (e.g. on
  // member switch). Only overwrites when there's a non-empty suggestion.
  useEffect(() => {
    if (defaultPrompt) setPrompt(defaultPrompt);
  }, [defaultPrompt]);

  const clamp = (n: number) => Math.max(TIME_MIN, Math.min(TIME_MAX, n));

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!prompt.trim() || loading || disabled) return;
    await onGenerate(prompt.trim(), minutes, engine);
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-5">
      {/* Prompt input */}
      <div>
        <div className="mb-2 flex items-center justify-between">
          <label htmlFor="gen-prompt" className="eyebrow">
            Session intent
          </label>
          {defaultPrompt && prompt === defaultPrompt && (
            <span className="text-[11px] text-ink-faint">Suggested from this morning's brief</span>
          )}
        </div>
        <textarea
          id="gen-prompt"
          rows={2}
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          placeholder="e.g. lower-body strength, HYROX conditioning, mobility & recovery…"
          disabled={loading || disabled}
          className="w-full resize-none rounded-xl border border-line bg-canvas/50 px-4 py-3 text-sm text-ink placeholder-ink-faint transition focus:border-ink focus:outline-none disabled:opacity-60"
        />
      </div>

      {/* Time window — plain number input */}
      <div>
        <label htmlFor="gen-time" className="eyebrow mb-2 block">
          Time window
        </label>
        <div className="inline-flex items-center gap-2">
          <input
            id="gen-time"
            type="number"
            min={TIME_MIN}
            max={TIME_MAX}
            step={TIME_STEP}
            value={minutes}
            onChange={(e) => setMinutes(Number(e.target.value))}
            onBlur={(e) => setMinutes(clamp(Number(e.target.value) || TIME_MIN))}
            disabled={loading || disabled}
            className="w-24 rounded-xl border border-line bg-canvas/50 px-3 py-2 text-sm text-ink focus:border-ink focus:outline-none disabled:opacity-60"
          />
          <span className="text-sm text-ink-faint">minutes</span>
        </div>
      </div>

      {/* Engine toggle */}
      <div>
        <label className="eyebrow mb-2 block">Engine</label>
        <div className="inline-flex rounded-full border border-line p-0.5">
          {([
            ["hybrid", "Hybrid", "fast"],
            ["llm", "Full LLM", "detailed"],
          ] as const).map(([id, label, hint]) => (
            <button
              key={id}
              type="button"
              onClick={() => setEngine(id)}
              disabled={loading || disabled}
              className={`rounded-full px-3.5 py-1.5 text-xs font-medium transition-colors disabled:opacity-50 ${
                engine === id ? "bg-ink text-canvas" : "text-ink-soft hover:text-ink"
              }`}
            >
              {label}
              <span className={`ml-1 ${engine === id ? "text-canvas/60" : "text-ink-faint"}`}>
                · {hint}
              </span>
            </button>
          ))}
        </div>
        <p className="mt-1.5 text-[11px] text-ink-faint">
          {engine === "hybrid"
            ? "Graph assembles the plan; the LLM writes only the rationale (~few seconds)."
            : "The LLM structures the entire plan (richer per-exercise prose, ~20s)."}
        </p>
      </div>

      {/* Submit */}
      <button
        type="submit"
        disabled={!prompt.trim() || loading || disabled}
        className="w-full rounded-full bg-ink py-3 text-sm font-semibold text-canvas transition-colors hover:bg-clay disabled:cursor-not-allowed disabled:opacity-50"
      >
        {loading ? (
          <span className="flex items-center justify-center gap-2">
            <span className="h-4 w-4 animate-spin rounded-full border-2 border-canvas/40 border-t-canvas" />
            Generating session…
          </span>
        ) : (
          "Generate session"
        )}
      </button>
    </form>
  );
}
