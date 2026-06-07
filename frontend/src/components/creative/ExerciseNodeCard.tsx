/**
 * ExerciseNodeCard — a single exercise card in the Creative Canvas.
 *
 * Displays the exercise name plus editable coach-annotation fields:
 *   stimulus, intensity, setsReps (free-text "3 x 10"), rest, notes.
 *
 * Shows a safety WARNING chip when the exercise is contraindicated for the
 * active member (does not block — just warns).
 *
 * Drag-reorder is handled by the parent via drag callbacks; the card renders
 * up/down move buttons as an accessible alternative.
 */

import { useState } from "react";
import type { CanvasNode } from "../../state/canvas";

interface ExerciseNodeCardProps {
  node: CanvasNode;
  index: number;
  total: number;
  isContraindicated: boolean;
  onChange: (patch: Partial<Omit<CanvasNode, "canvasId" | "exerciseId">>) => void;
  onRemove: () => void;
  onMoveUp: () => void;
  onMoveDown: () => void;
  /** Drag-and-drop event handlers — wired by parent */
  draggable?: boolean;
  onDragStart?: (e: React.DragEvent, index: number) => void;
  onDragOver?: (e: React.DragEvent, index: number) => void;
  onDrop?: (e: React.DragEvent, index: number) => void;
}

// ---------------------------------------------------------------------------
// Editable text field helper
// ---------------------------------------------------------------------------

interface EditableFieldProps {
  label: string;
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  multiline?: boolean;
}

function EditableField({
  label,
  value,
  onChange,
  placeholder,
  multiline,
}: EditableFieldProps) {
  return (
    <div className="flex flex-col gap-0.5">
      <label className="text-[10px] font-bold uppercase tracking-wide text-slate-400">
        {label}
      </label>
      {multiline ? (
        <textarea
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={placeholder}
          rows={2}
          className="text-xs text-slate-700 bg-slate-50 border border-slate-200 rounded px-2 py-1 resize-none focus:outline-none focus:ring-1 focus:ring-indigo-300 placeholder:text-slate-300"
        />
      ) : (
        <input
          type="text"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={placeholder}
          className="text-xs text-slate-700 bg-slate-50 border border-slate-200 rounded px-2 py-1 focus:outline-none focus:ring-1 focus:ring-indigo-300 placeholder:text-slate-300"
        />
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// ExerciseNodeCard
// ---------------------------------------------------------------------------

export function ExerciseNodeCard({
  node,
  index,
  total,
  isContraindicated,
  onChange,
  onRemove,
  onMoveUp,
  onMoveDown,
  draggable = true,
  onDragStart,
  onDragOver,
  onDrop,
}: ExerciseNodeCardProps) {
  const [expanded, setExpanded] = useState(true);

  return (
    <div className="relative">
      {/* Card */}
      <div
        draggable={draggable}
        onDragStart={onDragStart ? (e) => onDragStart(e, index) : undefined}
        onDragOver={onDragOver ? (e) => onDragOver(e, index) : undefined}
        onDrop={onDrop ? (e) => onDrop(e, index) : undefined}
        className={`rounded-xl border-2 bg-white transition-all select-none ${
          isContraindicated
            ? "border-amber-400"
            : "border-slate-200 hover:border-indigo-200"
        } ${draggable ? "cursor-grab active:cursor-grabbing" : ""}`}
      >
        {/* Card header */}
        <div className="flex items-center gap-2 px-4 py-3">
          {/* Position number */}
          <div className="flex-shrink-0 w-6 h-6 rounded-full bg-indigo-50 flex items-center justify-center">
            <span className="text-xs font-bold text-indigo-600">{index + 1}</span>
          </div>

          {/* Name */}
          <h4 className="flex-1 text-sm font-semibold text-slate-800 truncate">
            {node.name}
          </h4>

          {/* Safety warning chip */}
          {isContraindicated && (
            <span className="flex-shrink-0 text-[10px] font-bold uppercase tracking-wide px-2 py-0.5 rounded-full bg-amber-100 text-amber-700 border border-amber-300">
              Safety warning
            </span>
          )}

          {/* Collapse / expand */}
          <button
            type="button"
            onClick={() => setExpanded((v) => !v)}
            title={expanded ? "Collapse" : "Expand"}
            className="flex-shrink-0 text-slate-400 hover:text-slate-600 transition-colors text-xs px-1"
          >
            {expanded ? "▲" : "▼"}
          </button>
        </div>

        {/* Contraindication notice */}
        {isContraindicated && (
          <div className="px-4 pb-2">
            <p className="text-[10px] text-amber-700 bg-amber-50 rounded px-2 py-1 border border-amber-200">
              This exercise may be contraindicated for the active member's injury.
              Review before programming.
            </p>
          </div>
        )}

        {/* Editable fields */}
        {expanded && (
          <div className="px-4 pb-4 grid grid-cols-2 gap-3">
            <EditableField
              label="Sets x Reps"
              value={node.setsReps}
              onChange={(v) => onChange({ setsReps: v })}
              placeholder="e.g. 3 x 10"
            />
            <EditableField
              label="Rest"
              value={node.rest}
              onChange={(v) => onChange({ rest: v })}
              placeholder="e.g. 60s"
            />
            <EditableField
              label="Intensity"
              value={node.intensity}
              onChange={(v) => onChange({ intensity: v })}
              placeholder="e.g. 70% 1RM / RPE 7"
            />
            <EditableField
              label="Stimulus"
              value={node.stimulus}
              onChange={(v) => onChange({ stimulus: v })}
              placeholder="e.g. Glute activation"
            />
            <div className="col-span-2">
              <EditableField
                label="Notes"
                value={node.notes}
                onChange={(v) => onChange({ notes: v })}
                placeholder="Coaching cues, rationale…"
                multiline
              />
            </div>
          </div>
        )}

        {/* Footer actions */}
        <div className="flex items-center gap-1 px-4 py-2 border-t border-slate-100">
          <button
            type="button"
            onClick={onMoveUp}
            disabled={index === 0}
            title="Move up"
            className="text-xs text-slate-400 hover:text-slate-700 disabled:opacity-30 disabled:cursor-not-allowed px-1.5 py-0.5 rounded hover:bg-slate-100 transition-colors"
          >
            ↑
          </button>
          <button
            type="button"
            onClick={onMoveDown}
            disabled={index === total - 1}
            title="Move down"
            className="text-xs text-slate-400 hover:text-slate-700 disabled:opacity-30 disabled:cursor-not-allowed px-1.5 py-0.5 rounded hover:bg-slate-100 transition-colors"
          >
            ↓
          </button>
          <span className="flex-1" />
          <button
            type="button"
            onClick={onRemove}
            title="Remove exercise"
            className="text-xs text-red-400 hover:text-red-600 px-1.5 py-0.5 rounded hover:bg-red-50 transition-colors"
          >
            Remove
          </button>
        </div>
      </div>

      {/* Connector arrow (not on last card) */}
      {index < total - 1 && (
        <div className="flex justify-center my-2">
          <div className="flex flex-col items-center gap-0.5">
            <div className="w-px h-3 bg-indigo-200" />
            <svg
              width="10"
              height="6"
              viewBox="0 0 10 6"
              className="text-indigo-300"
              fill="currentColor"
            >
              <path d="M5 6L0 0h10L5 6z" />
            </svg>
          </div>
        </div>
      )}
    </div>
  );
}
