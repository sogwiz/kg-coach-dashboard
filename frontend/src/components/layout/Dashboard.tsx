/**
 * Dashboard — main layout with sidebar + main content area.
 *
 * Structure:
 *   - Sidebar: coach profile / logout, member switcher
 *   - Main: tabs for member overview (Phase 8), generator (Phase 9), copilot (Phase 10)
 *
 * The generator tab is keyed off the active member_id via useGenerator.
 */

import { useState, useEffect } from "react";
import { useAuth } from "../../state/auth";
import { useMembers } from "../../hooks/useMembers";
import { useActiveMember } from "../../state/activeMember";
import { useInjury } from "../../hooks/useInjury";
import { useGenerator } from "../../hooks/useGenerator";
import { fetchMember, type MemberContext } from "../../lib/api";
import { MemberSwitcher } from "../member/MemberSwitcher";
import { MemberHeader } from "../member/MemberHeader";
import { MorningBrief } from "../member/MorningBrief";
import { InjuryStatusCard } from "../injury/InjuryStatusCard";
import { InjuryTimeline } from "../injury/InjuryTimeline";
import { CheckInModal } from "../injury/CheckInModal";
import { GeneratorPanel } from "../generator/GeneratorPanel";
import { VariantChooser } from "../generator/VariantChooser";
import { InjuryWarning } from "../generator/InjuryWarning";
import { ProvenanceTrace } from "../generator/ProvenanceTrace";
import { DecisionTrace } from "../generator/DecisionTrace";
import { CopilotPanel } from "../copilot/CopilotPanel";
import { GraphExplorer } from "../graph/GraphExplorer";

type Tab = "overview" | "generator" | "copilot" | "graph";

export function Dashboard() {
  const { coach, logout } = useAuth();
  const { activeMember } = useActiveMember();
  const { isLoading: membersLoading, error: membersError } = useMembers();

  const [activeTab, setActiveTab] = useState<Tab>("overview");
  const [memberCtx, setMemberCtx] = useState<MemberContext | null>(null);
  const [checkInOpen, setCheckInOpen] = useState(false);
  const [isSelecting, setIsSelecting] = useState(false);

  // Load full member context when active member changes
  useEffect(() => {
    if (!activeMember) return;
    let cancelled = false;
    fetchMember(activeMember.member_id)
      .then((ctx) => {
        if (!cancelled) setMemberCtx(ctx);
      })
      .catch(() => {
        if (!cancelled) setMemberCtx(null);
      });
    return () => {
      cancelled = true;
    };
  }, [activeMember]);

  // Pick the first injury for the active member
  const firstInjury = memberCtx?.injuries?.[0] ?? null;
  const injuryId = firstInjury?.id ?? null;

  const {
    injury,
    currentState,
    history: injuryHistory,
    checkIn,
    needsCheckIn,
  } = useInjury(activeMember?.member_id ?? null, injuryId);

  // Generator state (keyed by active member)
  const {
    generate,
    selectVariant,
    variants,
    selectedVariant,
    traceSummary,
    decisionTrace,
    injuryStateUsed,
    loading: genLoading,
    error: genError,
    llmUnconfigured,
    reset: resetGenerator,
  } = useGenerator(activeMember?.member_id ?? null);

  // Reset generator output when switching members
  useEffect(() => {
    resetGenerator();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeMember?.member_id]);

  const handleSelectVariant = async (variantId: string) => {
    setIsSelecting(true);
    try {
      await selectVariant(variantId);
    } finally {
      setIsSelecting(false);
    }
  };

  // Most recent adherence %
  const adherenceWeeks = memberCtx?.adherence?.weekly_completion_pct ?? [];
  const lastAdherencePct =
    adherenceWeeks.length > 0
      ? adherenceWeeks[adherenceWeeks.length - 1].pct
      : null;

  const TABS: { id: Tab; label: string }[] = [
    { id: "overview", label: "Overview" },
    { id: "generator", label: "Workout Generator" },
    { id: "copilot", label: "AI Copilot" },
    { id: "graph", label: "Graph Explorer" },
  ];

  return (
    <div className="min-h-screen bg-slate-50 flex">
      {/* ---------------------------------------------------------------- */}
      {/* Sidebar                                                           */}
      {/* ---------------------------------------------------------------- */}
      <aside className="w-64 flex-shrink-0 bg-white border-r border-slate-200 flex flex-col">
        {/* Brand */}
        <div className="px-4 py-4 border-b border-slate-100">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-indigo-600 flex items-center justify-center flex-shrink-0">
              <span className="text-white font-bold text-sm">KG</span>
            </div>
            <div>
              <p className="text-sm font-semibold text-slate-900">KG Coach</p>
              <p className="text-xs text-slate-400">Dashboard</p>
            </div>
          </div>
        </div>

        {/* Member switcher */}
        <nav className="flex-1 overflow-y-auto px-3 py-4">
          {membersLoading ? (
            <p className="text-xs text-slate-400 px-3">Loading members...</p>
          ) : membersError ? (
            <p className="text-xs text-red-500 px-3">{membersError}</p>
          ) : (
            <MemberSwitcher />
          )}
        </nav>

        {/* Coach profile + logout */}
        {coach && (
          <div className="px-3 py-3 border-t border-slate-100">
            <div className="flex items-center gap-2 px-2 py-2">
              <div className="w-7 h-7 rounded-full bg-indigo-100 flex items-center justify-center flex-shrink-0">
                <span className="text-indigo-700 font-semibold text-xs">
                  {coach.avatar_initials}
                </span>
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-xs font-medium text-slate-800 truncate">
                  {coach.name}
                </p>
                <p className="text-xs text-slate-400 truncate">{coach.email}</p>
              </div>
            </div>
            <button
              onClick={logout}
              className="mt-1 w-full text-xs text-slate-500 hover:text-slate-800 text-left px-2 py-1 rounded hover:bg-slate-100 transition-colors"
            >
              Sign out
            </button>
          </div>
        )}
      </aside>

      {/* ---------------------------------------------------------------- */}
      {/* Main content                                                      */}
      {/* ---------------------------------------------------------------- */}
      <main className="flex-1 overflow-y-auto">
        {!activeMember ? (
          <div className="flex items-center justify-center h-full min-h-64">
            <p className="text-slate-400 text-sm">Select a member to begin.</p>
          </div>
        ) : (
          <div className="max-w-4xl mx-auto px-6 py-6 space-y-6">
            {/* Member header */}
            <MemberHeader
              member={activeMember}
              adherencePct={lastAdherencePct}
            />

            {/* Tab navigation */}
            <div className="flex gap-1 border-b border-slate-200">
              {TABS.map((tab) => (
                <button
                  key={tab.id}
                  type="button"
                  onClick={() => setActiveTab(tab.id)}
                  className={`px-4 py-2.5 text-sm font-medium rounded-t-lg border-b-2 transition-colors ${
                    activeTab === tab.id
                      ? "border-indigo-600 text-indigo-600 bg-white"
                      : "border-transparent text-slate-500 hover:text-slate-700 hover:border-slate-300"
                  }`}
                >
                  {tab.label}
                </button>
              ))}
            </div>

            {/* ---------------------------------------------------------- */}
            {/* Overview tab                                                */}
            {/* ---------------------------------------------------------- */}
            {activeTab === "overview" && (
              <div className="space-y-6">
                {/* Morning brief */}
                {memberCtx && (
                  <MorningBrief
                    tasks={memberCtx.coach_brief.morning_tasks}
                    generatedFor={memberCtx.coach_brief.generated_for}
                  />
                )}

                {/* Injury section */}
                {injury ? (
                  <div className="space-y-4">
                    <h3 className="text-sm font-semibold text-slate-700">
                      Injury Status
                    </h3>

                    <InjuryStatusCard
                      injury={injury}
                      currentState={currentState}
                      needsCheckIn={needsCheckIn}
                      onCheckIn={() => setCheckInOpen(true)}
                    />

                    <InjuryTimeline history={injuryHistory} />
                  </div>
                ) : firstInjury ? (
                  <div className="bg-white rounded-xl border border-slate-200 p-4">
                    <p className="text-sm text-slate-400">Loading injury data...</p>
                  </div>
                ) : null}

              </div>
            )}

            {/* ---------------------------------------------------------- */}
            {/* Generator tab                                               */}
            {/* ---------------------------------------------------------- */}
            {activeTab === "generator" && (
              <div className="space-y-6">
                {/* Generator input card */}
                <div className="bg-white rounded-xl border border-slate-200 p-6 space-y-4">
                  <div>
                    <h3 className="text-sm font-semibold text-slate-800">
                      Generate workout
                    </h3>
                    <p className="text-xs text-slate-400 mt-0.5">
                      Describe the session intent. The system applies the safety
                      filter once and returns 3 labeled variants.
                    </p>
                  </div>

                  {/* Injury warning (stale check-in) */}
                  {injury && needsCheckIn && (
                    <InjuryWarning
                      lastCheckIn={currentState}
                      staleCheckIn={needsCheckIn}
                      onCheckIn={() => setCheckInOpen(true)}
                    />
                  )}

                  {/* LLM unconfigured error */}
                  {llmUnconfigured && (
                    <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
                      <strong>LLM not configured</strong> — Set{" "}
                      <code className="text-xs bg-red-100 px-1 py-0.5 rounded">
                        ANTHROPIC_API_KEY
                      </code>{" "}
                      and restart the server. The deterministic safety filter
                      and decision trace still work without it.
                    </div>
                  )}

                  {/* General error */}
                  {genError && !llmUnconfigured && (
                    <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
                      {genError}
                    </div>
                  )}

                  <GeneratorPanel
                    onGenerate={generate}
                    loading={genLoading}
                    disabled={false}
                  />
                </div>

                {/* Variant chooser — only shown when variants are available */}
                {variants.length > 0 && (
                  <div className="space-y-4">
                    <h3 className="text-sm font-semibold text-slate-700">
                      Choose a variant
                    </h3>

                    {/* Stale check-in warning at results level too */}
                    {(traceSummary?.stale_check_in ||
                      injuryStateUsed !== null &&
                        variants[0]?.provenance?.stale_check_in) && (
                      <InjuryWarning
                        lastCheckIn={injuryStateUsed}
                        staleCheckIn={true}
                        onCheckIn={() => setCheckInOpen(true)}
                      />
                    )}

                    <VariantChooser
                      variants={variants}
                      selectedVariant={selectedVariant}
                      isSelecting={isSelecting}
                      onSelect={handleSelectVariant}
                    />

                    {/* Safety filter provenance */}
                    {traceSummary && (
                      <ProvenanceTrace
                        traceSummary={traceSummary}
                        healingPhase={variants[0]?.provenance?.healing_phase}
                        injuryRegion={injury?.region}
                      />
                    )}

                    {/* Decision trace */}
                    {decisionTrace.length > 0 && (
                      <DecisionTrace steps={decisionTrace} />
                    )}
                  </div>
                )}
              </div>
            )}

            {/* ---------------------------------------------------------- */}
            {/* Copilot tab                                                 */}
            {/* ---------------------------------------------------------- */}
            {activeTab === "copilot" && (
              <CopilotPanel
                memberId={activeMember?.member_id ?? null}
                memberCtx={memberCtx}
                injuryHistory={injuryHistory}
                injuryLabel={injury?.region ? `${injury.region} injury` : undefined}
              />
            )}

            {/* ---------------------------------------------------------- */}
            {/* Graph Explorer tab                                          */}
            {/* ---------------------------------------------------------- */}
            {activeTab === "graph" && (
              <GraphExplorer memberId={activeMember?.member_id ?? null} />
            )}
          </div>
        )}
      </main>

      {/* Check-in modal */}
      {checkInOpen && injury && (
        <CheckInModal
          injuryRegion={injury.region}
          onSubmit={checkIn}
          onClose={() => setCheckInOpen(false)}
        />
      )}
    </div>
  );
}
