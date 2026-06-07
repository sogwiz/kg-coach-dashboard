/**
 * canvas.ts — shared in-memory canvas state for the Creative Canvas.
 *
 * The Generator tab can call pushToCanvas(exercises) to pre-populate the
 * canvas with a generated variant's exercises. The Creative tab reads this
 * via useCanvas().
 *
 * This is plain module-level state (not React context) so it can be written
 * from any component without prop-drilling. React subscribers use the
 * useCanvas hook which registers via a simple listener pattern.
 */

import type { PlannedExercise } from "../lib/api";

// ---------------------------------------------------------------------------
// Canvas node — one exercise on the canvas
// ---------------------------------------------------------------------------

export interface CanvasNode {
  /** Unique id within the canvas (not the exercise id — allows duplicates) */
  canvasId: string;
  /** Catalog exercise id */
  exerciseId: string;
  name: string;
  /** Editable coach annotations */
  stimulus: string;
  intensity: string;
  setsReps: string; // free-text, e.g. "3 x 10" or "4 sets @ 60% 1RM"
  rest: string;
  notes: string;
}

// ---------------------------------------------------------------------------
// Internal store
// ---------------------------------------------------------------------------

let _nodes: CanvasNode[] = [];
let _listeners: Array<() => void> = [];

let _nextId = 1;

function newCanvasId(): string {
  return `cn-${_nextId++}`;
}

function notify() {
  for (const fn of _listeners) fn();
}

// ---------------------------------------------------------------------------
// Mutations — called from hooks / components
// ---------------------------------------------------------------------------

export function canvasAddNode(node: Omit<CanvasNode, "canvasId">): CanvasNode {
  const n: CanvasNode = { ...node, canvasId: newCanvasId() };
  _nodes = [..._nodes, n];
  notify();
  return n;
}

export function canvasRemoveNode(canvasId: string): void {
  _nodes = _nodes.filter((n) => n.canvasId !== canvasId);
  notify();
}

export function canvasUpdateNode(
  canvasId: string,
  patch: Partial<Omit<CanvasNode, "canvasId" | "exerciseId">>
): void {
  _nodes = _nodes.map((n) =>
    n.canvasId === canvasId ? { ...n, ...patch } : n
  );
  notify();
}

export function canvasMoveNode(fromIdx: number, toIdx: number): void {
  if (fromIdx === toIdx) return;
  const arr = [..._nodes];
  const [item] = arr.splice(fromIdx, 1);
  arr.splice(toIdx, 0, item);
  _nodes = arr;
  notify();
}

export function canvasClear(): void {
  _nodes = [];
  notify();
}

/**
 * Pre-populate the canvas from a generated variant's exercises.
 * Replaces current canvas contents.
 */
export function pushToCanvas(exercises: PlannedExercise[]): void {
  _nodes = exercises.map((ex) => ({
    canvasId: newCanvasId(),
    exerciseId: ex.exercise_id,
    name: ex.name,
    stimulus: ex.rationale ?? "",
    intensity: "",
    setsReps: ex.reps != null ? `${ex.sets} x ${ex.reps}` : `${ex.sets} sets`,
    rest: ex.rest_seconds > 0 ? `${ex.rest_seconds}s` : "",
    notes: ex.sequencing_rationale ?? "",
  }));
  notify();
}

// ---------------------------------------------------------------------------
// Subscription — for useCanvas hook
// ---------------------------------------------------------------------------

export function getCanvasNodes(): CanvasNode[] {
  return _nodes;
}

export function subscribeCanvas(fn: () => void): () => void {
  _listeners = [..._listeners, fn];
  return () => {
    _listeners = _listeners.filter((l) => l !== fn);
  };
}
