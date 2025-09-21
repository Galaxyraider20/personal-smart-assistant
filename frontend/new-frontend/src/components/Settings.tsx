import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { initTheme, setTheme } from "@/lib/theme";

export default function Settings() {
  const [isDark, setIsDark] = useState(false);

  useEffect(() => {
    // initialize once when page loads
    initTheme();
    // read the current class on <html>
    const darkNow = document.documentElement.classList.contains("dark");
    setIsDark(darkNow);
  }, []);

  function toggleDark(checked: boolean) {
    setIsDark(checked);
    setTheme(checked ? "dark" : "light");
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
      </div>
    </div>
  );
}
