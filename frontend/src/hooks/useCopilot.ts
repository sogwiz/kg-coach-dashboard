/**
 * useCopilot — streaming chat hook for the Copilot panel.
 *
 * Manages:
 *   - Message history (ChatMessage[])
 *   - Loading past chat history on init via GET /api/copilot/members/{id}/chat-history
 *   - Streaming send via POST /api/copilot/chat (falls back to sync on error)
 *   - isStreaming / isLoading states
 *
 * The hook is keyed by memberId — switching members resets state.
 */

import { useState, useEffect, useRef, useCallback } from "react";
import type { ChatAttachment, ChatMessage } from "../lib/api";
import { fetchChatHistory, streamCopilot } from "../lib/api";

export interface UseCopilotResult {
  messages: ChatMessage[];
  isStreaming: boolean;
  isLoadingHistory: boolean;
  historyError: string | null;
  llmUnavailable: boolean;
  send: (text: string, attachments?: ChatAttachment[]) => Promise<void>;
  clearError: () => void;
}

export function useCopilot(memberId: string | null): UseCopilotResult {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [isLoadingHistory, setIsLoadingHistory] = useState(false);
  const [historyError, setHistoryError] = useState<string | null>(null);
  const [llmUnavailable, setLlmUnavailable] = useState(false);

  // Track the member whose history is loaded to avoid double-loading
  const loadedMemberRef = useRef<string | null>(null);

  // Reset on member change
  useEffect(() => {
    if (!memberId) {
      setMessages([]);
      loadedMemberRef.current = null;
      return;
    }
    if (loadedMemberRef.current === memberId) return;

    loadedMemberRef.current = memberId;
    setMessages([]);
    setHistoryError(null);
    setLlmUnavailable(false);

    // Load seed history
    setIsLoadingHistory(true);
    fetchChatHistory(memberId)
      .then((history) => {
        const withRoles: ChatMessage[] = history.map((msg) => ({
          ...msg,
          role: msg.from === "coach" ? ("assistant" as const) : ("user" as const),
        }));
        setMessages(withRoles);
      })
      .catch((err) => {
        const msg = err instanceof Error ? err.message : String(err);
        setHistoryError(`Could not load chat history: ${msg}`);
      })
      .finally(() => {
        setIsLoadingHistory(false);
      });
  }, [memberId]);

  const send = useCallback(
    async (text: string, attachments: ChatAttachment[] = []) => {
      if (!memberId || isStreaming) return;

      // Optimistically add the user message
      const userMsg: ChatMessage = {
        ts: new Date().toISOString(),
        from: "coach",
        text,
        attachments,
        role: "user",
      };

      // Add a placeholder assistant message for streaming
      const assistantPlaceholder: ChatMessage = {
        ts: new Date().toISOString(),
        from: "coach",
        text: "",
        attachments: [],
        role: "assistant",
        isStreaming: true,
      };

      setMessages((prev) => [...prev, userMsg, assistantPlaceholder]);
      setIsStreaming(true);
      setLlmUnavailable(false);

      try {
        const reader = await streamCopilot(memberId, text, attachments);
        let accumulated = "";

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          accumulated += value;

          // Update the last (streaming) message with the accumulated text
          setMessages((prev) => {
            const updated = [...prev];
            const last = updated[updated.length - 1];
            if (last && last.isStreaming) {
              updated[updated.length - 1] = {
                ...last,
                text: accumulated,
              };
            }
            return updated;
          });
        }

        // Mark streaming complete
        setMessages((prev) => {
          const updated = [...prev];
          const last = updated[updated.length - 1];
          if (last && last.isStreaming) {
            updated[updated.length - 1] = {
              ...last,
              text: accumulated || "(No response)",
              isStreaming: false,
            };
          }
          return updated;
        });
      } catch (err) {
        const errMsg = err instanceof Error ? err.message : String(err);

        // Check for 503 (LLM not configured)
        const isLlmError =
          errMsg.includes("503") ||
          errMsg.toLowerCase().includes("api key") ||
          errMsg.toLowerCase().includes("not configured");

        setLlmUnavailable(isLlmError);

        // Update the placeholder with the error
        setMessages((prev) => {
          const updated = [...prev];
          const last = updated[updated.length - 1];
          if (last && last.isStreaming) {
            updated[updated.length - 1] = {
              ...last,
              text: isLlmError
                ? "LLM not configured — set ANTHROPIC_API_KEY and restart the server."
                : `Error: ${errMsg}`,
              isStreaming: false,
            };
          }
          return updated;
        });
      } finally {
        setIsStreaming(false);
      }
    },
    [memberId, isStreaming]
  );

  const clearError = useCallback(() => {
    setHistoryError(null);
    setLlmUnavailable(false);
  }, []);

  return {
    messages,
    isStreaming,
    isLoadingHistory,
    historyError,
    llmUnavailable,
    send,
    clearError,
  };
}
