/**
 * Active-member context — shared state that drives every surface.
 *
 * Switching a member re-keys all hooks (injury, generator, copilot) to the
 * new member_id.  Later phases (9, 10) read the same context so the member
 * switcher is the single source of truth for "who is the coach looking at."
 */

import {
  createContext,
  useContext,
  useState,
  useCallback,
  type ReactNode,
} from "react";
import type { MemberSummary } from "../lib/api";

// ---------------------------------------------------------------------------
// Context shape
// ---------------------------------------------------------------------------

interface ActiveMemberState {
  members: MemberSummary[];
  activeMember: MemberSummary | null;
  setMembers: (members: MemberSummary[]) => void;
  switchMember: (memberId: string) => void;
}

const ActiveMemberContext = createContext<ActiveMemberState | null>(null);

// ---------------------------------------------------------------------------
// Provider
// ---------------------------------------------------------------------------

export function ActiveMemberProvider({ children }: { children: ReactNode }) {
  const [members, setMembersState] = useState<MemberSummary[]>([]);
  const [activeMember, setActiveMember] = useState<MemberSummary | null>(null);

  const setMembers = useCallback((list: MemberSummary[]) => {
    setMembersState(list);
    // Auto-select first member if none selected
    if (list.length > 0 && activeMember === null) {
      setActiveMember(list[0]);
    }
  }, [activeMember]);

  const switchMember = useCallback(
    (memberId: string) => {
      const found = members.find((m) => m.member_id === memberId);
      if (found) setActiveMember(found);
    },
    [members]
  );

  return (
    <ActiveMemberContext.Provider
      value={{ members, activeMember, setMembers, switchMember }}
    >
      {children}
    </ActiveMemberContext.Provider>
  );
}

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

export function useActiveMember(): ActiveMemberState {
  const ctx = useContext(ActiveMemberContext);
  if (!ctx) {
    throw new Error("useActiveMember must be used inside <ActiveMemberProvider>");
  }
  return ctx;
}
