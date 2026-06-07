/**
 * CreativeCanvas — n8n-style ordered exercise session builder.
 *
 * Layout:
 *   - Left panel: ExercisePicker (browse + search /api/exercises)
 *   - Right panel: ordered drag-reorderable list of ExerciseNodeCards with
 *     connectors between them (left→right flow read top-to-bottom)
 *
 * Features:
 *   - Add exercises from the catalog (incl. Wall Ball Shot, Ball Slam)
 *   - Drag-and-drop reordering (+ up/down buttons for accessibility)
 *   - Per-exercise editable fields: stimulus, intensity, sets×reps, rest, notes
 *   - Safety-aware: exercises contraindicated for the active member show a
 *     warning chip (does not block — creative canvas is coach's sandbox)
 *   - "Send to Canvas" from Generator pre-populates via shared canvas state
 *   - Clear button to reset the canvas
 *
 * State lives in src/state/canvas.ts (in-memory, no DB write-back).
 */

import { useState, useRef } from "react";
import { useCanvas } from "../../hooks/useCanvas";
import { useExercises } from "../../hooks/useExercises";
import { ExerciseNodeCard } from "./ExerciseNodeCard";
import { ExercisePicker } from "./ExercisePicker";
import type { ExerciseItem } from "../../lib/api";
import type { CanvasNode } from "../../state/canvas";

interface CreativeCanvasProps {
  memberId: string | null;
}

export function CreativeCanvas({ memberId }: CreativeCanvasProps) {
  const { nodes, addNode, removeNode, updateNode, moveNode, clearCanvas } =
    useCanvas();

  // Track which exercise ids are contraindicated for member-aware warnings.
  // We fetch all exercises (no search) with member_id to get the full
  // contraindication map, then look up each canvas node.
  const { exercises: allExercises } = useExercises(memberId, "");
  const contraindicatedIds = new Set(
    allExercises.filter((e) => e.contraindicated).map((e) => e.id)
  );

  // Drag state refs (avoid re-renders during drag)
  const dragIndexRef = useRef<number | null>(null);
  const [dragOver, setDragOver] = useState<number | null>(null);

  const handleDragStart = (_: React.DragEvent, index: number) => {
    dragIndexRef.current = index;
  };

  const handleDragOver = (e: React.DragEvent, index: number) => {
    e.preventDefault();
    setDragOver(index);
  };

  const handleDrop = (e: React.DragEvent, toIndex: number) => {
    e.preventDefault();
    if (dragIndexRef.current !== null && dragIndexRef.current !== toIndex) {
      moveNode(dragIndexRef.current, toIndex);
    }
    dragIndexRef.current = null;
    setDragOver(null);
  };

  const handleDragEnd = () => {
    dragIndexRef.current = null;
    setDragOver(null);
  };

  const handleAddExercise = (ex: ExerciseItem) => {
    addNode({
      exerciseId: ex.id,
      name: ex.name,
      stimulus: "",
      intensity: "",
      setsReps: "",
      rest: "",
      notes: "",
    });
  };

  const handleNodeChange = (
    canvasId: string,
    patch: Partial<Omit<CanvasNode, "canvasId" | "exerciseId">>
  ) => {
    updateNode(canvasId, patch);
  };

  return (
    <div className="flex gap-6 min-h-[600px]">
      {/* ------------------------------------------------------------------ */}
      {/* Left panel — Exercise Picker                                        */}
      {/* ------------------------------------------------------------------ */}
      <div className="w-72 flex-shrink-0">
        <div className="bg-white rounded-xl border border-slate-200 p-4 sticky top-4">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-semibold text-slate-800">
              Add Exercise
            </h3>
            {memberId && (
              <span className="text-[10px] text-slate-400">Member-aware</span>
            )}
          </div>
          <ExercisePicker memberId={memberId} onAdd={handleAddExercise} />
        </div>
      </div>

      {/* ------------------------------------------------------------------ */}
      {/* Right panel — Canvas                                                */}
      {/* ------------------------------------------------------------------ */}
      <div className="flex-1 min-w-0">
        {/* Canvas header */}
        <div className="flex items-center justify-between mb-4">
          <div>
            <h3 className="text-sm font-semibold text-slate-800">
              Session Canvas
            </h3>
            <p className="text-xs text-slate-400 mt-0.5">
              {nodes.length === 0
                ? 'Add exercises from the left panel, or use "Send to Canvas" from the Generator.'
                : `${nodes.length} exercise${nodes.length !== 1 ? "s" : ""} — drag to reorder`}
            </p>
          </div>

          {nodes.length > 0 && (
            <button
              type="button"
              onClick={() => {
                if (confirm("Clear canvas? This cannot be undone.")) {
                  clearCanvas();
                }
              }}
              className="text-xs text-red-500 hover:text-red-700 px-2.5 py-1.5 rounded-lg border border-red-200 hover:bg-red-50 transition-colors"
            >
              Clear canvas
            </button>
          )}
        </div>

        {/* Empty state */}
        {nodes.length === 0 && (
          <div className="flex flex-col items-center justify-center min-h-64 rounded-xl border-2 border-dashed border-slate-200 bg-slate-50 text-center px-8 py-12">
            <div className="text-3xl mb-3 select-none">🏋️</div>
            <p className="text-sm font-medium text-slate-500">
              Canvas is empty
            </p>
            <p className="text-xs text-slate-400 mt-1 max-w-xs">
              Search for exercises on the left and click "+ Add", or generate a
              workout plan and click "Send to Canvas".
            </p>
          </div>
        )}

        {/* Node list */}
        {nodes.length > 0 && (
          <div
            onDragEnd={handleDragEnd}
            className="space-y-0"
          >
            {nodes.map((node, idx) => (
              <div
                key={node.canvasId}
                className={`transition-opacity ${
                  dragOver === idx && dragIndexRef.current !== idx
                    ? "opacity-60"
                    : "opacity-100"
                }`}
              >
                <ExerciseNodeCard
                  node={node}
                  index={idx}
                  total={nodes.length}
                  isContraindicated={contraindicatedIds.has(node.exerciseId)}
                  onChange={(patch) => handleNodeChange(node.canvasId, patch)}
                  onRemove={() => removeNode(node.canvasId)}
                  onMoveUp={() => moveNode(idx, idx - 1)}
                  onMoveDown={() => moveNode(idx, idx + 1)}
                  draggable
                  onDragStart={handleDragStart}
                  onDragOver={handleDragOver}
                  onDrop={handleDrop}
                />
              </div>
            ))}
          </div>
        )}

        {/* Footer stats when canvas has exercises */}
        {nodes.length > 0 && (
          <div className="mt-4 flex items-center gap-4 text-xs text-slate-400 border-t border-slate-100 pt-3">
            <span>
              {nodes.length} exercise{nodes.length !== 1 ? "s" : ""}
            </span>
            {contraindicatedIds.size > 0 &&
              nodes.some((n) => contraindicatedIds.has(n.exerciseId)) && (
                <span className="text-amber-600 font-medium">
                  ⚠{" "}
                  {
                    nodes.filter((n) => contraindicatedIds.has(n.exerciseId))
                      .length
                  }{" "}
                  with safety warnings
                </span>
              )}
          </div>
        )}
      </div>
    </div>
  );
}
