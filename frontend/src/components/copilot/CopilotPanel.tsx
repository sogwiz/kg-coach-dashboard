/**
 * CopilotPanel — Copilot chat UI with streaming responses.
 *
 * Loads the member's past chat_history (with inline images) on open
 * via GET /api/copilot/members/{id}/chat-history, shows message list
 * + streaming display, binds follow-ups to the same per-member thread.
 *
 * Also shows charts (Adherence, Sleep, Biomarkers, Injury Progress)
 * derived from the active member's data.
 */

import { useRef, useEffect } from "react";
import { useCopilot } from "../../hooks/useCopilot";
import { MessageRenderer } from "./MessageRenderer";
import { ChatComposer } from "./ChatComposer";
import { QuickPrompts } from "./QuickPrompts";
import { AdherenceChart } from "../charts/AdherenceChart";
import { SleepChart } from "../charts/SleepChart";
import { BiomarkersCard } from "../charts/BiomarkersCard";
import { InjuryProgressChart } from "../charts/InjuryProgressChart";
import type { MemberContext, InjuryState } from "../../lib/api";

interface CopilotPanelProps {
  memberId: string | null;
  memberCtx: MemberContext | null;
  injuryHistory?: InjuryState[];
  injuryLabel?: string;
}

export function CopilotPanel({
  memberId,
  memberCtx,
  injuryHistory = [],
  injuryLabel,
}: CopilotPanelProps) {
  const { messages, isStreaming, isLoadingHistory, historyError, llmUnavailable, send } =
    useCopilot(memberId);

  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom when messages update
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  if (!memberId) {
    return (
      <div className="flex items-center justify-center h-40 text-slate-400 text-sm">
        Select a member to open the Copilot.
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* LLM unavailable banner */}
      {llmUnavailable && (
        <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-700">
          <strong>LLM not configured</strong> — Set{" "}
          <code className="text-xs bg-amber-100 px-1 py-0.5 rounded">ANTHROPIC_API_KEY</code>{" "}
          and restart the server to enable the AI Copilot.
        </div>
      )}

      {/* Charts section */}
      {memberCtx && (
        <div className="bg-white rounded-xl border border-slate-200 p-5 space-y-5">
          <h3 className="text-sm font-semibold text-slate-800">Member Analytics</h3>

          <BiomarkersCard
            restingHr={memberCtx.biomarkers.resting_hr_bpm}
            hrv={memberCtx.biomarkers.hrv_ms}
            weightTrend={memberCtx.biomarkers.weight_trend_kg}
          />

          <AdherenceChart data={memberCtx.adherence.weekly_completion_pct} />

          <SleepChart sleepHours={memberCtx.biomarkers.sleep_hours_last_7_days} />

          {injuryHistory.length > 0 && (
            <InjuryProgressChart
              history={injuryHistory}
              injuryLabel={injuryLabel ?? "Injury"}
            />
          )}
        </div>
      )}

      {/* Chat panel */}
      <div className="bg-white rounded-xl border border-slate-200 flex flex-col" style={{ minHeight: "480px" }}>
        {/* Header */}
        <div className="px-5 py-4 border-b border-slate-100 flex items-center justify-between">
          <div>
            <h3 className="text-sm font-semibold text-slate-800">AI Copilot</h3>
            <p className="text-xs text-slate-400 mt-0.5">
              Grounded in {memberCtx?.profile.name ?? "member"}'s knowledge graph data
            </p>
          </div>
          {isStreaming && (
            <span className="text-xs text-indigo-500 animate-pulse">Thinking...</span>
          )}
        </div>

        {/* Message list */}
        <div className="flex-1 overflow-y-auto px-5 py-4 space-y-4">
          {isLoadingHistory && (
            <p className="text-xs text-slate-400">Loading chat history...</p>
          )}
          {historyError && (
            <p className="text-xs text-amber-600">{historyError}</p>
          )}
          {!isLoadingHistory && messages.length === 0 && (
            <div className="flex flex-col items-center justify-center py-8 text-center gap-2">
              <p className="text-sm text-slate-500">
                No conversation yet. Ask a question below or use a quick prompt.
              </p>
            </div>
          )}
          {messages.map((msg, i) => (
            <MessageRenderer key={i} message={msg} />
          ))}
          <div ref={messagesEndRef} />
        </div>

        {/* Quick prompts */}
        <div className="px-5 py-3 border-t border-slate-100">
          <QuickPrompts
            onSelect={(p) => send(p)}
            disabled={isStreaming}
            clientName={memberCtx?.profile.name}
            injury={memberCtx?.injuries?.[0]?.region ?? null}
          />
        </div>

        {/* Composer */}
        <div className="px-5 pb-4 pt-2">
          <ChatComposer
            onSend={send}
            disabled={isStreaming}
          />
        </div>
      </div>
    </div>
  );
}
