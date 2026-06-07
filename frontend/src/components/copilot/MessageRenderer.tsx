/**
 * MessageRenderer — renders a single chat message with text and attachments.
 */

import type { ChatMessage } from "../../lib/api";

interface MessageRendererProps {
  message: ChatMessage;
}

export function MessageRenderer({ message }: MessageRendererProps) {
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
          <p className="whitespace-pre-wrap leading-relaxed">{message.text}</p>
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
