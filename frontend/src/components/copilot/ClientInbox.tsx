/**
 * ClientInbox — the trainer↔client message thread (distinct from the Copilot).
 *
 * A quick chat view with the client: the seed chat history (with image
 * placeholders) plus a compose box. Opened from the member header's mail
 * button or deep-linked from a Copilot answer (which can point at a specific
 * message via a [[msg:<ts>]] token → openInbox(ts)).
 */

import { useEffect, useRef, useState } from "react";
import { useActiveMember } from "../../state/activeMember";
import { useCopilotDock } from "../../state/copilot";
import { fetchChatHistory, type ChatMessage } from "../../lib/api";

export function ClientInbox() {
  const { activeMember } = useActiveMember();
  const { inboxOpen, inboxHighlightTs, closeInbox } = useCopilotDock();

  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [loading, setLoading] = useState(false);
  const [draft, setDraft] = useState("");
  const endRef = useRef<HTMLDivElement>(null);
  const highlightRef = useRef<HTMLDivElement>(null);

  const memberId = activeMember?.member_id ?? null;

  // Load the client conversation when the inbox opens
  useEffect(() => {
    if (!inboxOpen || !memberId) return;
    setLoading(true);
    fetchChatHistory(memberId)
      .then((h) => setMessages(h))
      .catch(() => setMessages([]))
      .finally(() => setLoading(false));
  }, [inboxOpen, memberId]);

  // Scroll to the deep-linked message (or the bottom) once loaded
  useEffect(() => {
    if (!inboxOpen || loading) return;
    const t = setTimeout(() => {
      if (inboxHighlightTs && highlightRef.current) {
        highlightRef.current.scrollIntoView({ behavior: "smooth", block: "center" });
      } else {
        endRef.current?.scrollIntoView({ behavior: "auto" });
      }
    }, 80);
    return () => clearTimeout(t);
  }, [inboxOpen, loading, inboxHighlightTs, messages]);

  if (!inboxOpen || !activeMember) return null;

  const firstName = activeMember.name.split(" ")[0];

  const handleSend = () => {
    const text = draft.trim();
    if (!text) return;
    // Mock send — append locally as a coach message.
    setMessages((m) => [
      ...m,
      { ts: new Date().toISOString(), from: "coach", text, attachments: [] },
    ]);
    setDraft("");
    setTimeout(() => endRef.current?.scrollIntoView({ behavior: "smooth" }), 40);
  };

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center p-4">
      {/* Backdrop */}
      <div className="absolute inset-0 bg-ink/40" onClick={closeInbox} />

      {/* Panel */}
      <div className="relative flex max-h-[80vh] w-full max-w-lg flex-col overflow-hidden rounded-2xl border border-line bg-canvas shadow-2xl">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-line px-5 py-4">
          <div className="flex items-center gap-2">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="text-clay">
              <rect x="3" y="5" width="18" height="14" rx="2" />
              <path d="m3 7 9 6 9-6" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
            <div>
              <p className="eyebrow">Client Inbox</p>
              <p className="text-sm font-medium text-ink">Messages with {firstName}</p>
            </div>
          </div>
          <button
            onClick={closeInbox}
            aria-label="Close"
            className="text-ink-faint transition-colors hover:text-ink"
          >
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M6 6l12 12M6 18L18 6" strokeLinecap="round" />
            </svg>
          </button>
        </div>

        {/* Messages */}
        <div className="flex-1 space-y-3 overflow-y-auto px-5 py-4">
          {loading && <p className="text-xs text-ink-faint">Loading messages…</p>}
          {!loading && messages.length === 0 && (
            <p className="text-sm text-ink-faint">No messages yet.</p>
          )}
          {messages.map((m, i) => {
            const isClient = m.from === "member";
            const highlighted = inboxHighlightTs != null && m.ts === inboxHighlightTs;
            return (
              <div
                key={i}
                ref={highlighted ? highlightRef : undefined}
                className={`flex flex-col ${isClient ? "items-start" : "items-end"}`}
              >
                <span className="mb-0.5 text-[10px] text-ink-faint">
                  {isClient ? firstName : "You"} ·{" "}
                  {new Date(m.ts).toLocaleString([], {
                    month: "short",
                    day: "numeric",
                    hour: "2-digit",
                    minute: "2-digit",
                  })}
                </span>
                <div
                  className={`max-w-[80%] rounded-2xl px-3.5 py-2 text-sm transition-shadow ${
                    isClient
                      ? "bg-surface text-ink border border-line"
                      : "bg-ink text-canvas"
                  } ${highlighted ? "ring-2 ring-clay ring-offset-2 ring-offset-canvas" : ""}`}
                >
                  <p className="whitespace-pre-wrap leading-relaxed">{m.text}</p>
                  {m.attachments && m.attachments.length > 0 && (
                    <div className="mt-2 flex flex-wrap gap-1.5">
                      {m.attachments.map((a, j) => (
                        <span
                          key={j}
                          className={`inline-flex items-center gap-1 rounded-md px-2 py-1 text-[11px] ${
                            isClient ? "bg-sand text-ink-soft" : "bg-canvas/15 text-canvas"
                          }`}
                        >
                          🖼 {a.caption ?? "image"}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            );
          })}
          <div ref={endRef} />
        </div>

        {/* Composer */}
        <div className="border-t border-line px-5 py-3">
          <div className="flex items-end gap-2">
            <textarea
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  handleSend();
                }
              }}
              rows={1}
              placeholder={`Message ${firstName}…`}
              className="flex-1 resize-none rounded-xl border border-line bg-surface px-3 py-2 text-sm text-ink placeholder-ink-faint focus:border-ink focus:outline-none"
            />
            <button
              onClick={handleSend}
              disabled={!draft.trim()}
              className="rounded-full bg-ink px-4 py-2 text-sm font-semibold text-canvas transition-colors hover:bg-clay disabled:opacity-50"
            >
              Send
            </button>
          </div>
          <p className="mt-1.5 text-[11px] text-ink-faint">
            This is your conversation with the client — separate from the Copilot.
          </p>
        </div>
      </div>
    </div>
  );
}
