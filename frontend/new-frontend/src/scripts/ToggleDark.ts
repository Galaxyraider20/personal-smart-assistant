// toggleDark.ts (example)
export function toggleDark() {
  const root = document.documentElement;
  const next = root.classList.toggle("dark");
  localStorage.setItem("theme", next ? "dark" : "light");
}

// restore on load (optional)
(() => {
  const saved = localStorage.getItem("theme");
  if (saved === "dark") document.documentElement.classList.add("dark");
})();