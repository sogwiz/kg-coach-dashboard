/**
 * Auth state — React context + provider for coach authentication.
 *
 * Persists the token in localStorage so the session survives page reloads.
 * Unauthenticated users always see the LoginScreen; authenticated users see
 * the Dashboard.
 */

import {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
  type ReactNode,
} from "react";
import {
  login as apiLogin,
  fetchMe,
  setToken,
  clearToken,
  getToken,
  type CoachProfile,
} from "../lib/api";

// ---------------------------------------------------------------------------
// Context shape
// ---------------------------------------------------------------------------

interface AuthState {
  coach: CoachProfile | null;
  isLoading: boolean;
  error: string | null;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthState | null>(null);

// ---------------------------------------------------------------------------
// Provider
// ---------------------------------------------------------------------------

export function AuthProvider({ children }: { children: ReactNode }) {
  const [coach, setCoach] = useState<CoachProfile | null>(null);
  const [isLoading, setIsLoading] = useState(true); // check stored token on mount
  const [error, setError] = useState<string | null>(null);

  // On mount: if a token exists in localStorage, validate it with /api/auth/me
  useEffect(() => {
    const token = getToken();
    if (!token) {
      setIsLoading(false);
      return;
    }
    fetchMe()
      .then((profile) => setCoach(profile))
      .catch(() => {
        // Stale or invalid token — clear it
        clearToken();
      })
      .finally(() => setIsLoading(false));
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    setError(null);
    setIsLoading(true);
    try {
      const resp = await apiLogin(email, password);
      setToken(resp.token);
      setCoach(resp.coach);
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Login failed";
      setError(msg);
    } finally {
      setIsLoading(false);
    }
  }, []);

  const logout = useCallback(() => {
    clearToken();
    setCoach(null);
  }, []);

  return (
    <AuthContext.Provider value={{ coach, isLoading, error, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth must be used inside <AuthProvider>");
  }
  return ctx;
}
