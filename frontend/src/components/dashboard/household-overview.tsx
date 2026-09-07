"use client";

import * as React from "react";
import { CheckCircle, AlertCircle, Calendar, Sparkles } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

export interface HouseholdSummary {
  household_name?: string;
  total_active: number;
  total_completed: number;
  unassigned_count: number;
  completion_rate: number;
  members_count?: number;
}

interface HouseholdOverviewProps {
  summary: HouseholdSummary;
}

export function HouseholdOverview({ summary }: HouseholdOverviewProps) {
  return (
    <div className="space-y-4" data-testid="household-overview-section">
      <div>
        <h2 className="text-xl font-bold tracking-tight">Household Pulse</h2>
        <p className="text-sm text-muted-foreground">
          Real-time health of shared duties in {summary.household_name || "your home"}.
        </p>
      </div>

      {summary.unassigned_count > 0 && (
        <div
          data-testid="unassigned-alert-banner"
          className="flex items-center gap-3 p-3 rounded-lg border border-amber-300 bg-amber-50 text-amber-900 dark:bg-amber-950/40 dark:border-amber-800 dark:text-amber-200 text-sm"
        >
          <AlertCircle className="h-5 w-5 shrink-0 text-amber-600 dark:text-amber-400" />
          <div className="flex-1">
            <span className="font-semibold">
              {summary.unassigned_count} unassigned chore{summary.unassigned_count > 1 ? "s" : ""}
            </span>{" "}
            need attention due to member absences or rotation pauses.
          </div>
          <Badge variant="outline" className="border-amber-400 text-amber-800 dark:text-amber-300">
            Action Needed
          </Badge>
        </div>
      )}

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Card data-testid="stat-card-active">
          <CardHeader className="p-4 pb-1">
            <CardTitle className="text-xs font-medium text-muted-foreground flex items-center gap-1.5">
              <Calendar className="h-3.5 w-3.5" />
              Active Chores
            </CardTitle>
          </CardHeader>
          <CardContent className="p-4 pt-1">
            <div className="text-2xl font-bold">{summary.total_active}</div>
            <p className="text-xs text-muted-foreground">in rotation</p>
          </CardContent>
        </Card>

        <Card data-testid="stat-card-completed">
          <CardHeader className="p-4 pb-1">
            <CardTitle className="text-xs font-medium text-muted-foreground flex items-center gap-1.5">
              <CheckCircle className="h-3.5 w-3.5 text-emerald-500" />
              Completed
            </CardTitle>
          </CardHeader>
          <CardContent className="p-4 pt-1">
            <div className="text-2xl font-bold text-emerald-600 dark:text-emerald-400">
              {summary.total_completed}
            </div>
            <p className="text-xs text-muted-foreground">logged cycles</p>
          </CardContent>
        </Card>

        <Card data-testid="stat-card-rate">
          <CardHeader className="p-4 pb-1">
            <CardTitle className="text-xs font-medium text-muted-foreground flex items-center gap-1.5">
              <Sparkles className="h-3.5 w-3.5 text-blue-500" />
              Completion Rate
            </CardTitle>
          </CardHeader>
          <CardContent className="p-4 pt-1">
            <div className="text-2xl font-bold text-blue-600 dark:text-blue-400">
              {Math.round(summary.completion_rate)}%
            </div>
            <p className="text-xs text-muted-foreground">household reliability</p>
          </CardContent>
        </Card>

        <Card data-testid="stat-card-unassigned">
          <CardHeader className="p-4 pb-1">
            <CardTitle className="text-xs font-medium text-muted-foreground flex items-center gap-1.5">
              <AlertCircle className="h-3.5 w-3.5 text-amber-500" />
              Unassigned
            </CardTitle>
          </CardHeader>
          <CardContent className="p-4 pt-1">
            <div
              className={`text-2xl font-bold ${
                summary.unassigned_count > 0
                  ? "text-amber-600 dark:text-amber-400"
                  : "text-muted-foreground"
              }`}
            >
              {summary.unassigned_count}
            </div>
            <p className="text-xs text-muted-foreground">needs coverage</p>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
