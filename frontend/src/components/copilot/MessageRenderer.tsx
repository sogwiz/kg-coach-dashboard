/**
 * MessageRenderer — renders a single chat message with text and attachments.
 */

import type { ReactNode } from "react";
import type { ChatMessage } from "../../lib/api";

interface MessageRendererProps {
  message: ChatMessage;
  /** Click handler for logged event chips (e.g. "open the generated plan"). */
  onEventClick?: () => void;
  /** Deep-link handler for [[msg:<ts>]] tokens → open that client message in the Inbox. */
  onOpenMessage?: (ts: string) => void;
}

// Parse Copilot text, turning [[msg:<ts>]] deep-link tokens into inline chips
// that open the referenced client message in the Inbox.
const MSG_TOKEN = /\[\[msg:([^\]]+)\]\]/g;
function renderText(text: string, onOpenMessage?: (ts: string) => void): ReactNode {
  if (!text || !text.includes("[[msg:")) return text;
  const out: ReactNode[] = [];
  let last = 0;
  let key = 0;
  let m: RegExpExecArray | null;
  MSG_TOKEN.lastIndex = 0;
  while ((m = MSG_TOKEN.exec(text)) !== null) {
    if (m.index > last) out.push(text.slice(last, m.index));
    const ts = m[1];
    out.push(
      <button
        key={`lnk-${key++}`}
        type="button"
        onClick={() => onOpenMessage?.(ts)}
        className="mx-0.5 inline-flex items-center gap-0.5 rounded bg-clay/10 px-1.5 py-0.5 align-baseline text-[0.7rem] font-medium text-clay transition-colors hover:bg-clay/20"
      >
        ↗ message
      </button>
    );
    last = m.index + m[0].length;
  }
  if (last < text.length) out.push(text.slice(last));
  return out;
}

export function MessageRenderer({ message, onEventClick, onOpenMessage }: MessageRendererProps) {
  // Logged activity (e.g. a generated workout) — a centered, clickable chip.
  if (message.role === "event") {
    return (
      <div className="flex justify-center py-1">
        <button
          type="button"
          onClick={onEventClick}
          className="group inline-flex items-center gap-2 rounded-full border border-line bg-canvas px-3.5 py-1.5 text-xs text-ink-soft transition-colors hover:border-ink hover:text-ink"
        >
          <span className="h-1.5 w-1.5 rounded-full bg-clay" />
          <span className="font-medium">{message.text}</span>
          <span className="text-ink-faint group-hover:text-clay">View →</span>
        </button>
      </div>
    );
  }

  const isUser = message.from === "coach" && message.role === "user";
  const isHistoricalMember = message.from === "member";

  const alignClass = isUser ? "items-end" : "items-start";
  const bubbleClass = isUser
    ? "bg-indigo-600 text-white"
    : isHistoricalMember
    ? "bg-blue-50 text-slate-800 border border-blue-100"
    : "bg-white text-slate-800 border border-slate-200";

  // Format timestamp
  const ts = message.ts
    ? new Date(message.ts).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
    : "";

  return (
    <div className={`flex flex-col gap-0.5 ${alignClass}`}>
      {/* Role label */}
      <div className={`flex items-center gap-1 ${isUser ? "flex-row-reverse" : "flex-row"}`}>
        <span className="text-xs text-slate-400">
          {isUser ? "You" : isHistoricalMember ? message.from : "Copilot"}
        </span>
        {ts && <span className="text-xs text-slate-300">{ts}</span>}
      </div>

      {/* Bubble */}
      <div className={`max-w-sm md:max-w-md rounded-xl px-3 py-2 text-sm shadow-sm ${bubbleClass}`}>
        {message.isStreaming && !message.text ? (
          <span className="flex gap-1 py-1">
            <span className="w-1.5 h-1.5 rounded-full bg-slate-400 animate-bounce [animation-delay:0ms]" />
            <span className="w-1.5 h-1.5 rounded-full bg-slate-400 animate-bounce [animation-delay:150ms]" />
            <span className="w-1.5 h-1.5 rounded-full bg-slate-400 animate-bounce [animation-delay:300ms]" />
          </span>
        ) : (
          <p className="whitespace-pre-wrap leading-relaxed">
            {renderText(message.text, onOpenMessage)}
          </p>
        )}

        {/* Attachments */}
        {message.attachments && message.attachments.length > 0 && (
          <div className="mt-2 space-y-1">
            {message.attachments.map((att, i) => (
              <div
                key={i}
                className="flex items-center gap-1 rounded bg-black/10 px-2 py-1 text-xs"
              >
                <span>
                  {att.type?.startsWith("image") ? "IMG" : "FILE"}
                </span>
                {att.caption && <span className="text-xs opacity-80">{att.caption}</span>}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
