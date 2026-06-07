/**
 * useCanvas — React hook that subscribes to the shared canvas store.
 *
 * Returns the current ordered list of CanvasNodes and all mutation helpers.
 * Components re-render whenever the canvas changes.
 */

import { useSyncExternalStore, useCallback } from "react";
import {
  getCanvasNodes,
  subscribeCanvas,
  canvasAddNode,
  canvasRemoveNode,
  canvasUpdateNode,
  canvasMoveNode,
  canvasClear,
  type CanvasNode,
} from "../state/canvas";

interface UseCanvasResult {
  nodes: CanvasNode[];
  addNode: (node: Omit<CanvasNode, "canvasId">) => CanvasNode;
  removeNode: (canvasId: string) => void;
  updateNode: (
    canvasId: string,
    patch: Partial<Omit<CanvasNode, "canvasId" | "exerciseId">>
  ) => void;
  moveNode: (fromIdx: number, toIdx: number) => void;
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

  const moveNode = useCallback(
    (from: number, to: number) => canvasMoveNode(from, to),
    []
  );

  const clearCanvas = useCallback(() => canvasClear(), []);

  return { nodes, addNode, removeNode, updateNode, moveNode, clearCanvas };
}
