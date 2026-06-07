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

/** The three session columns of the calendar-grid canvas. */
export type CanvasSection = "warmup" | "main" | "cooldown";

export const CANVAS_SECTIONS: { id: CanvasSection; label: string }[] = [
  { id: "warmup", label: "Warmup / Mobility" },
  { id: "main", label: "Main" },
  { id: "cooldown", label: "Cooldown" },
];

export interface CanvasNode {
  /** Unique id within the canvas (not the exercise id — allows duplicates) */
  canvasId: string;
  /** Catalog exercise id */
  exerciseId: string;
  name: string;
  /** Which column the exercise lives in */
  section: CanvasSection;
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

/** Move a node into a section, appended after the last node of that section. */
export function canvasMoveToSection(canvasId: string, section: CanvasSection): void {
  const node = _nodes.find((n) => n.canvasId === canvasId);
  if (!node || node.section === section) return;
  const updated: CanvasNode = { ...node, section };
  const rest = _nodes.filter((n) => n.canvasId !== canvasId);
  // Insert after the last node already in the target section
  let lastIdx = -1;
  rest.forEach((n, i) => {
    if (n.section === section) lastIdx = i;
  });
  rest.splice(lastIdx + 1, 0, updated);
  _nodes = rest;
  notify();
}

/** Reorder a node up/down within its OWN section (dir: -1 up, +1 down). */
export function canvasReorderInSection(canvasId: string, dir: -1 | 1): void {
  const node = _nodes.find((n) => n.canvasId === canvasId);
  if (!node) return;
  // Indices of same-section nodes, in flat order
  const sameSection = _nodes
    .map((n, i) => ({ n, i }))
    .filter((x) => x.n.section === node.section);
  const pos = sameSection.findIndex((x) => x.n.canvasId === canvasId);
  const swapWith = sameSection[pos + dir];
  if (!swapWith) return;
  const arr = [..._nodes];
  const a = sameSection[pos].i;
  const b = swapWith.i;
  [arr[a], arr[b]] = [arr[b], arr[a]];
  _nodes = arr;
  notify();
}

export function canvasClear(): void {
  _nodes = [];
  notify();
}

/**
 * Pre-populate the canvas from a generated plan, mapping each section to its
 * column. Replaces current canvas contents.
 */
export function pushToCanvas(plan: {
  warmup: PlannedExercise[];
  main: PlannedExercise[];
  cooldown: PlannedExercise[];
}): void {
  const fromSection = (exs: PlannedExercise[], section: CanvasSection): CanvasNode[] =>
    [...exs]
      .sort((a, b) => a.order - b.order)
      .map((ex) => ({
        canvasId: newCanvasId(),
        exerciseId: ex.exercise_id,
        name: ex.name,
        section,
        stimulus: ex.rationale ?? "",
        intensity: "",
        setsReps: ex.reps != null ? `${ex.sets} x ${ex.reps}` : `${ex.sets} sets`,
        rest: ex.rest_seconds > 0 ? `${ex.rest_seconds}s` : "",
        notes: ex.sequencing_rationale ?? "",
      }));

  _nodes = [
    ...fromSection(plan.warmup, "warmup"),
    ...fromSection(plan.main, "main"),
    ...fromSection(plan.cooldown, "cooldown"),
  ];
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
