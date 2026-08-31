/**
 * Authentication state for the whole app.
 *
 * The previous version compared `admin`/`admin` inside the login component and
 * accepted any citizen ID without checking anything, so the "role" was just a
 * variable in React state. Here the role comes from a signed token the server
 * issued, and the server re-checks it on every request — the frontend cannot
 * grant itself permissions by setting a variable.
 */

import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from 'react';

import {
  ApiError,
  api,
  clearTokens,
  hasSession,
  setSessionExpiredHandler,
  setTokens,
  type Role,
  type User,
} from './api';

interface AuthState {
  user: User | null;
  loading: boolean;
  /** True while restoring a session on first paint, so we don't flash the login screen. */
  initialising: boolean;
  error: string | null;
  signIn: (email: string, password: string) => Promise<void>;
  signOut: () => void;
  clearError: () => void;
  isOfficer: boolean;
  isCitizen: boolean;
  role: Role | null;
}

const AuthContext = createContext<AuthState | null>(null);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(false);
  const [initialising, setInitialising] = useState(hasSession());
  const [error, setError] = useState<string | null>(null);

  // Restore a session from the stored token on first load.
  useEffect(() => {
    if (!hasSession()) {
      setInitialising(false);
      return;
    }
    let cancelled = false;

    api.auth
      .me()
      .then((me) => {
        if (!cancelled) setUser(me);
      })
      .catch(() => {
        clearTokens();
      })
      .finally(() => {
        if (!cancelled) setInitialising(false);
      });

    return () => {
      cancelled = true;
    };
  }, []);

  const signOut = useCallback(() => {
    clearTokens();
    setUser(null);
    setError(null);
  }, []);

  // A refresh failure anywhere in the app drops us back to the login screen.
  useEffect(() => {
    setSessionExpiredHandler(() => {
      setUser(null);
      setError('Your session has expired. Please sign in again.');
    });
    return () => setSessionExpiredHandler(null);
  }, []);

  const signIn = useCallback(async (email: string, password: string) => {
    setLoading(true);
    setError(null);
    try {
      const tokens = await api.auth.login(email.trim(), password);
      setTokens(tokens.accessToken, tokens.refreshToken);
      setUser(await api.auth.me());
    } catch (err) {
      clearTokens();
      const message =
        err instanceof ApiError
          ? err.isOffline
            ? 'Cannot reach the server. Start the backend with: uvicorn app.main:app --port 8000'
            : err.message
          : 'Something went wrong. Please try again.';
      setError(message);
      throw err;
    } finally {
      setLoading(false);
    }
  }, []);

  const value = useMemo<AuthState>(
    () => ({
      user,
      loading,
      initialising,
      error,
      signIn,
      signOut,
      clearError: () => setError(null),
      isOfficer: user?.role === 'officer' || user?.role === 'admin',
      isCitizen: user?.role === 'citizen',
      role: user?.role ?? null,
    }),
    [user, loading, initialising, error, signIn, signOut],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};

export const useAuth = (): AuthState => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used inside an <AuthProvider>');
  }
  return context;
};
