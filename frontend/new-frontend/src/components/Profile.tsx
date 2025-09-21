import { useState } from "react";
import type { FormEvent } from "react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/lib/auth";

export default function Profile() {
  const { user, loading } = useAuth();

  return (
    <div className="min-h-screen bg-background p-6 text-foreground">
      <div className="mx-auto flex w-full max-w-4xl flex-col gap-6">
        {loading ? (
          <Card className="rounded-2xl border border-border bg-card text-card-foreground">
            <CardHeader>
              <CardTitle className="text-xl">Loading profile</CardTitle>
              <CardDescription>Checking your sign-in status...</CardDescription>
            </CardHeader>
            <CardContent>
              <p className="text-sm text-muted-foreground">
                Just a moment while we connect to Firebase.
              </p>
            </CardContent>
          </Card>
        ) : user ? (
          <ProfileDetails />
        ) : (
          <AuthGateway />
        )}
        <Card className="rounded-2xl border border-border bg-card text-card-foreground">
          <CardHeader>
            <CardTitle className="text-lg">Next steps</CardTitle>
            <CardDescription>
              The UI is wired to Firebase Auth; swap in your real backend plus Google Calendar logic when ready.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-2 text-sm text-muted-foreground">
            <p>
              Configure your Firebase project and add the keys in a <code>.env</code> file (see <code>src/lib/firebase.ts</code>).
            </p>
            <p>
              Every authenticated request should include <code>Authorization: Bearer &lt;id_token&gt;</code> so your backend can verify it with the Firebase Admin SDK.
            </p>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function ProfileDetails() {
  const { user, logout } = useAuth();
  const [signingOut, setSigningOut] = useState(false);

  if (!user) {
    return null;
  }

  const displayName = user.displayName || "Set your name";

  async function handleSignOut() {
    try {
      setSigningOut(true);
      await logout();
    } finally {
      setSigningOut(false);
    }
  }

  return (
    <Card className="rounded-2xl border border-border bg-card text-card-foreground">
      <CardHeader>
        <CardTitle className="text-2xl font-semibold">Your profile</CardTitle>
        <CardDescription>Signed in as {user.email}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="space-y-1">
          <Label className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            Display name
          </Label>
          <p className="text-lg font-medium">{displayName}</p>
        </div>
        <div className="space-y-1">
          <Label className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Email</Label>
          <p className="text-lg font-medium">{user.email}</p>
        </div>
        <div className="space-y-1">
          <Label className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Email verified</Label>
          <p className="text-sm font-medium">{user.emailVerified ? "Yes" : "No"}</p>
        </div>
        <div className="pt-2">
          <Button type="button" variant="outline" onClick={handleSignOut} disabled={signingOut}>
            {signingOut ? "Signing out..." : "Sign out"}
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}

function AuthGateway() {
  const { login, signup } = useAuth();
  const [mode, setMode] = useState<"login" | "signup">("login");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      if (mode === "login") {
        await login(email, password);
      } else {
        await signup(name, email, password);
      }
    } catch (err) {
      if (err instanceof Error) {
        setError(err.message);
      } else {
        setError("Something went wrong. Please try again.");
      }
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Card className="rounded-2xl border border-border bg-card text-card-foreground">
      <CardHeader>
        <CardTitle className="text-2xl font-semibold">
          {mode === "login" ? "Welcome back" : "Create an account"}
        </CardTitle>
        <CardDescription>
          {mode === "login"
            ? "Sign in with your Firebase account to sync chat and calendar data."
            : "Sign up to create a Firebase identity for your Calvera workspace."}
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        <form className="space-y-4" onSubmit={handleSubmit}>
          {mode === "signup" && (
            <div className="space-y-2">
              <Label htmlFor="profile-name">Name</Label>
              <Input
                id="profile-name"
                value={name}
                onChange={(event) => setName(event.target.value)}
                placeholder="Alex Student"
                autoComplete="name"
                disabled={submitting}
              />
            </div>
          )}
          <div className="space-y-2">
            <Label htmlFor="profile-email">Email</Label>
            <Input
              id="profile-email"
              type="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              placeholder="you@example.com"
              autoComplete={mode === "login" ? "email" : "new-email"}
              disabled={submitting}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="profile-password">Password</Label>
            <Input
              id="profile-password"
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              placeholder="********"
              autoComplete={mode === "login" ? "current-password" : "new-password"}
              disabled={submitting}
            />
          </div>
          {error && <p className="text-sm text-destructive">{error}</p>}
          <Button type="submit" className="w-full" disabled={submitting}>
            {submitting ? "Please wait..." : mode === "login" ? "Sign in" : "Create account"}
          </Button>
        </form>
        <div className="text-center text-sm text-muted-foreground">
          {mode === "login" ? (
            <>
              Need an account?{" "}
              <button
                type="button"
                className="font-medium text-primary hover:underline"
                onClick={() => {
                  setMode("signup");
                  setError(null);
                }}
              >
                Sign up
              </button>
            </>
          ) : (
            <>
              Already have an account?{" "}
              <button
                type="button"
                className="font-medium text-primary hover:underline"
                onClick={() => {
                  setMode("login");
                  setError(null);
                }}
              >
                Sign in
              </button>
            </>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
