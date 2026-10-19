import {
  createContext,
  ReactNode,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import { ACCESS_TOKEN_KEY, REFRESH_TOKEN_KEY } from "../api/client";
import { getCurrentUser, login as loginApi, logout as logoutApi } from "../api/auth";
import type { User } from "../types";

interface AuthContextValue {
  isAuthenticated: boolean;
  user: User | null;
  login: (username: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: Readonly<{ children: ReactNode }>) {
  const [accessToken, setAccessToken] = useState<string | null>(() =>
    localStorage.getItem(ACCESS_TOKEN_KEY),
  );
  const [user, setUser] = useState<User | null>(null);

  useEffect(() => {
    if (!accessToken) {
      setUser(null);
      return;
    }
    let cancelled = false;
    getCurrentUser()
      .then((u) => {
        if (!cancelled) setUser(u);
      })
      .catch(() => {
        if (!cancelled) setUser(null);
      });
    return () => {
      cancelled = true;
    };
  }, [accessToken]);

  const login = useCallback(async (username: string, password: string) => {
    const tokens = await loginApi({ username, password });
    localStorage.setItem(ACCESS_TOKEN_KEY, tokens.access_token);
    localStorage.setItem(REFRESH_TOKEN_KEY, tokens.refresh_token);
    setAccessToken(tokens.access_token);
  }, []);

  const logout = useCallback(async () => {
    const refreshToken = localStorage.getItem(REFRESH_TOKEN_KEY);
    if (refreshToken) {
      try {
        await logoutApi(refreshToken);
      } catch {
        // Best-effort: if the server-side revocation or audit write
        // fails, we still clear local state so the user is signed
        // out from this browser.
      }
    }
    localStorage.removeItem(ACCESS_TOKEN_KEY);
    localStorage.removeItem(REFRESH_TOKEN_KEY);
    setAccessToken(null);
    setUser(null);
  }, []);

  // Memoised, so a consumer renders again only when the session it reads has changed.
  const value = useMemo(
    () => ({ isAuthenticated: !!accessToken, user, login, logout }),
    [accessToken, user, login, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider.");
  return ctx;
}
