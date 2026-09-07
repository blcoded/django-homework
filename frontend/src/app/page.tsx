"use client";

import * as React from "react";
import Link from "next/link";
import { Flame, PlusCircle, ArrowRight, RefreshCw, AlertCircle } from "lucide-react";
import { useAuth } from "@/context/auth-context";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { MyChores, ChoreOccurrenceItem } from "@/components/dashboard/my-chores";
import { HouseholdOverview, HouseholdSummary } from "@/components/dashboard/household-overview";
import { ActivityTicker, ActivityItem } from "@/components/dashboard/activity-ticker";

export default function DashboardPage() {
  const { user, isAuthenticated, isLoading: authLoading } = useAuth();

  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);
  const [completingId, setCompletingId] = React.useState<number | null>(null);

  const [activeChores, setActiveChores] = React.useState<ChoreOccurrenceItem[]>([]);
  const [nextUpChore, setNextUpChore] = React.useState<ChoreOccurrenceItem | null>(null);
  const [householdSummary, setHouseholdSummary] = React.useState<HouseholdSummary>({
    household_name: "Shared Household",
    total_active: 0,
    total_completed: 0,
    unassigned_count: 0,
    completion_rate: 100,
  });
  const [recentActivity, setRecentActivity] = React.useState<ActivityItem[]>([]);
  const [streakData, setStreakData] = React.useState<{ current_streak: number; longest_streak: number }>({
    current_streak: 0,
    longest_streak: 0,
  });

  const loadDashboardData = React.useCallback(async () => {
    if (!isAuthenticated) return;
    setLoading(true);
    setError(null);

    try {
      // 1. Fetch chores occurrences for user
      const occurrencesPromise = api.chores.occurrences().catch(() => []);
      // 2. Fetch household stats
      const householdStatsPromise = api.stats.household().catch(() => null);
      // 3. Fetch personal stats
      const personalStatsPromise = api.stats.personal().catch(() => null);
      // 4. Fetch recent activity
      const activityPromise = api.activity.list().catch(() => []);

      const [occurrences, hStats, pStats, activities] = await Promise.all([
        occurrencesPromise,
        householdStatsPromise,
        personalStatsPromise,
        activityPromise,
      ]);

      // Filter user's active chores
      if (Array.isArray(occurrences)) {
        const userOccurrences = occurrences.filter(
          (occ: any) =>
            occ.assigned_to === user?.id ||
            occ.assigned_member?.user?.id === user?.id ||
            occ.assigned_member?.user === user?.id
        );

        const currentActive = userOccurrences.filter(
          (occ: any) => occ.status === "active" || occ.status === "upcoming"
        );
        setActiveChores(currentActive);

        const nextUp = userOccurrences.find((occ: any) => occ.status === "upcoming" && occ.scheduled_start);
        setNextUpChore(nextUp || null);
      }

      // Populate household stats
      if (hStats) {
        setHouseholdSummary({
          household_name: hStats.household_name || "Shared Household",
          total_active: hStats.total_active_chores ?? hStats.total_chores ?? 0,
          total_completed: hStats.completed_count ?? hStats.total_completed ?? 0,
          unassigned_count: hStats.unassigned_count ?? 0,
          completion_rate: hStats.completion_rate ?? 100,
          members_count: hStats.member_count,
        });
      }

      // Populate personal streak
      if (pStats) {
        setStreakData({
          current_streak: pStats.current_streak ?? 0,
          longest_streak: pStats.longest_streak ?? 0,
        });
      }

      // Populate activities
      if (Array.isArray(activities)) {
        const formattedActivities: ActivityItem[] = activities.slice(0, 5).map((a: any) => ({
          id: a.id,
          event_type: a.event_type,
          description: a.description,
          user_name: a.user_display_name || a.user?.display_name || a.user?.email,
          created_at: a.created_at,
        }));
        setRecentActivity(formattedActivities);
      }
    } catch (err: any) {
      setError(err.message || "Failed to load dashboard data");
    } finally {
      setLoading(false);
    }
  }, [isAuthenticated, user?.id]);

  React.useEffect(() => {
    if (!authLoading) {
      if (isAuthenticated) {
        loadDashboardData();
      } else {
        setLoading(false);
      }
    }
  }, [authLoading, isAuthenticated, loadDashboardData]);

  const handleCompleteChore = async (occurrenceId: number) => {
    try {
      setCompletingId(occurrenceId);
      await api.chores.completeOccurrence(occurrenceId);
      // Refresh state
      await loadDashboardData();
    } catch (err: any) {
      alert(err.message || "Failed to mark chore as complete");
    } finally {
      setCompletingId(null);
    }
  };

  if (authLoading || (loading && isAuthenticated)) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[400px] space-y-4" data-testid="dashboard-loading">
        <RefreshCw className="h-8 w-8 animate-spin text-primary" />
        <p className="text-sm text-muted-foreground font-medium">Syncing household chore board...</p>
      </div>
    );
  }

  // Guest view
  if (!isAuthenticated) {
    return (
      <div className="max-w-3xl mx-auto py-12 px-4 text-center space-y-6" data-testid="guest-welcome">
        <div className="inline-flex items-center justify-center p-3 rounded-full bg-primary/10 text-primary mb-2">
          <Flame className="h-8 w-8" />
        </div>
        <h1 className="text-3xl font-extrabold tracking-tight sm:text-4xl">
          Equitable, Stress-Free Shared Chores
        </h1>
        <p className="text-muted-foreground max-w-xl mx-auto text-base">
          Rotate responsibilities fairly with automated load-balancing, dispute-free photo proofs, streaks, and anonymous chore proposals.
        </p>
        <div className="flex flex-wrap items-center justify-center gap-4 pt-4">
          <Button asChild size="lg" data-testid="guest-login-btn">
            <Link href="/login">Sign In</Link>
          </Button>
          <Button asChild variant="outline" size="lg" data-testid="guest-register-btn">
            <Link href="/register">Create an Account</Link>
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-8" data-testid="dashboard-page">
      {/* Welcome & Action Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight" data-testid="welcome-heading">
            Welcome back, {user?.display_name || user?.email?.split("@")[0]}!
          </h1>
          <p className="text-sm text-muted-foreground">
            Here is your chore rundown and household summary today.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={() => loadDashboardData()} className="gap-1.5">
            <RefreshCw className="h-4 w-4" />
            <span>Refresh</span>
          </Button>
          <Button asChild size="sm" className="gap-1.5">
            <Link href="/chores">
              <PlusCircle className="h-4 w-4" />
              <span>Chore Catalog</span>
            </Link>
          </Button>
        </div>
      </div>

      {error && (
        <div className="p-4 rounded-lg bg-destructive/10 text-destructive flex items-center gap-3 text-sm" data-testid="dashboard-error">
          <AlertCircle className="h-5 w-5 shrink-0" />
          <span>{error}</span>
          <Button variant="outline" size="sm" onClick={() => loadDashboardData()} className="ml-auto">
            Retry
          </Button>
        </div>
      )}

      {/* Main Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Left 2 Columns: Household Overview + My Responsibilities */}
        <div className="lg:col-span-2 space-y-8">
          <HouseholdOverview summary={householdSummary} />

          <MyChores
            activeChores={activeChores}
            nextUpChore={nextUpChore}
            onComplete={handleCompleteChore}
            completingId={completingId}
          />
        </div>

        {/* Right 1 Column: Streak & Milestone Widget + Live Activity */}
        <div className="space-y-6">
          <Card data-testid="streak-widget-card" className="border shadow-sm">
            <CardHeader className="pb-2">
              <div className="flex items-center justify-between">
                <CardTitle className="text-base font-semibold">Your Habit Streak</CardTitle>
                <Flame className="h-5 w-5 text-amber-500 animate-pulse" />
              </div>
              <CardDescription className="text-xs">
                Keep completing chores on time to earn milestone badges.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-3 pt-2">
              <div className="flex items-baseline gap-2">
                <span className="text-4xl font-extrabold text-foreground" data-testid="streak-count">
                  {streakData.current_streak}
                </span>
                <span className="text-sm font-medium text-muted-foreground">
                  consecutive completions
                </span>
              </div>
              <div className="text-xs text-muted-foreground pt-1 border-t flex justify-between items-center">
                <span>Personal Best: {streakData.longest_streak} cycles</span>
                <Link href="/stats" className="text-primary hover:underline font-medium flex items-center gap-0.5">
                  View Badges
                  <ArrowRight className="h-3 w-3" />
                </Link>
              </div>
            </CardContent>
          </Card>

          <ActivityTicker events={recentActivity} />
        </div>
      </div>
    </div>
  );
}
