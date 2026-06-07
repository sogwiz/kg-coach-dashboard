/**
 * Dashboard — the studio shell.
 *
 * Layout:
 *   - Left rail: brand, member switcher, coach profile / logout
 *   - Main: a sticky glass command bar (member + section nav) over the content.
 *     The Overview leads with a cinematic scroll-over-image hero; the content
 *     sheet rises and covers the image as the coach scrolls.
 *
 * All generator / copilot / graph / creative wiring is preserved from prior
 * phases — only the presentation layer changed.
 */

import { useState, useEffect, useCallback } from "react";
import { useAuth } from "../../state/auth";
import { useMembers } from "../../hooks/useMembers";
import { useActiveMember } from "../../state/activeMember";
import { useInjury } from "../../hooks/useInjury";
import { useGenerator } from "../../hooks/useGenerator";
import { fetchMember, type MemberContext } from "../../lib/api";
import { MemberSwitcher } from "../member/MemberSwitcher";
import { MemberHeaderCard } from "../member/MemberHeaderCard";
import { MorningBrief } from "../member/MorningBrief";
import { InjuryStatusCard } from "../injury/InjuryStatusCard";
import { InjuryTimeline } from "../injury/InjuryTimeline";
import { CheckInModal } from "../injury/CheckInModal";
import { GeneratorPanel } from "../generator/GeneratorPanel";
import { VariantChooser } from "../generator/VariantChooser";
import { InjuryWarning } from "../generator/InjuryWarning";
import { ProvenanceTrace } from "../generator/ProvenanceTrace";
import { DecisionTrace } from "../generator/DecisionTrace";
import { GraphExplorer } from "../graph/GraphExplorer";
import { CreativeCanvas } from "../creative/CreativeCanvas";
import { AnalyticsPanel } from "../member/AnalyticsPanel";
import { CopilotDock } from "../copilot/CopilotDock";
import { ClientInbox } from "../copilot/ClientInbox";
import { useCopilotDock } from "../../state/copilot";

type Tab = "overview" | "generator" | "analytics" | "graph" | "creative";

// Short labels — used for the tab nav AND the Copilot's tab-awareness context.
const TAB_LABEL: Record<Tab, string> = {
  overview: "Overview",
  generator: "Generate",
  analytics: "Analytics",
  graph: "Insights",
  creative: "Studio",
};

/**
 * Construct a session-intent prompt from the morning brief: the workout
 * recommendation (program_note) plus any "avoid …" constraint from the check-in.
 * Returns "" when the brief has no actionable recommendation.
 */
function buildIntentFromBrief(tasks: { type: string; text: string }[]): string {
  const note = tasks.find((t) => t.type === "program_note");
  if (!note) return "";
  // The recommendation = first sentence, minus the "Today is a good day for …" lead-in.
  let rec = note.text.split(/(?<=\.)\s/)[0].trim();
  rec = rec.replace(/^today,?\s+is a good day for\s+/i, "").replace(/^today,?\s+/i, "");
  rec = rec.replace(/\.$/, "");
  rec = rec.charAt(0).toUpperCase() + rec.slice(1);
  // Any "Avoid …" constraint from the check-in task.
  const checkIn = tasks.find((t) => t.type === "check_in");
  const avoid = checkIn?.text.match(/Avoid[^.]*\./i)?.[0]?.trim() ?? "";
  return [rec, avoid].filter(Boolean).join(". ");
}

export function Dashboard() {
  const { coach, logout } = useAuth();
  const { activeMember } = useActiveMember();
  const { isLoading: membersLoading, error: membersError, refresh: refreshMembers } = useMembers();

  const [activeTab, setActiveTab] = useState<Tab>("overview");
  const [memberCtx, setMemberCtx] = useState<MemberContext | null>(null);
  const [checkInOpen, setCheckInOpen] = useState(false);

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
    generateStream,
    regenerate,
    variants,
    traceSummary,
    decisionTrace,
    injuryStateUsed,
    loading: genLoading,
    genStatus,
    error: genError,
    llmUnconfigured,
    reset: resetGenerator,
  } = useGenerator(activeMember?.member_id ?? null);

  // Reset generator output when switching members
  useEffect(() => {
    resetGenerator();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeMember?.member_id]);

  // Copilot dock — log generation events + keep it tab-aware.
  const { pushEvent, setContext, isOpen: copilotOpen } = useCopilotDock();

  // Tell the Copilot which surface the coach is currently viewing.
  useEffect(() => {
    setContext({ tab: TAB_LABEL[activeTab] });
  }, [activeTab, setContext]);

  const handleGenerate = useCallback(
    async (prompt: string, minutes: number, engine: "hybrid" | "llm") => {
      const ok = await generateStream(prompt, minutes, engine);
      if (ok) {
        pushEvent(`Generated session · "${prompt}" · ${minutes} min`, {
          kind: "workout_generated",
          prompt,
          minutes,
        });
      }
    },
    [generateStream, pushEvent]
  );

  // Regenerate a fresh variation, aware of the current session (optional tweak).
  const handleRegenerate = useCallback(
    async (adjustment?: string) => {
      const ok = await regenerate(adjustment);
      if (ok) {
        pushEvent(
          adjustment
            ? `Regenerated · "${adjustment}"`
            : "Regenerated a fresh variation",
          { kind: "workout_regenerated" }
        );
      }
    },
    [regenerate, pushEvent]
  );

  /** Switch to Creative tab after "Send to Canvas" */
  const handleSendToCanvas = useCallback(() => {
    setActiveTab("creative");
  }, []);

  const TABS: { id: Tab; label: string }[] = [
    { id: "overview", label: "Overview" },
    { id: "generator", label: "Generate" },
    { id: "analytics", label: "Analytics" },
    { id: "graph", label: "Insights" },
    { id: "creative", label: "Studio" },
  ];

  // Highest-priority goal for the member header meta line
  const primaryGoal =
    (memberCtx?.goals ?? [])
      .slice()
      .sort((a, b) => a.priority - b.priority)[0]?.text ?? null;

  // Injury label for the header pill (region, e.g. "left knee")
  const injuryPill = injury?.region ?? activeMember?.active_injury ?? null;

  // Pre-fill the generator's session intent from the morning brief recommendation
  const briefPrompt = buildIntentFromBrief(memberCtx?.coach_brief?.morning_tasks ?? []);

  return (
    <div className="flex min-h-screen bg-canvas text-ink">
      {/* ── Left rail ──────────────────────────────────────────────────── */}
      <aside className="flex w-60 flex-shrink-0 flex-col border-r border-line bg-canvas">
        {/* Brand */}
        <div className="px-6 py-7">
          <div className="flex items-center gap-2.5">
            <span className="h-2.5 w-2.5 rounded-full bg-clay" />
            <span className="text-[0.8rem] font-medium uppercase tracking-[0.3em] text-ink">
              Atlas
            </span>
          </div>
          <p className="mt-1 pl-5 text-[0.65rem] tracking-wide text-ink-faint">
            Performance Studio
          </p>
        </div>

        {/* Member switcher */}
        <div className="flex-1 overflow-y-auto px-3 py-2">
          <p className="eyebrow mb-3 px-3">Clients</p>
          {membersLoading ? (
            <p className="px-3 text-xs text-ink-faint">Loading…</p>
          ) : membersError ? (
            <p className="px-3 text-xs text-clay">{membersError}</p>
          ) : (
            <MemberSwitcher />
          )}
        </div>

        {/* Coach profile + logout */}
        {coach && (
          <div className="border-t border-line px-4 py-4">
            <div className="flex items-center gap-2.5">
              <div className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-full bg-sand">
                <span className="text-xs font-semibold text-ink">
                  {coach.avatar_initials}
                </span>
              </div>
              <div className="min-w-0 flex-1">
                <p className="truncate text-xs font-medium text-ink">
                  {coach.name}
                </p>
                <p className="truncate text-[0.7rem] text-ink-faint">
                  {coach.email}
                </p>
              </div>
            </div>
            <button
              onClick={logout}
              className="mt-3 text-[0.7rem] text-ink-faint link-underline hover:text-ink"
            >
              Sign out
            </button>
          </div>
        )}
      </aside>

      {/* ── Main ───────────────────────────────────────────────────────── */}
      {/* When the Copilot drawer is open, reserve space on lg+ so the content
          and tabs stay visible beside it (non-modal, persistent). */}
      <main
        className={`relative flex-1 overflow-y-auto transition-[padding] duration-300 ${
          copilotOpen ? "lg:pr-[28rem]" : ""
        }`}
      >
        {!activeMember ? (
          <div className="flex h-full min-h-64 items-center justify-center">
            <p className="text-sm text-ink-faint">Select a client to begin.</p>
          </div>
        ) : (
          <div className="mx-auto max-w-5xl px-6 py-8">
            {/* Member header card */}
            <MemberHeaderCard
              member={activeMember}
              goalText={primaryGoal}
              injuryLabel={injuryPill}
            />

            {/* Centered pill tab nav — under the member's name */}
            <div className="mt-6 flex justify-center">
              <nav className="inline-flex gap-1 rounded-full border border-line bg-surface p-1">
                {TABS.map((tab) => (
                  <button
                    key={tab.id}
                    type="button"
                    onClick={() => setActiveTab(tab.id)}
                    className={`rounded-full px-5 py-2 text-sm font-medium transition-colors ${
                      activeTab === tab.id
                        ? "bg-ink text-canvas"
                        : "text-ink-soft hover:text-ink"
                    }`}
                  >
                    {tab.label}
                  </button>
                ))}
              </nav>
            </div>

            {/* Tab content */}
            <div className="mt-8">
              {/* ── Overview ──────────────────────────────────────────── */}
              {activeTab === "overview" && (
                <div className="space-y-10">
                  {memberCtx && (
                    <section>
                      <p className="eyebrow mb-4">Morning Brief</p>
                      <MorningBrief
                        tasks={memberCtx.coach_brief.morning_tasks}
                        generatedFor={memberCtx.coach_brief.generated_for}
                      />
                    </section>
                  )}

                  {injury ? (
                    <section className="space-y-5">
                      <p className="eyebrow">Recovery</p>
                      <InjuryStatusCard
                        injury={injury}
                        currentState={currentState}
                        needsCheckIn={needsCheckIn}
                        onCheckIn={() => setCheckInOpen(true)}
                      />
                      <InjuryTimeline history={injuryHistory} />
                    </section>
                  ) : firstInjury ? (
                    <p className="text-sm text-ink-faint">Loading recovery data…</p>
                  ) : null}
                </div>
              )}

              {/* ── Other tabs ────────────────────────────────────────── */}
                {activeTab === "generator" && (
                  <div className="space-y-6">
                    <div className="rounded-2xl border border-line bg-surface p-6 space-y-4">
                      <div>
                        <p className="eyebrow mb-1">Generator</p>
                        <h3 className="font-display text-2xl font-light text-ink">
                          Compose a session
                        </h3>
                        <p className="mt-1 text-sm text-ink-soft">
                          One deterministic safety pass, then a single
                          structured session with stimulus gauges.
                        </p>
                      </div>

                      {injury && needsCheckIn && (
                        <InjuryWarning
                          lastCheckIn={currentState}
                          staleCheckIn={needsCheckIn}
                          onCheckIn={() => setCheckInOpen(true)}
                        />
                      )}

                      {llmUnconfigured && (
                        <div className="rounded-lg border border-clay/30 bg-clay/5 px-4 py-3 text-sm text-clay">
                          <strong>LLM not configured</strong> — set{" "}
                          <code className="rounded bg-clay/10 px-1 py-0.5 text-xs">
                            ANTHROPIC_API_KEY
                          </code>{" "}
                          and restart. The safety filter and decision trace
                          still work without it.
                        </div>
                      )}

                      {genError && !llmUnconfigured && (
                        <div className="rounded-lg border border-clay/30 bg-clay/5 px-4 py-3 text-sm text-clay">
                          {genError}
                        </div>
                      )}

                      <GeneratorPanel
                        onGenerate={handleGenerate}
                        loading={genLoading}
                        disabled={false}
                        defaultPrompt={briefPrompt}
                      />

                      {/* Live streaming progress */}
                      {genLoading && genStatus && (
                        <div className="flex items-center gap-2.5 rounded-lg border border-line bg-canvas/60 px-4 py-2.5 text-sm">
                          <span className="h-3.5 w-3.5 flex-shrink-0 animate-spin rounded-full border-2 border-clay/30 border-t-clay" />
                          <span className="text-ink-soft">
                            {genStatus.stage === "resolve" && "Resolving intent…"}
                            {genStatus.stage === "safety" &&
                              (genStatus.safe_count != null
                                ? `Safety filter — ${genStatus.safe_count} safe · ${genStatus.removed_count} filtered out`
                                : "Running safety filter…")}
                            {genStatus.stage === "structuring" &&
                              (genStatus.engine === "llm"
                                ? "Structuring session…"
                                : "Assembling plan + writing rationale…")}
                          </span>
                          {genStatus.stage === "safety" && genStatus.safe_count != null && (
                            <span className="ml-auto text-xs text-emerald-600">✓ deterministic</span>
                          )}
                        </div>
                      )}
                    </div>

                    {variants.length > 0 && (
                      <div className="space-y-4">
                        {(traceSummary?.stale_check_in ||
                          (injuryStateUsed !== null &&
                            variants[0]?.provenance?.stale_check_in)) && (
                          <InjuryWarning
                            lastCheckIn={injuryStateUsed}
                            staleCheckIn={true}
                            onCheckIn={() => setCheckInOpen(true)}
                          />
                        )}

                        <VariantChooser
                          variants={variants}
                          onRegenerate={handleRegenerate}
                          onSendToCanvas={handleSendToCanvas}
                          onWorkoutSent={refreshMembers}
                          generatorLoading={genLoading}
                          memberId={activeMember?.member_id}
                          memberName={activeMember?.name}
                        />

                        {traceSummary && (
                          <ProvenanceTrace
                            traceSummary={traceSummary}
                            healingPhase={variants[0]?.provenance?.healing_phase}
                            injuryRegion={injury?.region}
                          />
                        )}

                        {decisionTrace.length > 0 && (
                          <DecisionTrace steps={decisionTrace} />
                        )}
                      </div>
                    )}
                  </div>
                )}

                {activeTab === "analytics" && (
                  <AnalyticsPanel
                    memberCtx={memberCtx}
                    injuryHistory={injuryHistory}
                    injuryLabel={injury?.region ? `${injury.region} injury` : undefined}
                  />
                )}

                {activeTab === "graph" && (
                  <GraphExplorer memberId={activeMember?.member_id ?? null} />
                )}

                {activeTab === "creative" && (
                  <div className="space-y-4">
                    <div>
                      <p className="eyebrow mb-1">Studio</p>
                      <h3 className="font-display text-2xl font-light text-ink">
                        Creative canvas
                      </h3>
                      <p className="mt-1 text-sm text-ink-soft">
                        Compose from the catalog or send a generated plan here to
                        refine. Safety warnings flag anything contraindicated for{" "}
                        {activeMember.name}.
                      </p>
                    </div>
                    <CreativeCanvas memberId={activeMember?.member_id ?? null} />
                  </div>
                )}
            </div>
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

      {/* Floating Copilot dock (chat-only). Event chips jump to the Generator. */}
      <CopilotDock onOpenGenerator={() => setActiveTab("generator")} />

      {/* Client Inbox (trainer↔client messages) — separate from the Copilot. */}
      <ClientInbox />
    </div>
  );
}
