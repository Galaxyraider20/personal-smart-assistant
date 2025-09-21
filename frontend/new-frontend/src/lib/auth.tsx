import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import type { ReactNode } from "react";
import {
  type AuthError,
  type User as FirebaseUser,
  createUserWithEmailAndPassword,
  onAuthStateChanged,
  signInWithEmailAndPassword,
  signOut,
  updateProfile,
} from "firebase/auth";

import { auth } from "./firebase";

export type AuthUser = {
  uid: string;
  email: string | null;
  displayName: string | null;
  photoURL: string | null;
  emailVerified: boolean;
};

export type AuthContextValue = {
  user: AuthUser | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  signup: (name: string, email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  getIdToken: (forceRefresh?: boolean) => Promise<string>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

function mapFirebaseUser(user: FirebaseUser): AuthUser {
  return {
    uid: user.uid,
    email: user.email,
    displayName: user.displayName,
    photoURL: user.photoURL,
    emailVerified: user.emailVerified,
  };
}

function normalizeAuthError(error: unknown): Error {
  if (typeof error === "object" && error && "code" in error) {
    const { code, message } = error as AuthError;
    switch (code) {
      case "auth/invalid-email":
        return new Error("Enter a valid email address.");
      case "auth/user-not-found":
      case "auth/wrong-password":
        return new Error("Incorrect email or password.");
      case "auth/email-already-in-use":
        return new Error("An account with that email already exists.");
      case "auth/weak-password":
        return new Error("Password must be at least 6 characters.");
      default:
        return new Error(message || "Authentication failed.");
    }
  }
  return new Error("Authentication failed.");
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState(true);
  const firebaseUserRef = useRef<FirebaseUser | null>(auth.currentUser ?? null);

  useEffect(() => {
    const unsubscribe = onAuthStateChanged(auth, (firebaseUser) => {
      firebaseUserRef.current = firebaseUser;
      setUser(firebaseUser ? mapFirebaseUser(firebaseUser) : null);
      setLoading(false);
    });
    return () => unsubscribe();
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    try {
      await signInWithEmailAndPassword(auth, email.trim(), password);
    } catch (error) {
      throw normalizeAuthError(error);
    }
  }, []);

  const signup = useCallback(
    async (name: string, email: string, password: string) => {
      try {
        const { user: firebaseUser } = await createUserWithEmailAndPassword(
          auth,
          email.trim(),
          password
        );
        const displayName = name.trim();
        if (displayName) {
          await updateProfile(firebaseUser, { displayName });
          firebaseUserRef.current = auth.currentUser;
          if (firebaseUserRef.current) {
            setUser(mapFirebaseUser(firebaseUserRef.current));
          }
        }
      } catch (error) {
        throw normalizeAuthError(error);
      }
    },
    []
  );

  const logout = useCallback(async () => {
    try {
      await signOut(auth);
    } catch (error) {
      throw normalizeAuthError(error);
    }
  }, []);

  const getIdToken = useCallback(async (forceRefresh = false) => {
    const current = firebaseUserRef.current ?? auth.currentUser;
    if (!current) {
      throw new Error("You need to be signed in.");
    }
    return current.getIdToken(forceRefresh);
  }, []);

  const value = useMemo(
    () => ({
      user,
      loading,
      login,
      signup,
      logout,
      getIdToken,
    }),
    [user, loading, login, signup, logout, getIdToken]
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
