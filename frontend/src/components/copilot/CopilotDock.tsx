/**
 * CopilotDock — floating Copilot bubble + right-side chat drawer.
 *
 * Chat-only (analytics now live in their own member tab). Reads the shared
 * conversation from CopilotProvider so generation events logged elsewhere show
 * up inline. Clicking a logged event chip opens the related surface via
 * onOpenGenerator.
 */

import { useEffect, useRef } from "react";
import { useActiveMember } from "../../state/activeMember";
import { useCopilotDock } from "../../state/copilot";
import { MessageRenderer } from "./MessageRenderer";
import { ChatComposer } from "./ChatComposer";
import { QuickPrompts } from "./QuickPrompts";

interface CopilotDockProps {
  /** Called when a logged "workout generated" event chip is clicked. */
  onOpenGenerator?: () => void;
}

export function CopilotDock({ onOpenGenerator }: CopilotDockProps) {
  const { activeMember } = useActiveMember();
  const {
    messages,
    isStreaming,
    isLoadingHistory,
    llmUnavailable,
    send,
    isOpen,
    close,
    toggle,
    unread,
    context,
    openInbox,
  } = useCopilotDock();

  const endRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (isOpen) endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isOpen]);

  if (!activeMember) return null;

  const clientFirstName = activeMember.name.split(" ")[0];

  // Event chips jump to the related surface but KEEP the drawer open.
  const handleEventClick = () => {
    onOpenGenerator?.();
  };

  return (
    <>
      {/* Floating bubble — only when closed (the drawer has its own X) */}
      {!isOpen && (
        <button
          type="button"
          onClick={toggle}
          aria-label="Open Copilot"
          className="fixed bottom-6 right-6 z-40 flex h-14 w-14 items-center justify-center rounded-full bg-ink text-canvas shadow-lg transition-transform hover:scale-105 hover:bg-clay"
        >
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
            <path d="M21 11.5a8.38 8.38 0 0 1-8.5 8.5 8.5 8.5 0 0 1-3.8-.9L3 21l1.9-5.7a8.5 8.5 0 0 1-.9-3.8 8.38 8.38 0 0 1 8.5-8.5 8.5 8.5 0 0 1 8.5 8.5z" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
          {unread > 0 && (
            <span className="absolute -right-0.5 -top-0.5 flex h-5 min-w-[1.25rem] items-center justify-center rounded-full bg-clay px-1 text-[0.65rem] font-bold text-white ring-2 ring-canvas">
              {unread}
            </span>
          )}
        </button>
      )}

      {/* Drawer — non-modal: no backdrop, so tabs/content stay interactive and
          the drawer persists across tab switches for this client. */}
      {isOpen && (
          <aside className="fixed right-0 top-0 z-40 flex h-full w-full max-w-md flex-col border-l border-line bg-canvas shadow-2xl">
            {/* Header */}
            <div className="flex items-center justify-between border-b border-line px-5 py-4">
              <div>
                <p className="eyebrow">Copilot</p>
                <p className="mt-0.5 text-sm text-ink-soft">
                  {activeMember.name}
                  {context.tab && (
                    <span className="text-ink-faint"> · viewing {context.tab}</span>
                  )}
                </p>
              </div>
              <div className="flex items-center gap-1">
                <button
                  type="button"
                  onClick={() => openInbox()}
                  aria-label="Open client inbox"
                  title="Client inbox"
                  className="flex h-8 w-8 items-center justify-center rounded-full text-ink-faint transition-colors hover:bg-sand hover:text-ink"
                >
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
                    <rect x="3" y="5" width="18" height="14" rx="2" />
                    <path d="m3 7 9 6 9-6" strokeLinecap="round" strokeLinejoin="round" />
                  </svg>
                </button>
                <button
                  type="button"
                  onClick={close}
                  aria-label="Close"
                  className="flex h-8 w-8 items-center justify-center rounded-full text-ink-faint transition-colors hover:bg-sand hover:text-ink"
                >
                  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M6 6l12 12M6 18L18 6" strokeLinecap="round" />
                  </svg>
                </button>
              </div>
            </div>

            {/* LLM unavailable */}
            {llmUnavailable && (
              <div className="border-b border-clay/20 bg-clay/5 px-5 py-2.5 text-xs text-clay">
                <strong>LLM not configured</strong> — set <code className="rounded bg-clay/10 px-1">ANTHROPIC_API_KEY</code> and restart.
              </div>
            )}

            {/* Messages */}
            <div className="flex-1 space-y-4 overflow-y-auto px-5 py-4">
              {isLoadingHistory && (
                <p className="text-xs text-ink-faint">Loading chat history…</p>
              )}
              {!isLoadingHistory && messages.length === 0 && (
                <div className="flex h-full flex-col items-center justify-center gap-2 text-center">
                  <p className="text-sm text-ink-soft">
                    Your AI assistant for {activeMember.name}. Ask about adherence,
                    sleep, labs, injury, the current plan, or training methods.
                  </p>
                  <p className="text-xs text-ink-faint">
                    Client messages live in the{" "}
                    <button
                      type="button"
                      onClick={() => openInbox()}
                      className="font-medium text-clay underline-offset-2 hover:underline"
                    >
                      inbox
                    </button>
                    .
                  </p>
                </div>
              )}
              {messages.map((msg, i) => (
                <MessageRenderer
                  key={i}
                  message={msg}
                  onEventClick={handleEventClick}
                  onOpenMessage={(ts) => openInbox(ts)}
                />
              ))}
              <div ref={endRef} />
            </div>

            {/* Quick prompts */}
            <div className="border-t border-line px-5 py-3">
              <QuickPrompts
                onSelect={(p) => send(p)}
                disabled={isStreaming}
                clientName={clientFirstName}
                injury={activeMember.active_injury}
              />
            </div>

            {/* Composer */}
            <div className="px-5 pb-4 pt-2">
              <ChatComposer onSend={send} disabled={isStreaming} />
            </div>
          </aside>
      )}
    </>
  );
}
