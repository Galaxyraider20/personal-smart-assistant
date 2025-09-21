// src/App.tsx
import { useEffect, useMemo, useState } from "react";
import CalendarPage from "./components/Calendar";
import DefaultSidebar from "./components/Navbar";
import Profile from "./components/Profile";
import Chatbot from "./components/chatbot";
import Home from "./components/home"; // <- the calendar-chat page you added
import Settings from "./components/Settings"; // <- add
import { initTheme } from "./lib/theme";

function useHashRoute() {
  const [hash, setHash] = useState<string>(() => window.location.hash || "#home");
  useEffect(() => {
    const onHashChange = () => setHash(window.location.hash || "#home");
    window.addEventListener("hashchange", onHashChange);
    return () => window.removeEventListener("hashchange", onHashChange);
  }, []);
  return useMemo(() => (hash.startsWith("#") ? hash.slice(1) : hash), [hash]);
}

function MainView({ route }: { route: string }) {
  switch (route) {
    case "home":
      return <Home />; // calendar + chat experience
    case "chat":
      return (
        <div className="h-full overflow-hidden">
          <Chatbot />
        </div>
      );
    case "calendar":
      return (
        <CalendarPage
          // optional: pass real events; otherwise it uses samples
          // events={[
          //   { id: "e1", title: "Standup", start: new Date(), where: "Meet" },
          //   { id: "e2", title: "Review", start: "2025-09-23T13:00:00" },
          // ]}
          weekStartsOn={0} // 0=Sun, 1=Mon
        />
      );
    case "settings": // <- add
      return <Settings />;
    case "profile":
      return <Profile />;
    default:
      return <div className="p-6">Welcome! Pick an item from the sidebar.</div>;
  }
}

export default function App() {
  const route = useHashRoute();
  // make sure the theme is applied app-wide on mount
  useEffect(() => {
    initTheme();
  }, []);
  return (
    <div className="h-screen w-screen bg-background text-foreground flex">
      {/* Sidebar */}
      <div className="shrink-0">
        <DefaultSidebar />
      </div>

      {/* Main content -- keep min-h-0 so inner scroll areas can size correctly */}
      <main className="flex-1 min-h-0 p-0 bg-background text-foreground">
        <div className="h-full flex flex-col">
          <MainView route={route} />
        </div>
      </main>
    </div>
  );
}
