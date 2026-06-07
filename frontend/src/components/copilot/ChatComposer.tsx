/**
 * ChatComposer — text input + image attach for the Copilot panel.
 */

import { useState, useRef, type KeyboardEvent } from "react";
import type { ChatAttachment } from "../../lib/api";

interface ChatComposerProps {
  onSend: (text: string, attachments: ChatAttachment[]) => void;
  disabled?: boolean;
  placeholder?: string;
}

export function ChatComposer({
  onSend,
  disabled = false,
  placeholder = "Ask a question about this member...",
}: ChatComposerProps) {
  const [text, setText] = useState("");
  const [attachments, setAttachments] = useState<ChatAttachment[]>([]);
  const fileRef = useRef<HTMLInputElement>(null);

  const handleSend = () => {
    const trimmed = text.trim();
    if (!trimmed || disabled) return;
    onSend(trimmed, attachments);
    setText("");
    setAttachments([]);
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files) return;
    const newAtts: ChatAttachment[] = [];
    for (const file of Array.from(files)) {
      if (!file.type.startsWith("image/")) continue;
      const reader = new FileReader();
      reader.onload = (ev) => {
        newAtts.push({
          type: file.type,
          url: ev.target?.result as string,
          caption: file.name,
        });
        if (newAtts.length === files.length) {
          setAttachments((prev) => [...prev, ...newAtts]);
        }
      };
      reader.readAsDataURL(file);
    }
    // Reset input
    e.target.value = "";
  };

  const removeAttachment = (i: number) => {
    setAttachments((prev) => prev.filter((_, idx) => idx !== i));
  };

  return (
    <div className="space-y-2">
      {/* Attachment previews */}
      {attachments.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {attachments.map((att, i) => (
            <div
              key={i}
              className="flex items-center gap-1 bg-indigo-50 border border-indigo-200 rounded-full px-2.5 py-1 text-xs text-indigo-700"
            >
              <span>IMG: {att.caption ?? "image"}</span>
              <button
                type="button"
                onClick={() => removeAttachment(i)}
                className="text-indigo-400 hover:text-indigo-700 font-bold ml-0.5"
              >
                x
              </button>
            </div>
          ))}
        </div>
      )}

      {/* Input row */}
      <div className="flex gap-2 items-end">
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={disabled}
          placeholder={placeholder}
          rows={2}
          className="flex-1 resize-none rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed"
        />

        {/* Attach image */}
        <button
          type="button"
          onClick={() => fileRef.current?.click()}
          disabled={disabled}
          title="Attach image"
          className="flex-shrink-0 rounded-lg border border-slate-200 bg-white px-3 py-2 text-slate-500 hover:bg-slate-50 hover:text-slate-700 disabled:opacity-50 disabled:cursor-not-allowed text-sm"
        >
          IMG
        </button>
        <input
          ref={fileRef}
          type="file"
          accept="image/*"
          multiple
          className="hidden"
          onChange={handleFileChange}
        />

        {/* Send */}
        <button
          type="button"
          onClick={handleSend}
          disabled={disabled || !text.trim()}
          className="flex-shrink-0 rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          Send
        </button>
      </div>
      <p className="text-xs text-slate-400">Enter to send, Shift+Enter for new line.</p>
    </div>
  );
}
