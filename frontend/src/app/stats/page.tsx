"use client";

import * as React from "react";
import { Flame, Trophy, Award, CheckCircle, ShieldCheck, RefreshCw, AlertCircle, Sparkles, Heart } from "lucide-react";
import { useAuth } from "@/context/auth-context";
import { api } from "@/lib/api";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

interface MilestoneBadge {
  badge_key: string;
  name: string;
  description: string;
  icon: string;
  is_unlocked: boolean;
  unlocked_at: string | null;
}

interface PersonalStats {
  display_name: string;
  current_streak: number;
  longest_streak: number;
  on_time_completions: number;
  late_completions: number;
  total_completed: number;
  completion_rate: number;
  milestones: MilestoneBadge[];
}

interface HouseholdMemberStat {
  user_id: number;
  display_name: string;
  total_completed: number;
  on_time_completions: number;
  current_streak: number;
  completion_rate: number;
}

interface HouseholdStats {
  household_name: string;
  total_completed: number;
  completion_rate: number;
  members: HouseholdMemberStat[];
}

export default function StatsPage() {
  const { user } = useAuth();

  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);

  const [personalStats, setPersonalStats] = React.useState<PersonalStats | null>(null);
  const [householdStats, setHouseholdStats] = React.useState<HouseholdStats | null>(null);

  const loadData = React.useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [pStats, hStats] = await Promise.all([
        api.stats.personal().catch(() => null),
        api.stats.household().catch(() => null),
      ]);
      setPersonalStats(pStats);
      setHouseholdStats(hStats);
    } catch (err: any) {
      setError(err.message || "Failed to load stats.");
    } finally {
      setLoading(false);
    }
  }, []);

  React.useEffect(() => {
    loadData();
  }, [loadData]);

  return (
    <div className="space-y-8" data-testid="stats-page">
      {/* Top Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Personal & Household Streaks</h1>
          <p className="text-sm text-muted-foreground">
            Celebrate habit consistency, unlock personal milestones, and view shared household health.
          </p>
        </div>

        <Button
          variant="outline"
          size="sm"
          onClick={() => loadData()}
          className="gap-1.5"
          data-testid="refresh-stats-btn"
        >
          <RefreshCw className="h-4 w-4" />
          <span>Refresh</span>
        </Button>
      </div>

      {error && (
        <div className="p-4 rounded-lg bg-destructive/10 text-destructive flex items-center gap-2 text-sm" data-testid="stats-error">
          <AlertCircle className="h-5 w-5 shrink-0" />
          <span>{error}</span>
          <Button variant="outline" size="sm" onClick={() => loadData()} className="ml-auto">
            Retry
          </Button>
        </div>
      )}

      {loading ? (
        <div className="flex items-center justify-center min-h-[350px]" data-testid="stats-loading">
          <RefreshCw className="h-8 w-8 animate-spin text-primary" />
        </div>
      ) : (
        <>
          {/* Personal Streak & Metrics */}
          <div className="space-y-4" data-testid="personal-stats-section">
            <h2 className="text-lg font-semibold tracking-tight flex items-center gap-2">
              <Flame className="h-5 w-5 text-amber-500" />
              <span>Your Habit Streaks</span>
            </h2>

            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
              <Card data-testid="stat-current-streak" className="border shadow-sm">
                <CardHeader className="p-4 pb-1">
                  <CardTitle className="text-xs text-muted-foreground font-medium flex items-center gap-1.5">
                    <Flame className="h-4 w-4 text-amber-500" />
                    Current Streak
                  </CardTitle>
                </CardHeader>
                <CardContent className="p-4 pt-1">
                  <div className="text-3xl font-extrabold text-foreground">
                    {personalStats?.current_streak ?? 0}
                  </div>
                  <p className="text-xs text-muted-foreground mt-0.5">on-time chores in a row</p>
                </CardContent>
              </Card>

              <Card data-testid="stat-longest-streak" className="border shadow-sm">
                <CardHeader className="p-4 pb-1">
                  <CardTitle className="text-xs text-muted-foreground font-medium flex items-center gap-1.5">
                    <Trophy className="h-4 w-4 text-purple-500" />
                    Longest Streak
                  </CardTitle>
                </CardHeader>
                <CardContent className="p-4 pt-1">
                  <div className="text-3xl font-extrabold text-foreground">
                    {personalStats?.longest_streak ?? 0}
                  </div>
                  <p className="text-xs text-muted-foreground mt-0.5">personal record</p>
                </CardContent>
              </Card>

              <Card data-testid="stat-total-completed" className="border shadow-sm">
                <CardHeader className="p-4 pb-1">
                  <CardTitle className="text-xs text-muted-foreground font-medium flex items-center gap-1.5">
                    <CheckCircle className="h-4 w-4 text-emerald-500" />
                    Total Completed
                  </CardTitle>
                </CardHeader>
                <CardContent className="p-4 pt-1">
                  <div className="text-3xl font-extrabold text-emerald-600 dark:text-emerald-400">
                    {personalStats?.total_completed ?? 0}
                  </div>
                  <p className="text-xs text-muted-foreground mt-0.5">lifetime completed</p>
                </CardContent>
              </Card>

              <Card data-testid="stat-completion-rate" className="border shadow-sm">
                <CardHeader className="p-4 pb-1">
                  <CardTitle className="text-xs text-muted-foreground font-medium flex items-center gap-1.5">
                    <ShieldCheck className="h-4 w-4 text-blue-500" />
                    Reliability Rate
                  </CardTitle>
                </CardHeader>
                <CardContent className="p-4 pt-1">
                  <div className="text-3xl font-extrabold text-blue-600 dark:text-blue-400">
                    {Math.round(personalStats?.completion_rate ?? 100)}%
                  </div>
                  <p className="text-xs text-muted-foreground mt-0.5">on-time consistency</p>
                </CardContent>
              </Card>
            </div>
          </div>

          {/* Milestone Badges Gallery */}
          <div className="space-y-4" data-testid="milestones-gallery-section">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-lg font-semibold tracking-tight flex items-center gap-2">
                  <Award className="h-5 w-5 text-purple-500" />
                  <span>Milestone Badges</span>
                </h2>
                <p className="text-xs text-muted-foreground">
                  Badges unlocked automatically as you complete chores on time.
                </p>
              </div>
              <Badge variant="secondary" className="text-xs" data-testid="milestones-unlocked-badge">
                {personalStats?.milestones?.filter((m) => m.is_unlocked).length || 0} /{" "}
                {personalStats?.milestones?.length || 0} Unlocked
              </Badge>
            </div>

            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3" data-testid="milestones-grid">
              {(personalStats?.milestones || []).map((m) => (
                <Card
                  key={m.badge_key}
                  data-testid={`milestone-card-${m.badge_key}`}
                  className={`border transition-all ${
                    m.is_unlocked
                      ? "bg-primary/5 border-primary/30 shadow-sm"
                      : "opacity-60 bg-muted/20 border-dashed"
                  }`}
                >
                  <CardHeader className="p-4 pb-2">
                    <div className="flex items-start justify-between gap-2">
                      <div className="flex items-center gap-2.5">
                        <span className="text-2xl">{m.icon || "🏅"}</span>
                        <div>
                          <CardTitle className="text-sm font-bold">{m.name}</CardTitle>
                          <CardDescription className="text-xs">{m.description}</CardDescription>
                        </div>
                      </div>
                    </div>
                  </CardHeader>
                  <CardContent className="p-4 pt-1 text-xs">
                    {m.is_unlocked ? (
                      <span className="text-emerald-600 dark:text-emerald-400 font-semibold flex items-center gap-1">
                        <CheckCircle className="h-3.5 w-3.5" />
                        Unlocked {m.unlocked_at ? new Date(m.unlocked_at).toLocaleDateString() : "Active"}
                      </span>
                    ) : (
                      <span className="text-muted-foreground italic">In progress</span>
                    )}
                  </CardContent>
                </Card>
              ))}
            </div>
          </div>

          {/* Non-Competitive Household Roster */}
          <div className="space-y-4" data-testid="household-stats-section">
            <div className="p-4 rounded-lg border bg-muted/10 space-y-1">
              <div className="flex items-center gap-2 text-xs font-semibold text-primary uppercase tracking-wide">
                <Heart className="h-4 w-4 text-rose-500" />
                <span>Non-Competitive Household Principle</span>
              </div>
              <p className="text-xs text-muted-foreground">
                Chores are about collaborative partnership, not a contest. Roommates are listed alphabetically without rankings or competitive placement.
              </p>
            </div>

            <div className="flex items-center justify-between">
              <h2 className="text-lg font-semibold tracking-tight">
                {householdStats?.household_name || "Household"} Consistency
              </h2>
              <Badge variant="outline">
                {householdStats?.completion_rate ? Math.round(householdStats.completion_rate) : 100}% overall reliability
              </Badge>
            </div>

            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4" data-testid="household-members-roster">
              {(householdStats?.members || []).map((m) => (
                <Card key={m.user_id} data-testid={`member-stat-card-${m.user_id}`} className="shadow-sm">
                  <CardHeader className="p-4 pb-2">
                    <CardTitle className="text-sm font-semibold">{m.display_name}</CardTitle>
                    <CardDescription className="text-xs">
                      Active Chore Contributor
                    </CardDescription>
                  </CardHeader>
                  <CardContent className="p-4 pt-1 space-y-1 text-xs text-muted-foreground border-t">
                    <div className="flex justify-between">
                      <span>Completed:</span>
                      <span className="font-semibold text-foreground">{m.total_completed} chores</span>
                    </div>
                    <div className="flex justify-between">
                      <span>On-Time:</span>
                      <span className="font-semibold text-foreground">{m.on_time_completions}</span>
                    </div>
                    <div className="flex justify-between">
                      <span>Current Streak:</span>
                      <span className="font-semibold text-amber-600 dark:text-amber-400">
                        {m.current_streak} 🔥
                      </span>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          </div>
        </>
      )}
    </div>
  );
}
