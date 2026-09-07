"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { PlusCircle, UserPlus, Sparkles, AlertCircle, CheckCircle, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { useAuth } from "@/context/auth-context";

export default function OnboardingPage() {
  const router = useRouter();
  const { createHousehold, joinHousehold } = useAuth();

  const [mode, setMode] = React.useState<"create" | "join">("create");
  const [householdName, setHouseholdName] = React.useState("");
  const [timezone, setTimezone] = React.useState("UTC");
  const [inviteCode, setInviteCode] = React.useState("");

  const [error, setError] = React.useState<string | null>(null);
  const [success, setSuccess] = React.useState<string | null>(null);
  const [submitting, setSubmitting] = React.useState(false);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSuccess(null);

    if (!householdName.trim()) {
      setError("Please enter a name for your household.");
      return;
    }

    setSubmitting(true);
    try {
      const created = await createHousehold(householdName.trim(), timezone);
      setSuccess(`Household "${created.name}" created! Redirecting to dashboard...`);
      setTimeout(() => router.push("/"), 1200);
    } catch (err: any) {
      setError(err.message || "Failed to create household. Please try again.");
    } finally {
      setSubmitting(false);
    }
  };

  const handleJoin = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSuccess(null);

    if (!inviteCode.trim()) {
      setError("Please enter a valid invite code.");
      return;
    }

    setSubmitting(true);
    try {
      const result = await joinHousehold(inviteCode.trim().toUpperCase());
      if (result.status === "pending_approval") {
        setSuccess("Join request submitted! Waiting for roommate approval.");
      } else {
        setSuccess("Successfully joined household! Redirecting to dashboard...");
      }
      setTimeout(() => router.push("/"), 1200);
    } catch (err: any) {
      setError(err.message || "Failed to join household. Check your invite code.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="flex min-h-[80vh] items-center justify-center px-4">
      <Card className="w-full max-w-lg shadow-lg border">
        <CardHeader className="text-center space-y-2">
          <div className="flex items-center justify-center gap-2 text-primary font-bold text-xl">
            <Sparkles className="h-6 w-6" />
            <span>RoommateOS</span>
          </div>
          <CardTitle className="text-2xl">Household Setup</CardTitle>
          <CardDescription>
            You are one step away! Either create a new household or join your roommates with an invite code.
          </CardDescription>

          <div className="flex rounded-lg bg-muted p-1 mt-4">
            <button
              type="button"
              data-testid="tab-create"
              onClick={() => {
                setMode("create");
                setError(null);
                setSuccess(null);
              }}
              className={`flex-1 flex items-center justify-center gap-2 py-2 text-sm font-medium rounded-md transition-all ${
                mode === "create"
                  ? "bg-background text-foreground shadow-sm"
                  : "text-muted-foreground hover:text-foreground"
              }`}
            >
              <PlusCircle className="h-4 w-4" />
              <span>Create Household</span>
            </button>
            <button
              type="button"
              data-testid="tab-join"
              onClick={() => {
                setMode("join");
                setError(null);
                setSuccess(null);
              }}
              className={`flex-1 flex items-center justify-center gap-2 py-2 text-sm font-medium rounded-md transition-all ${
                mode === "join"
                  ? "bg-background text-foreground shadow-sm"
                  : "text-muted-foreground hover:text-foreground"
              }`}
            >
              <UserPlus className="h-4 w-4" />
              <span>Join with Code</span>
            </button>
          </div>
        </CardHeader>

        <CardContent>
          {error && (
            <div
              role="alert"
              data-testid="onboarding-error"
              className="mb-4 flex items-center gap-2 rounded-md bg-destructive/15 p-3 text-sm text-destructive font-medium"
            >
              <AlertCircle className="h-4 w-4 shrink-0" />
              <span>{error}</span>
            </div>
          )}

          {success && (
            <div
              role="status"
              data-testid="onboarding-success"
              className="mb-4 flex items-center gap-2 rounded-md bg-emerald-500/15 p-3 text-sm text-emerald-600 dark:text-emerald-400 font-medium"
            >
              <CheckCircle className="h-4 w-4 shrink-0" />
              <span>{success}</span>
            </div>
          )}

          {mode === "create" ? (
            <form onSubmit={handleCreate} data-testid="create-household-form" noValidate className="space-y-4">
              <div className="space-y-1.5">
                <label htmlFor="householdName" className="text-sm font-medium leading-none">
                  Household Name
                </label>
                <Input
                  id="householdName"
                  name="householdName"
                  placeholder="e.g., Maple Apartment 4B"
                  value={householdName}
                  onChange={(e) => setHouseholdName(e.target.value)}
                  required
                />
              </div>

              <div className="space-y-1.5">
                <label htmlFor="timezone" className="text-sm font-medium leading-none">
                  Timezone
                </label>
                <Input
                  id="timezone"
                  name="timezone"
                  placeholder="UTC"
                  value={timezone}
                  onChange={(e) => setTimezone(e.target.value)}
                />
              </div>

              <Button
                type="submit"
                className="w-full mt-2"
                disabled={submitting}
                data-testid="create-household-submit"
              >
                {submitting ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Creating Household...
                  </>
                ) : (
                  "Create Household"
                )}
              </Button>
            </form>
          ) : (
            <form onSubmit={handleJoin} data-testid="join-household-form" noValidate className="space-y-4">
              <div className="space-y-1.5">
                <label htmlFor="inviteCode" className="text-sm font-medium leading-none">
                  Invite Code
                </label>
                <Input
                  id="inviteCode"
                  name="inviteCode"
                  placeholder="e.g. AB12CD34"
                  value={inviteCode}
                  onChange={(e) => setInviteCode(e.target.value.toUpperCase())}
                  className="uppercase tracking-widest font-mono text-center text-lg"
                  required
                />
              </div>

              <Button
                type="submit"
                className="w-full mt-2"
                disabled={submitting}
                data-testid="join-household-submit"
              >
                {submitting ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Joining Household...
                  </>
                ) : (
                  "Join Household"
                )}
              </Button>
            </form>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
