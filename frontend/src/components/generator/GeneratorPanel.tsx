/**
 * GeneratorPanel — free-text prompt input + time-window slider + generate button.
 *
 * Calls POST /api/generate with {prompt, time_window_minutes, member_id}
 * via the useGenerator hook passed down from the parent.
 */

import { useState } from "react";

interface GeneratorPanelProps {
  onGenerate: (prompt: string, minutes: number) => Promise<void>;
  loading: boolean;
  disabled?: boolean;
}

const TIME_MARKS = [20, 30, 45, 60, 75, 90];

export function GeneratorPanel({
  onGenerate,
  loading,
  disabled = false,
}: GeneratorPanelProps) {
  const [prompt, setPrompt] = useState("");
  const [minutes, setMinutes] = useState(60);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!prompt.trim() || loading || disabled) return;
    await onGenerate(prompt.trim(), minutes);
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      {/* Prompt input */}
      <div>
        <label
          htmlFor="gen-prompt"
          className="block text-xs font-semibold text-slate-600 mb-1.5"
        >
          Session intent
        </label>
        <textarea
          id="gen-prompt"
          rows={2}
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          placeholder="e.g. lower body strength, full body conditioning, mobility focus..."
          disabled={loading || disabled}
          className="w-full resize-none rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-800 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-indigo-400 disabled:opacity-60 transition"
        />
      </div>

      {/* Time window slider */}
      <div>
        <div className="flex items-center justify-between mb-1.5">
          <label
            htmlFor="gen-time"
            className="text-xs font-semibold text-slate-600"
          >
            Time window
          </label>
          <span className="text-xs font-medium text-indigo-600">
            {minutes} min
          </span>
        </div>
        <input
          id="gen-time"
          type="range"
          min={10}
          max={180}
          step={5}
          value={minutes}
          onChange={(e) => setMinutes(Number(e.target.value))}
          disabled={loading || disabled}
          className="w-full accent-indigo-600 disabled:opacity-60"
        />
        {/* Quick-pick marks */}
        <div className="flex justify-between mt-1">
          {TIME_MARKS.map((m) => (
            <button
              key={m}
              type="button"
              onClick={() => setMinutes(m)}
              disabled={loading || disabled}
              className={`text-xs px-1.5 py-0.5 rounded transition ${
                minutes === m
                  ? "bg-indigo-100 text-indigo-700 font-semibold"
                  : "text-slate-400 hover:text-slate-600"
              } disabled:opacity-50`}
            >
              {m}m
            </button>
          ))}
        </div>
      </div>

      {/* Submit */}
      <button
        type="submit"
        disabled={!prompt.trim() || loading || disabled}
        className="w-full rounded-lg bg-indigo-600 py-2.5 text-sm font-semibold text-white hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
      >
        {loading ? (
          <span className="flex items-center justify-center gap-2">
            <span className="h-4 w-4 border-2 border-white/40 border-t-white rounded-full animate-spin" />
            Generating 3 variants...
          </span>
        ) : (
          "Generate workout"
        )}
      </button>
    </form>
  );
}
