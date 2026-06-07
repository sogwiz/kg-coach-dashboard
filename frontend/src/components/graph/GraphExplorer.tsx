/**
 * GraphExplorer — interactive force-directed graph for the Movement/Clinical KG.
 *
 * Uses react-force-graph-2d for the force layout.
 *
 * Affordances:
 *   - Search + focus: type an exercise/joint → highlight neighborhood
 *   - Node-type + edge-type filters with a color legend
 *   - Click-to-explain: click exercise → side panel listing its concepts
 *   - Member-aware filtering toggle: filtered-out exercises dimmed/red,
 *     part-of chain highlighted; clicking removed exercise shows exclusion reason
 */

import { useState, useCallback, useRef, useMemo, useEffect } from "react";
import ForceGraph2D from "react-force-graph-2d";
import { useGraph } from "../../hooks/useGraph";

// ---------------------------------------------------------------------------
// Color palette
// ---------------------------------------------------------------------------

const NODE_COLORS: Record<string, string> = {
  exercise: "#6366f1",        // indigo
  muscle: "#10b981",          // emerald
  joint: "#f59e0b",           // amber
  pattern: "#8b5cf6",         // violet
  equipment: "#06b6d4",       // cyan
  injury_concept: "#ef4444",  // red
  body_region: "#f97316",     // orange
  unknown: "#94a3b8",         // slate
};

const EDGE_COLORS: Record<string, string> = {
  stresses: "#6366f1",
  targets: "#10b981",
  requires: "#06b6d4",
  "part-of": "#f59e0b",
  uses: "#8b5cf6",
  "contraindicated-for": "#ef4444",
  involves: "#f97316",
  unknown: "#94a3b8",
};

// ---------------------------------------------------------------------------
// Types for react-force-graph-2d
// ---------------------------------------------------------------------------

interface FGNode {
  id: string;
  label: string;
  type: string;
  filtered_out: boolean;
  on_filter_path: boolean;
  excluded_by?: { injury: string; joint: string; reason: string }[];
  // layout fields added by force-graph
  x?: number;
  y?: number;
  fx?: number;
  fy?: number;
}

interface FGLink {
  source: string | FGNode;
  target: string | FGNode;
  relation: string;
  on_filter_path: boolean;
  movement_types: string[];
}

// ---------------------------------------------------------------------------
// Legend
// ---------------------------------------------------------------------------

function Legend() {
  return (
    <div className="flex flex-wrap gap-x-3 gap-y-1">
      {Object.entries(NODE_COLORS).filter(([k]) => k !== "unknown").map(([type, color]) => (
        <div key={type} className="flex items-center gap-1 text-xs text-slate-600">
          <div className="w-3 h-3 rounded-full flex-shrink-0" style={{ background: color }} />
          {type.replace("_", " ")}
        </div>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

interface GraphExplorerProps {
  memberId?: string | null;
}

export function GraphExplorer({ memberId }: GraphExplorerProps) {
  const { payload, isLoading, error } = useGraph(memberId);

  const [searchQuery, setSearchQuery] = useState("");
  const [focusedId, setFocusedId] = useState<string | null>(null);
  const [selectedNode, setSelectedNode] = useState<FGNode | null>(null);
  const [showMemberFilter, setShowMemberFilter] = useState(!!memberId);
  const [activeNodeTypes, setActiveNodeTypes] = useState<Set<string>>(
    new Set(["exercise", "muscle", "joint", "pattern", "equipment", "injury_concept", "body_region"])
  );
  const [activeEdgeTypes, setActiveEdgeTypes] = useState<Set<string>>(
    new Set(["stresses", "targets", "requires", "part-of", "uses", "contraindicated-for"])
  );

  const graphRef = useRef<any>(null);

  // When member changes, reset filter toggle
  useEffect(() => {
    setShowMemberFilter(!!memberId);
    setSelectedNode(null);
    setFocusedId(null);
  }, [memberId]);

  // Build the graph data from payload
  const { nodes, links, neighborSet, edgesByNode } = useMemo(() => {
    if (!payload) return { nodes: [], links: [], neighborSet: new Map<string, Set<string>>(), edgesByNode: new Map<string, FGLink[]>() };

    const filteredNodes: FGNode[] = payload.nodes
      .filter((n) => activeNodeTypes.has(n.type))
      .map((n) => ({
        id: n.id,
        label: n.label,
        type: n.type,
        filtered_out: n.filtered_out,
        on_filter_path: n.on_filter_path,
        excluded_by: n.excluded_by ?? [],
      }));

    const nodeIdSet = new Set(filteredNodes.map((n) => n.id));

    const filteredLinks: FGLink[] = payload.edges
      .filter(
        (e) =>
          activeEdgeTypes.has(e.relation) &&
          nodeIdSet.has(e.source) &&
          nodeIdSet.has(e.target)
      )
      .map((e) => ({
        source: e.source,
        target: e.target,
        relation: e.relation,
        on_filter_path: e.on_filter_path,
        movement_types: e.movement_types,
      }));

    // Build neighbor + edge maps for click-to-explain
    const neighborSet = new Map<string, Set<string>>();
    const edgesByNode = new Map<string, FGLink[]>();

    for (const link of filteredLinks) {
      const srcId = typeof link.source === "string" ? link.source : link.source.id;
      const tgtId = typeof link.target === "string" ? link.target : link.target.id;
      if (!neighborSet.has(srcId)) neighborSet.set(srcId, new Set());
      if (!neighborSet.has(tgtId)) neighborSet.set(tgtId, new Set());
      neighborSet.get(srcId)!.add(tgtId);
      neighborSet.get(tgtId)!.add(srcId);
      if (!edgesByNode.has(srcId)) edgesByNode.set(srcId, []);
      edgesByNode.get(srcId)!.push(link);
    }

    return { nodes: filteredNodes, links: filteredLinks, neighborSet, edgesByNode };
  }, [payload, activeNodeTypes, activeEdgeTypes]);

  // Search match
  const searchMatches = useMemo(() => {
    if (!searchQuery.trim()) return new Set<string>();
    const q = searchQuery.toLowerCase();
    return new Set(
      nodes
        .filter((n) => n.label.toLowerCase().includes(q) || n.id.toLowerCase().includes(q))
        .map((n) => n.id)
    );
  }, [searchQuery, nodes]);

  // Focus on first search match
  useEffect(() => {
    if (searchMatches.size === 1) {
      const id = [...searchMatches][0];
      setFocusedId(id);
    } else if (searchMatches.size === 0) {
      setFocusedId(null);
    }
  }, [searchMatches]);

  // Node color (with filtering + focus logic)
  const getNodeColor = useCallback(
    (node: FGNode): string => {
      const isFiltered = showMemberFilter && node.filtered_out;
      if (isFiltered) return "#ef4444"; // red for filtered-out exercises

      // If we have a focus, fade non-neighbors
      if (focusedId) {
        const neighbors = neighborSet.get(focusedId) ?? new Set();
        if (node.id !== focusedId && !neighbors.has(node.id)) {
          return "#e2e8f0"; // faded
        }
      }

      // Search highlight
      if (searchQuery && !searchMatches.has(node.id)) {
        return "#e2e8f0";
      }

      // Filter path highlight
      if (showMemberFilter && node.on_filter_path) {
        return "#dc2626"; // deeper red for chain nodes
      }

      return NODE_COLORS[node.type] ?? NODE_COLORS.unknown;
    },
    [focusedId, neighborSet, searchQuery, searchMatches, showMemberFilter]
  );

  // Link color
  const getLinkColor = useCallback(
    (link: FGLink): string => {
      if (showMemberFilter && link.on_filter_path) return "#dc2626";
      if (focusedId) {
        const srcId = typeof link.source === "string" ? link.source : link.source.id;
        const tgtId = typeof link.target === "string" ? link.target : link.target.id;
        const neighbors = neighborSet.get(focusedId) ?? new Set();
        if (
          srcId !== focusedId && tgtId !== focusedId &&
          !neighbors.has(srcId) && !neighbors.has(tgtId)
        ) {
          return "#f1f5f9"; // very faded
        }
      }
      return EDGE_COLORS[link.relation] ?? EDGE_COLORS.unknown;
    },
    [focusedId, neighborSet, showMemberFilter]
  );

  const handleNodeClick = useCallback(
    (node: FGNode) => {
      if (focusedId === node.id) {
        setFocusedId(null);
        setSelectedNode(null);
      } else {
        setFocusedId(node.id);
        setSelectedNode(node);
      }
    },
    [focusedId]
  );

  // Side panel: edges from the selected node
  const selectedEdges = useMemo(() => {
    if (!selectedNode) return [];
    return (edgesByNode.get(selectedNode.id) ?? []).slice(0, 20);
  }, [selectedNode, edgesByNode]);

  const selectedNeighbors = useMemo(() => {
    if (!selectedNode || !payload) return [];
    const neighbors = neighborSet.get(selectedNode.id) ?? new Set();
    return payload.nodes.filter((n) => neighbors.has(n.id)).slice(0, 15);
  }, [selectedNode, payload, neighborSet]);

  // Toggle node type filter
  const toggleNodeType = (type: string) => {
    setActiveNodeTypes((prev) => {
      const next = new Set(prev);
      if (next.has(type)) next.delete(type);
      else next.add(type);
      return next;
    });
  };

  // Toggle edge type filter
  const toggleEdgeType = (rel: string) => {
    setActiveEdgeTypes((prev) => {
      const next = new Set(prev);
      if (next.has(rel)) next.delete(rel);
      else next.add(rel);
      return next;
    });
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64 text-slate-400 text-sm">
        Loading knowledge graph...
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-lg bg-red-50 border border-red-200 p-4 text-sm text-red-700">
        Failed to load graph: {error}
      </div>
    );
  }

  if (!payload) return null;

  const filteredOutCount = payload.filtered_exercise_ids.length;

  return (
    <div className="space-y-4">
      {/* Controls */}
      <div className="bg-white rounded-xl border border-slate-200 p-4 space-y-3">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-semibold text-slate-800">Graph Explorer</h3>
          <span className="text-xs text-slate-400">
            {nodes.length} nodes · {links.length} edges
          </span>
        </div>

        {/* Search */}
        <input
          type="text"
          placeholder="Search nodes (exercise, muscle, joint...)..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="w-full rounded-lg border border-slate-200 px-3 py-1.5 text-sm placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-indigo-500"
        />

        {/* Member filter toggle */}
        {memberId && (
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => setShowMemberFilter((v) => !v)}
              className={`relative inline-flex h-5 w-9 items-center rounded-full transition-colors ${
                showMemberFilter ? "bg-indigo-600" : "bg-slate-200"
              }`}
            >
              <span
                className={`inline-block h-3.5 w-3.5 transform rounded-full bg-white transition-transform ${
                  showMemberFilter ? "translate-x-4" : "translate-x-0.5"
                }`}
              />
            </button>
            <span className="text-xs text-slate-600">
              Show member filtering
              {showMemberFilter && filteredOutCount > 0 && (
                <span className="ml-1 text-red-600">
                  ({filteredOutCount} exercises excluded)
                </span>
              )}
            </span>
          </div>
        )}

        {/* Active injuries driving the filter — named so exclusions are attributable */}
        {memberId && showMemberFilter && (payload?.member_injuries?.length ?? 0) > 0 && (
          <div className="rounded-lg bg-red-50 border border-red-200 px-3 py-2">
            <p className="text-[11px] font-semibold uppercase tracking-wide text-red-700 mb-1">
              Filtering for {payload!.member_injuries!.length === 1 ? "injury" : "injuries"}
            </p>
            <ul className="space-y-0.5">
              {payload!.member_injuries!.map((inj) => (
                <li key={inj.joint} className="flex items-center gap-1.5 text-xs text-red-800">
                  <span className="h-1.5 w-1.5 rounded-full bg-red-500 flex-shrink-0" />
                  <span className="font-medium">{inj.label}</span>
                  {inj.healing_phase && (
                    <span className="text-red-500">· {inj.healing_phase}</span>
                  )}
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Node type filters */}
        <div className="space-y-1">
          <p className="text-xs text-slate-500 font-medium">Node types</p>
          <div className="flex flex-wrap gap-1.5">
            {Object.entries(NODE_COLORS)
              .filter(([k]) => k !== "unknown")
              .map(([type, color]) => (
                <button
                  key={type}
                  type="button"
                  onClick={() => toggleNodeType(type)}
                  className={`flex items-center gap-1 rounded-full px-2 py-0.5 text-xs border transition-opacity ${
                    activeNodeTypes.has(type)
                      ? "opacity-100 border-current"
                      : "opacity-40 border-slate-200"
                  }`}
                  style={{ color, borderColor: activeNodeTypes.has(type) ? color : undefined }}
                >
                  <span
                    className="w-2 h-2 rounded-full flex-shrink-0"
                    style={{ background: color }}
                  />
                  {type.replace("_", " ")}
                </button>
              ))}
          </div>
        </div>

        {/* Edge type filters */}
        <div className="space-y-1">
          <p className="text-xs text-slate-500 font-medium">Edge types</p>
          <div className="flex flex-wrap gap-1.5">
            {Object.entries(EDGE_COLORS)
              .filter(([k]) => k !== "unknown")
              .map(([rel, color]) => (
                <button
                  key={rel}
                  type="button"
                  onClick={() => toggleEdgeType(rel)}
                  className={`flex items-center gap-1 rounded-full px-2 py-0.5 text-xs border transition-opacity ${
                    activeEdgeTypes.has(rel)
                      ? "opacity-100 border-current"
                      : "opacity-40 border-slate-200"
                  }`}
                  style={{ color, borderColor: activeEdgeTypes.has(rel) ? color : undefined }}
                >
                  {rel}
                </button>
              ))}
          </div>
        </div>

        <Legend />
      </div>

      {/* Graph + side panel */}
      <div className="flex gap-4">
        {/* Graph canvas */}
        <div
          className="flex-1 bg-slate-50 rounded-xl border border-slate-200 overflow-hidden"
          style={{ height: 520 }}
        >
          {nodes.length > 0 ? (
            <ForceGraph2D
              ref={graphRef}
              graphData={{ nodes, links }}
              nodeId="id"
              nodeLabel="label"
              nodeColor={getNodeColor}
              linkColor={getLinkColor}
              linkDirectionalArrowLength={3}
              linkDirectionalArrowRelPos={1}
              linkCurvature={0.1}
              nodeCanvasObject={(node, ctx, globalScale) => {
                const n = node as FGNode & { x: number; y: number };
                const r = 4;
                ctx.beginPath();
                ctx.arc(n.x, n.y, r, 0, 2 * Math.PI);
                ctx.fillStyle = getNodeColor(n);
                ctx.fill();

                // Border for filter-path nodes
                if (showMemberFilter && (n.filtered_out || n.on_filter_path)) {
                  ctx.strokeStyle = "#dc2626";
                  ctx.lineWidth = 1.5;
                  ctx.stroke();
                }

                // Label for focused node
                if (n.id === focusedId || (searchMatches.size > 0 && searchMatches.has(n.id))) {
                  const fontSize = Math.max(10 / globalScale, 8);
                  ctx.font = `${fontSize}px sans-serif`;
                  ctx.fillStyle = "#1e293b";
                  ctx.textAlign = "center";
                  ctx.fillText(n.label.slice(0, 24), n.x, n.y - r - 2);
                }
              }}
              onNodeClick={(node) => handleNodeClick(node as FGNode)}
              cooldownTicks={80}
              width={selectedNode ? undefined : undefined}
            />
          ) : (
            <div className="flex items-center justify-center h-full text-slate-400 text-sm">
              No nodes match the current filters.
            </div>
          )}
        </div>

        {/* Side panel */}
        {selectedNode && (
          <div className="w-72 flex-shrink-0 bg-white rounded-xl border border-slate-200 p-4 overflow-y-auto" style={{ maxHeight: 520 }}>
            <div className="flex items-start justify-between mb-3">
              <div>
                <div
                  className="inline-block rounded-full px-2 py-0.5 text-xs font-medium text-white mb-1"
                  style={{ background: NODE_COLORS[selectedNode.type] ?? NODE_COLORS.unknown }}
                >
                  {selectedNode.type.replace("_", " ")}
                </div>
                <h4 className="text-sm font-semibold text-slate-800 break-words">
                  {selectedNode.label}
                </h4>
              </div>
              <button
                type="button"
                onClick={() => { setSelectedNode(null); setFocusedId(null); }}
                className="text-slate-400 hover:text-slate-600 text-lg leading-none ml-2"
              >
                x
              </button>
            </div>

            {/* Filtered out — name the specific injury(ies) + graph reason */}
            {showMemberFilter && selectedNode.filtered_out && (
              <div className="rounded-lg bg-red-50 border border-red-200 px-3 py-2 mb-3">
                {(selectedNode.excluded_by?.length ?? 0) > 0 ? (
                  <>
                    <p className="text-xs font-semibold text-red-700 mb-1">
                      Excluded by safety filter — injury:
                    </p>
                    <ul className="space-y-1.5">
                      {selectedNode.excluded_by!.map((ex, i) => (
                        <li key={i} className="text-xs text-red-800">
                          <span className="font-medium">{ex.injury}</span>
                          <span className="block text-red-600 mt-0.5">{ex.reason}</span>
                        </li>
                      ))}
                    </ul>
                  </>
                ) : (
                  <p className="text-xs text-red-700">
                    Excluded by safety filter (equipment, preference, or explicit
                    exclusion — not injury-related).
                  </p>
                )}
              </div>
            )}

            {showMemberFilter && selectedNode.on_filter_path && !selectedNode.filtered_out && (
              <div className="rounded-lg bg-amber-50 border border-amber-200 px-3 py-2 text-xs text-amber-700 mb-3">
                Part of the injury exclusion chain (part-of traversal path).
              </div>
            )}

            {/* Edges */}
            {selectedEdges.length > 0 && (
              <div className="space-y-2">
                <p className="text-xs font-medium text-slate-600">Edges from this node</p>
                <div className="space-y-1">
                  {selectedEdges.map((edge, i) => {
                    const tgtId = typeof edge.target === "string" ? edge.target : edge.target.id;
                    const tgtLabel =
                      payload?.nodes.find((n) => n.id === tgtId)?.label ?? tgtId;
                    return (
                      <div
                        key={i}
                        className="flex items-start gap-1.5 text-xs text-slate-600 py-1 border-b border-slate-50 last:border-0"
                      >
                        <span
                          className="rounded-full px-1.5 py-0.5 text-white text-xs flex-shrink-0"
                          style={{ background: EDGE_COLORS[edge.relation] ?? "#94a3b8" }}
                        >
                          {edge.relation}
                        </span>
                        <span className="break-words">{tgtLabel}</span>
                        {edge.movement_types.length > 0 && (
                          <span className="text-slate-400 text-xs">
                            [{edge.movement_types.join(", ")}]
                          </span>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

            {/* Neighbor summary */}
            {selectedNeighbors.length > 0 && (
              <div className="mt-3 space-y-1">
                <p className="text-xs font-medium text-slate-600">
                  Neighboring concepts ({selectedNeighbors.length})
                </p>
                <div className="flex flex-wrap gap-1">
                  {selectedNeighbors.map((n) => (
                    <span
                      key={n.id}
                      className="rounded-full px-2 py-0.5 text-xs text-white"
                      style={{ background: NODE_COLORS[n.type] ?? NODE_COLORS.unknown }}
                    >
                      {n.label.slice(0, 18)}
                    </span>
                  ))}
                </div>
              </div>
            )}

            <p className="mt-4 text-xs text-slate-400">
              ID: <code className="bg-slate-50 px-1 rounded">{selectedNode.id}</code>
            </p>
          </div>
        )}
      </div>

      {!selectedNode && (
        <p className="text-xs text-slate-400 text-center">
          Click any node to see its edges and neighboring concepts.
          {memberId && " Toggle the member filter to highlight excluded exercises."}
        </p>
      )}
    </div>
  );
}
