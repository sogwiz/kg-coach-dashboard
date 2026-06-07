/**
 * CopilotProvider — shared Copilot conversation + drawer state.
 *
 * Lifts the per-member copilot conversation into context so BOTH the floating
 * drawer (CopilotDock) and the rest of the app (e.g. the generator logging a
 * "workout generated" event) read and write the same thread. Keyed by the
 * active member via useActiveMember.
 */

import {
  createContext,
  useContext,
  useState,
  useEffect,
  useRef,
  useCallback,
  type ReactNode,
} from "react";
import { useActiveMember } from "./activeMember";
import { useCopilot, type UseCopilotResult } from "../hooks/useCopilot";

interface CopilotDockState extends UseCopilotResult {
  isOpen: boolean;
  open: () => void;
  close: () => void;
  toggle: () => void;
  unread: number;
  /** The dashboard surface the coach is currently viewing (tab awareness). */
  context: { tab?: string };
  setContext: (c: { tab?: string }) => void;
  /** Client Inbox (trainer↔client messages) — separate from the Copilot. */
  inboxOpen: boolean;
  inboxHighlightTs: string | null;
  openInbox: (ts?: string | null) => void;
  closeInbox: () => void;
}

const CopilotContext = createContext<CopilotDockState | null>(null);

export function CopilotProvider({ children }: { children: ReactNode }) {
  const { activeMember } = useActiveMember();
  const copilot = useCopilot(activeMember?.member_id ?? null);

  const [isOpen, setIsOpen] = useState(false);
  const [unread, setUnread] = useState(0);
  const [context, setContextState] = useState<{ tab?: string }>({});

  // Keep a ref of isOpen so pushEvent can read it without re-creating callbacks.
  const openRef = useRef(isOpen);
  useEffect(() => {
    openRef.current = isOpen;
  }, [isOpen]);

  // Keep a ref of context so send() reads the latest tab without re-creating.
  const contextRef = useRef(context);
  useEffect(() => {
    contextRef.current = context;
  }, [context]);

  const setContext = useCallback((c: { tab?: string }) => setContextState(c), []);

  // Client Inbox state
  const [inboxOpen, setInboxOpen] = useState(false);
  const [inboxHighlightTs, setInboxHighlightTs] = useState<string | null>(null);
  const openInbox = useCallback((ts?: string | null) => {
    setInboxHighlightTs(ts ?? null);
    setInboxOpen(true);
  }, []);
  const closeInbox = useCallback(() => setInboxOpen(false), []);

  // Close the inbox when the member changes
  useEffect(() => {
    setInboxOpen(false);
  }, [activeMember?.member_id]);

  // Reset unread when the member changes
  useEffect(() => {
    setUnread(0);
  }, [activeMember?.member_id]);

  const open = useCallback(() => {
    setIsOpen(true);
    setUnread(0);
  }, []);
  const close = useCallback(() => setIsOpen(false), []);
  const toggle = useCallback(() => {
    setIsOpen((v) => {
      if (!v) setUnread(0);
      return !v;
    });
  }, []);

  // Wrap pushEvent to bump the unread badge when the drawer is closed.
  const basePushEvent = copilot.pushEvent;
  const pushEvent = useCallback<UseCopilotResult["pushEvent"]>(
    (text, event) => {
      basePushEvent(text, event);
      if (!openRef.current) setUnread((u) => u + 1);
    },
    [basePushEvent]
  );

  // Wrap send to inject the current tab as context (tab awareness).
  const baseSend = copilot.send;
  const send = useCallback<UseCopilotResult["send"]>(
    (text, attachments, ctx) => baseSend(text, attachments, ctx ?? contextRef.current.tab),
    [baseSend]
  );

  const value: CopilotDockState = {
    ...copilot,
    send,
    pushEvent,
    isOpen,
    open,
    close,
    toggle,
    unread,
    context,
    setContext,
    inboxOpen,
    inboxHighlightTs,
    openInbox,
    closeInbox,
  };

  return <CopilotContext.Provider value={value}>{children}</CopilotContext.Provider>;
}

export function useCopilotDock(): CopilotDockState {
  const ctx = useContext(CopilotContext);
  if (!ctx) {
    throw new Error("useCopilotDock must be used within a CopilotProvider");
  }
  return ctx;
}
