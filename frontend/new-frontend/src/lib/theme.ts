// Simple, framework-agnostic theme helpers
const STORAGE_KEY = "theme"; // "dark" | "light"

export type ThemeMode = "dark" | "light";

export function getStoredTheme(): ThemeMode | null {
  const v = localStorage.getItem(STORAGE_KEY);
  return v === "dark" || v === "light" ? v : null;
}

export function getSystemPref(): ThemeMode {
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

export function applyTheme(mode: ThemeMode) {
  const root = document.documentElement;
  root.classList.toggle("dark", mode === "dark");
}

export function setTheme(mode: ThemeMode) {
  applyTheme(mode);
  localStorage.setItem(STORAGE_KEY, mode);
}

// Call once on app start (or inside Settings useEffect)
export function initTheme() {
  const stored = getStoredTheme();
  applyTheme(stored ?? getSystemPref());
}
