/**
 * CreativeCanvas — calendar-grid session builder.
 *
 * Three columns map to the session structure:
 *   Warmup / Mobility · Main · Cooldown
 *
 * Add exercises from the left picker into a chosen column. Within a column,
 * reorder with ↑/↓; move across columns with ←/→ or by dragging a card onto
 * another column. Cards carry editable coach annotations. Exercises
 * contraindicated for the active member show a safety warning (does not block).
 *
 * "Send to Canvas" from the Generator pre-populates each column from the
 * generated plan's warmup / main / cooldown sections.
 */

import { useRef, useState } from "react";
import { useCanvas } from "../../hooks/useCanvas";
import { useExercises } from "../../hooks/useExercises";
import { ExercisePicker } from "./ExercisePicker";
import { WorkoutSynthesis } from "./WorkoutSynthesis";
import { analyzeCanvas, type CanvasAnalysis, type ExerciseItem } from "../../lib/api";
import { CANVAS_SECTIONS, type CanvasNode, type CanvasSection } from "../../state/canvas";

interface Props {
  memberId: string | null;
}

const SECTION_ACCENT: Record<CanvasSection, string> = {
  warmup: "var(--color-sage)",
  main: "var(--color-clay)",
  cooldown: "var(--color-gold)",
};

export function CreativeCanvas({ memberId }: Props) {
  const { nodes, addNode, removeNode, updateNode, moveToSection, reorderInSection, clearCanvas } =
    useCanvas();

  const { exercises: allExercises } = useExercises(memberId, "");
  const contraindicatedIds = new Set(
    allExercises.filter((e) => e.contraindicated).map((e) => e.id)
  );

  const [target, setTarget] = useState<CanvasSection>("main");
  const [dragOver, setDragOver] = useState<CanvasSection | null>(null);
  const dragId = useRef<string | null>(null);

  // Synthesis (actual training outcome of the built workout)
  const [analysis, setAnalysis] = useState<CanvasAnalysis | null>(null);
  const [analyzing, setAnalyzing] = useState(false);

  const handleSynthesize = async () => {
    if (nodes.length === 0) return;
    setAnalyzing(true);
    try {
      const result = await analyzeCanvas(
        nodes.map((n) => ({
          exercise_id: n.exerciseId,
          name: n.name,
          section: n.section,
          sets_reps: n.setsReps,
          rest: n.rest,
          intensity: n.intensity,
        }))
      );
      setAnalysis(result);
    } catch {
      setAnalysis(null);
    } finally {
      setAnalyzing(false);
    }
  };

  const handleAdd = (ex: ExerciseItem) => {
    addNode({
      exerciseId: ex.id,
      name: ex.name,
      section: target,
      stimulus: "",
      intensity: "",
      setsReps: "",
      rest: "",
      notes: "",
    });
  };

  const bySection = (s: CanvasSection) => nodes.filter((n) => n.section === s);

  return (
    <div className="flex gap-5">
      {/* Left — Exercise picker */}
      <div className="w-64 flex-shrink-0">
        <div className="sticky top-4 rounded-2xl border border-line bg-surface p-4">
          <p className="eyebrow mb-3">Add exercise</p>

          {/* Target column selector */}
          <div className="mb-3">
            <p className="mb-1.5 text-[11px] text-ink-faint">Add to column</p>
            <div className="flex gap-1">
              {CANVAS_SECTIONS.map((s) => (
                <button
                  key={s.id}
                  type="button"
                  onClick={() => setTarget(s.id)}
                  className={`flex-1 rounded-lg px-2 py-1 text-[11px] font-medium transition-colors ${
                    target === s.id
                      ? "bg-ink text-canvas"
                      : "border border-line text-ink-soft hover:border-ink"
                  }`}
                >
                  {s.id === "warmup" ? "Warmup" : s.id === "main" ? "Main" : "Cooldown"}
                </button>
              ))}
            </div>
          </div>

          <ExercisePicker memberId={memberId} onAdd={handleAdd} />
        </div>
      </div>

      {/* Right — 3-column grid */}
      <div className="min-w-0 flex-1">
        <div className="mb-4 flex items-center justify-between">
          <div>
            <p className="eyebrow mb-0.5">Session Canvas</p>
            <p className="text-xs text-ink-faint">
              {nodes.length === 0
                ? "Add exercises, or use “Send to Canvas” from the Generator."
                : `${nodes.length} exercise${nodes.length === 1 ? "" : "s"} · drag between columns to reorganize`}
            </p>
          </div>
          {nodes.length > 0 && (
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={handleSynthesize}
                disabled={analyzing}
                className="flex items-center gap-1.5 rounded-full bg-ink px-4 py-1.5 text-xs font-semibold text-canvas transition-colors hover:bg-clay disabled:opacity-60"
              >
                {analyzing ? (
                  <span className="h-3 w-3 animate-spin rounded-full border-2 border-canvas/40 border-t-canvas" />
                ) : (
                  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M3 3v18h18M7 14l3-3 3 3 5-6" strokeLinecap="round" strokeLinejoin="round" />
                  </svg>
                )}
                Synthesize workout
              </button>
              <button
                type="button"
                onClick={() => {
                  if (confirm("Clear canvas? This cannot be undone.")) {
                    clearCanvas();
                    setAnalysis(null);
                  }
                }}
                className="rounded-full border border-line px-3 py-1.5 text-xs text-ink-soft transition-colors hover:border-clay hover:text-clay"
              >
                Clear
              </button>
            </div>
          )}
        </div>

        {/* Synthesis — actual training outcome of the built workout */}
        {analysis && (
          <div className="mb-5">
            <WorkoutSynthesis analysis={analysis} onClose={() => setAnalysis(null)} />
          </div>
        )}

        <div className="grid grid-cols-3 gap-4">
          {CANVAS_SECTIONS.map((sec) => {
            const items = bySection(sec.id);
            const isOver = dragOver === sec.id;
            return (
              <div
                key={sec.id}
                onDragOver={(e) => {
                  e.preventDefault();
                  setDragOver(sec.id);
                }}
                onDragLeave={() => setDragOver((d) => (d === sec.id ? null : d))}
                onDrop={(e) => {
                  e.preventDefault();
                  if (dragId.current) moveToSection(dragId.current, sec.id);
                  dragId.current = null;
                  setDragOver(null);
                }}
                className={`rounded-2xl border bg-canvas/40 transition-colors ${
                  isOver ? "border-clay bg-clay/5" : "border-line"
                }`}
              >
                {/* Column header */}
                <div
                  className="flex items-center justify-between rounded-t-2xl border-b border-line px-3 py-2.5"
                  style={{ borderTop: `3px solid ${SECTION_ACCENT[sec.id]}` }}
                >
                  <span className="text-xs font-semibold text-ink">{sec.label}</span>
                  <span className="text-[11px] text-ink-faint">{items.length}</span>
                </div>

                {/* Cards */}
                <div className="min-h-[120px] space-y-2 p-2">
                  {items.length === 0 && (
                    <p className="px-2 py-6 text-center text-[11px] text-ink-faint">
                      Drop or add exercises here
                    </p>
                  )}
                  {items.map((node, i) => (
                    <CanvasCard
                      key={node.canvasId}
                      node={node}
                      first={i === 0}
                      last={i === items.length - 1}
                      contraindicated={contraindicatedIds.has(node.exerciseId)}
                      onChange={(patch) => updateNode(node.canvasId, patch)}
                      onRemove={() => removeNode(node.canvasId)}
                      onUp={() => reorderInSection(node.canvasId, -1)}
                      onDown={() => reorderInSection(node.canvasId, 1)}
                      onSection={(s) => moveToSection(node.canvasId, s)}
                      onDragStart={() => (dragId.current = node.canvasId)}
                      onDragEnd={() => (dragId.current = null)}
                    />
                  ))}
                </div>
              </div>
            );
          })}
        </div>

        {contraindicatedIds.size > 0 &&
          nodes.some((n) => contraindicatedIds.has(n.exerciseId)) && (
            <p className="mt-3 text-xs font-medium text-amber-600">
              ⚠ {nodes.filter((n) => contraindicatedIds.has(n.exerciseId)).length} exercise(s) with
              safety warnings for the active member.
            </p>
          )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Compact card
// ---------------------------------------------------------------------------

interface CardProps {
  node: CanvasNode;
  first: boolean;
  last: boolean;
  contraindicated: boolean;
  onChange: (patch: Partial<Omit<CanvasNode, "canvasId" | "exerciseId">>) => void;
  onRemove: () => void;
  onUp: () => void;
  onDown: () => void;
  onSection: (s: CanvasSection) => void;
  onDragStart: () => void;
  onDragEnd: () => void;
}

function CanvasCard({
  node,
  first,
  last,
  contraindicated,
  onChange,
  onRemove,
  onUp,
  onDown,
  onSection,
  onDragStart,
  onDragEnd,
}: CardProps) {
  const [open, setOpen] = useState(false);
  const order: CanvasSection[] = ["warmup", "main", "cooldown"];
  const idx = order.indexOf(node.section);

  return (
    <div
      draggable
      onDragStart={onDragStart}
      onDragEnd={onDragEnd}
      className={`cursor-grab rounded-xl border bg-surface active:cursor-grabbing ${
        contraindicated ? "border-amber-400" : "border-line"
      }`}
    >
      {/* Header */}
      <div className="flex items-start gap-1.5 px-2.5 pt-2">
        <button
          type="button"
          onClick={() => setOpen((v) => !v)}
          className="min-w-0 flex-1 text-left"
        >
          <span className="block truncate text-xs font-semibold text-ink">{node.name}</span>
          {(node.setsReps || node.rest) && (
            <span className="block truncate text-[10px] text-ink-faint">
              {[node.setsReps, node.rest].filter(Boolean).join(" · ")}
            </span>
          )}
        </button>
        <button
          type="button"
          onClick={onRemove}
          aria-label="Remove"
          className="flex-shrink-0 text-ink-faint hover:text-clay"
        >
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2">
            <path d="M6 6l12 12M6 18L18 6" strokeLinecap="round" />
          </svg>
        </button>
      </div>

      {contraindicated && (
        <p className="mx-2.5 mt-1 rounded bg-amber-50 px-1.5 py-0.5 text-[9px] text-amber-700">
          ⚠ contraindicated for active member
        </p>
      )}

      {/* Editable fields */}
      {open && (
        <div className="space-y-1.5 px-2.5 pb-2 pt-2">
          <Field label="Sets × Reps" value={node.setsReps} onChange={(v) => onChange({ setsReps: v })} placeholder="3 × 10" />
          <Field label="Rest" value={node.rest} onChange={(v) => onChange({ rest: v })} placeholder="60s" />
          <Field label="Intensity" value={node.intensity} onChange={(v) => onChange({ intensity: v })} placeholder="RPE 7" />
          <Field label="Stimulus" value={node.stimulus} onChange={(v) => onChange({ stimulus: v })} placeholder="glute activation" />
          <Field label="Notes" value={node.notes} onChange={(v) => onChange({ notes: v })} placeholder="cues…" multiline />
        </div>
      )}

      {/* Footer controls */}
      <div className="flex items-center gap-0.5 border-t border-line px-2 py-1">
        <IconBtn label="Up" disabled={first} onClick={onUp}>↑</IconBtn>
        <IconBtn label="Down" disabled={last} onClick={onDown}>↓</IconBtn>
        <span className="flex-1" />
        <IconBtn label="Move left" disabled={idx === 0} onClick={() => onSection(order[idx - 1])}>←</IconBtn>
        <IconBtn label="Move right" disabled={idx === 2} onClick={() => onSection(order[idx + 1])}>→</IconBtn>
      </div>
    </div>
  );
}

function IconBtn({
  children,
  onClick,
  disabled,
  label,
}: {
  children: React.ReactNode;
  onClick: () => void;
  disabled?: boolean;
  label: string;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      aria-label={label}
      title={label}
      className="rounded px-1.5 py-0.5 text-xs text-ink-faint transition-colors hover:bg-sand hover:text-ink disabled:opacity-30"
    >
      {children}
    </button>
  );
}

function Field({
  label,
  value,
  onChange,
  placeholder,
  multiline,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  multiline?: boolean;
}) {
  return (
    <label className="block">
      <span className="mb-0.5 block text-[9px] font-semibold uppercase tracking-wide text-ink-faint">
        {label}
      </span>
      {multiline ? (
        <textarea
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={placeholder}
          rows={2}
          className="w-full resize-none rounded border border-line bg-canvas/50 px-1.5 py-1 text-[11px] text-ink placeholder-ink-faint focus:border-ink focus:outline-none"
        />
      ) : (
        <input
          type="text"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={placeholder}
          className="w-full rounded border border-line bg-canvas/50 px-1.5 py-1 text-[11px] text-ink placeholder-ink-faint focus:border-ink focus:outline-none"
        />
      )}
    </label>
  );
}
