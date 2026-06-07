/**
 * App — root component wiring auth + active-member providers together.
 *
 * Routing logic:
 *  - isLoading (validating stored token) → spinner
 *  - !coach (unauthenticated) → LoginScreen
 *  - coach (authenticated) → Dashboard
 */

import { AuthProvider, useAuth } from "./state/auth";
import { ActiveMemberProvider } from "./state/activeMember";
import { LoginScreen } from "./components/auth/LoginScreen";
import { Dashboard } from "./components/layout/Dashboard";

function AppInner() {
  const { coach, isLoading } = useAuth();

  if (isLoading) {
    return (
      <div className="min-h-screen bg-slate-50 flex items-center justify-center">
        <div className="text-slate-400 text-sm">Loading…</div>
      </div>
    );
  }

  if (!coach) {
    return <LoginScreen />;
  }

  return (
    <ActiveMemberProvider>
      <Dashboard />
    </ActiveMemberProvider>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <AppInner />
    </AuthProvider>
  );
}
