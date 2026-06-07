/**
 * useCanvas — React hook that subscribes to the shared canvas store.
 *
 * Returns the current nodes (across all 3 sections) and section-aware mutation
 * helpers. Components re-render whenever the canvas changes.
 */

import { useSyncExternalStore, useCallback } from "react";
import {
  getCanvasNodes,
  subscribeCanvas,
  canvasAddNode,
  canvasRemoveNode,
  canvasUpdateNode,
  canvasMoveToSection,
  canvasReorderInSection,
  canvasClear,
  type CanvasNode,
  type CanvasSection,
} from "../state/canvas";

interface UseCanvasResult {
  nodes: CanvasNode[];
  addNode: (node: Omit<CanvasNode, "canvasId">) => CanvasNode;
  removeNode: (canvasId: string) => void;
  updateNode: (
    canvasId: string,
    patch: Partial<Omit<CanvasNode, "canvasId" | "exerciseId">>
  ) => void;
  moveToSection: (canvasId: string, section: CanvasSection) => void;
  reorderInSection: (canvasId: string, dir: -1 | 1) => void;
  clearCanvas: () => void;
}

export function useCanvas(): UseCanvasResult {
  const nodes = useSyncExternalStore(subscribeCanvas, getCanvasNodes);

  const addNode = useCallback(
    (node: Omit<CanvasNode, "canvasId">) => canvasAddNode(node),
    []
  );
  const removeNode = useCallback((id: string) => canvasRemoveNode(id), []);
  const updateNode = useCallback(
    (
      id: string,
      patch: Partial<Omit<CanvasNode, "canvasId" | "exerciseId">>
    ) => canvasUpdateNode(id, patch),
    []
  );
  const moveToSection = useCallback(
    (id: string, section: CanvasSection) => canvasMoveToSection(id, section),
    []
  );
  const reorderInSection = useCallback(
    (id: string, dir: -1 | 1) => canvasReorderInSection(id, dir),
    []
  );
  const clearCanvas = useCallback(() => canvasClear(), []);

  return {
    nodes,
    addNode,
    removeNode,
    updateNode,
    moveToSection,
    reorderInSection,
    clearCanvas,
  };
}
