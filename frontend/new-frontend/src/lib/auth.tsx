import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";

export type AuthUser = {
  id: string;
  name: string;
  email: string;
};

export type AuthContextValue = {
  user: AuthUser | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  signup: (name: string, email: string, password: string) => Promise<void>;
  logout: () => void;
};

const STORAGE_KEY = "calvera-auth-user";
const ACCOUNTS_KEY = "calvera-auth-accounts";

type StoredAccounts = Record<
  string,
  {
    id: string;
    name: string;
  }
>;

const AuthContext = createContext<AuthContextValue | null>(null);

function generateId(): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }
  return `user-${Math.random().toString(36).slice(2, 10)}`;
}

function sanitizeEmail(email: string) {
  return email.trim().toLowerCase();
}

function displayNameFromEmail(email: string) {
  const localPart = email.split("@")[0] ?? "";
  if (!localPart) {
    return "User";
  }
  return localPart.charAt(0).toUpperCase() + localPart.slice(1);
}

function readAccounts(): StoredAccounts {
  if (typeof window === "undefined") {
    return {};
  }
  const raw = window.localStorage.getItem(ACCOUNTS_KEY);
  if (!raw) {
    return {};
  }
  try {
    return JSON.parse(raw) as StoredAccounts;
  } catch {
    return {};
  }
}

function persistAccounts(accounts: StoredAccounts) {
  if (typeof window === "undefined") {
    return;
  }
  window.localStorage.setItem(ACCOUNTS_KEY, JSON.stringify(accounts));
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(() => {
    if (typeof window === "undefined") {
      return null;
    }
    const stored = window.localStorage.getItem(STORAGE_KEY);
    if (!stored) {
      return null;
    }
    try {
      return JSON.parse(stored) as AuthUser;
    } catch {
      return null;
    }
  });
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }
    if (user) {
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify(user));
    } else {
      window.localStorage.removeItem(STORAGE_KEY);
    }
  }, [user]);

  const simulateNetwork = useCallback(
    () =>
      new Promise<void>((resolve) => {
        setTimeout(resolve, 450);
      }),
    []
  );

  const login = useCallback(
    async (email: string, password: string) => {
      const nextEmail = sanitizeEmail(email);
      const nextPassword = password.trim();

      if (!nextEmail || !nextEmail.includes("@")) {
        throw new Error("Enter a valid email address.");
      }
      if (nextPassword.length < 4) {
        throw new Error("Password must be at least 4 characters.");
      }

      setLoading(true);
      try {
        await simulateNetwork();
        const accounts = readAccounts();
        const account = accounts[nextEmail];
        const resolved: AuthUser = account
          ? { id: account.id, name: account.name, email: nextEmail }
          : { id: generateId(), name: displayNameFromEmail(nextEmail), email: nextEmail };

        if (!account) {
          accounts[nextEmail] = { id: resolved.id, name: resolved.name };
          persistAccounts(accounts);
        }

        setUser(resolved);
      } finally {
        setLoading(false);
      }
    },
    [simulateNetwork]
  );

  const signup = useCallback(
    async (name: string, email: string, password: string) => {
      const nextName = name.trim();
      const nextEmail = sanitizeEmail(email);
      const nextPassword = password.trim();

      if (!nextName) {
        throw new Error("Tell us what to call you.");
      }
      if (!nextEmail || !nextEmail.includes("@")) {
        throw new Error("Enter a valid email address.");
      }
      if (nextPassword.length < 4) {
        throw new Error("Password must be at least 4 characters.");
      }

      setLoading(true);
      try {
        await simulateNetwork();
        const nextUser: AuthUser = {
          id: generateId(),
          name: nextName,
          email: nextEmail,
        };
        setUser(nextUser);

        const accounts = readAccounts();
        accounts[nextEmail] = { id: nextUser.id, name: nextUser.name };
        persistAccounts(accounts);
      } finally {
        setLoading(false);
      }
    },
    [simulateNetwork]
  );

  const logout = useCallback(() => {
    setUser(null);
  }, []);

  const value = useMemo(
    () => ({
      user,
      loading,
      login,
      signup,
      logout,
    }),
    [user, loading, login, signup, logout]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within AuthProvider");
  }
  return context;
}
