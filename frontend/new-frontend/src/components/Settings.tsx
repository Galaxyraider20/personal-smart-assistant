import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Button } from "@/components/ui/button";
import { initTheme, setTheme } from "@/lib/theme";
import { CheckCircle, XCircle, RefreshCcw } from "lucide-react";

const backendBase = (import.meta.env.VITE_BACKEND_URL as string | undefined) ?? "http://localhost:8000";
const cleanBackendBase = backendBase.replace(/\/$/, "");
const googleAuthUrl = `${cleanBackendBase}/auth/google/login`;
const statusUrl = `${cleanBackendBase}/auth/status`;

type AuthStatus = "unknown" | "ok" | "error";

export default function Settings() {
  const [isDark, setIsDark] = useState(false);
  const [authStatus, setAuthStatus] = useState<AuthStatus>("unknown");
  const [authMessage, setAuthMessage] = useState<string>("Check connection status");
  const [isChecking, setIsChecking] = useState(false);

  useEffect(() => {
    initTheme();
    const darkNow = document.documentElement.classList.contains("dark");
    setIsDark(darkNow);
  }, []);

  function toggleDark(checked: boolean) {
    setIsDark(checked);
    setTheme(checked ? "dark" : "light");
  }

  function handleGoogleConnect() {
    window.open(googleAuthUrl, "_blank", "noopener,noreferrer");
  }

  async function handleStatusCheck() {
    setIsChecking(true);
    try {
      const response = await fetch(statusUrl, { credentials: "include" });
      if (!response.ok) {
        throw new Error(`Status request failed (${response.status})`);
      }
      const data = await response.json() as { authenticated?: boolean; message?: string };
      if (data.authenticated) {
        setAuthStatus("ok");
        setAuthMessage(data.message ?? "Connected to Google Calendar");
      } else {
        setAuthStatus("error");
        setAuthMessage(data.message ?? "Calendar not authenticated");
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : "Unable to check status.";
      setAuthStatus("error");
      setAuthMessage(message);
    } finally {
      setIsChecking(false);
    }
  }

  return (
    <div className="min-h-screen bg-background text-foreground p-6">
      <div className="mx-auto max-w-3xl space-y-6">
        <h1 className="text-2xl font-semibold">Settings</h1>

        <Card className="rounded-2xl">
          <CardHeader>
            <CardTitle>Appearance</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex items-center justify-between gap-4">
              <div>
                <Label htmlFor="dark-mode">Dark mode</Label>
                <p className="text-sm text-muted-foreground">
                  Switch between light and dark theme.
                </p>
              </div>
              <Switch
                id="dark-mode"
                checked={isDark}
                onCheckedChange={toggleDark}
              />
            </div>
          </CardContent>
        </Card>

        <Card className="rounded-2xl">
          <CardHeader>
            <CardTitle>Connected Accounts</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <p className="text-sm text-muted-foreground">
                  Link your Google account to sync calendar events and preferences.
                </p>
              </div>
              <div className="flex gap-2">
                <Button type="button" onClick={handleGoogleConnect}>
                  Connect Google Account
                </Button>
                <Button type="button" variant="outline" onClick={() => void handleStatusCheck()} disabled={isChecking}>
                  {isChecking ? (
                    <RefreshCcw className="h-4 w-4 animate-spin" />
                  ) : (
                    <span>Status</span>
                  )}
                </Button>
              </div>
            </div>
            <div className="flex items-center gap-2 text-sm">
              {authStatus === "ok" && <CheckCircle className="h-4 w-4 text-emerald-500" />}
              {authStatus === "error" && <XCircle className="h-4 w-4 text-destructive" />}
              {authStatus === "unknown" && <span className="h-4 w-4 rounded-full border border-muted" />}
              <span className={authStatus === "error" ? "text-destructive" : "text-muted-foreground"}>
                {authMessage}
              </span>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
