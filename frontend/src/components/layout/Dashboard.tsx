/**
 * Dashboard — main layout with sidebar + main content area.
 *
 * Structure:
 *   - Sidebar: coach profile / logout, member switcher
 *   - Main: tabs for member overview (this phase), generator, copilot (later)
 *
 * The layout is intentionally built to accept additional main-content
 * tabs/sections in Phases 9 and 10.
 */

import { useState, useEffect } from "react";
import { useAuth } from "../../state/auth";
import { useMembers } from "../../hooks/useMembers";
import { useActiveMember } from "../../state/activeMember";
import { useInjury } from "../../hooks/useInjury";
import { fetchMember, type MemberContext } from "../../lib/api";
import { MemberSwitcher } from "../member/MemberSwitcher";
import { MemberHeader } from "../member/MemberHeader";
import { MorningBrief } from "../member/MorningBrief";
import { InjuryStatusCard } from "../injury/InjuryStatusCard";
import { InjuryTimeline } from "../injury/InjuryTimeline";
import { CheckInModal } from "../injury/CheckInModal";

type Tab = "overview";

export function Dashboard() {
  const { coach, logout } = useAuth();
  const { activeMember } = useActiveMember();
  const { isLoading: membersLoading, error: membersError } = useMembers();

  const [_activeTab] = useState<Tab>("overview");
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

  // Most recent adherence %
  const adherenceWeeks = memberCtx?.adherence?.weekly_completion_pct ?? [];
  const lastAdherencePct =
    adherenceWeeks.length > 0
      ? adherenceWeeks[adherenceWeeks.length - 1].pct
      : null;

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
            <p className="text-xs text-slate-400 px-3">Loading members…</p>
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
          <div className="max-w-3xl mx-auto px-6 py-6 space-y-6">
            {/* Member header */}
            <MemberHeader
              member={activeMember}
              adherencePct={lastAdherencePct}
            />

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
              // Injury still loading
              <div className="bg-white rounded-xl border border-slate-200 p-4">
                <p className="text-sm text-slate-400">Loading injury data…</p>
              </div>
            ) : null}

            {/* Placeholder for Phase 9 generator panel */}
            <div className="bg-white rounded-xl border border-dashed border-slate-300 p-6 text-center">
              <p className="text-sm text-slate-400">
                Generator panel — coming in Phase 9
              </p>
            </div>

            {/* Placeholder for Phase 10 copilot panel */}
            <div className="bg-white rounded-xl border border-dashed border-slate-300 p-6 text-center">
              <p className="text-sm text-slate-400">
                Copilot panel — coming in Phase 10
              </p>
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
    </div>
  );
}
