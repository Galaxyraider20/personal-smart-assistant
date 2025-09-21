import { auth } from "./firebase";

const STORAGE_KEY = "calvera-anon-user-id";

export function getActiveUserId(): string {
  const current = auth.currentUser;
  if (current?.uid) {
    return current.uid;
  }

  if (typeof window === "undefined") {
    return "anonymous";
  }

  try {
    const stored = window.localStorage.getItem(STORAGE_KEY);
    if (stored) {
      return stored;
    }

    const randomId = typeof crypto !== "undefined" && typeof crypto.randomUUID === "function"
      ? crypto.randomUUID()
      : Math.random().toString(36).slice(2, 10);

    const anonId = `anon_${randomId}`;
    window.localStorage.setItem(STORAGE_KEY, anonId);
    return anonId;
  } catch {
    return "anonymous";
  }
}
