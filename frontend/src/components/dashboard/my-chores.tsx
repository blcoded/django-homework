"use client";

import * as React from "react";
import { CheckCircle2, Clock, AlertTriangle, ArrowRight, Sparkles } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

export interface ChoreOccurrenceItem {
  id: number;
  chore: {
    id: number;
    title: string;
    effort_level: "small" | "medium" | "large";
    points?: number;
  };
  status: "upcoming" | "active" | "completed" | "missed" | "completed_late" | "disputed" | "unassigned";
  scheduled_start: string;
  due_date: string | null;
  is_actionable?: boolean;
}

interface MyChoresProps {
  activeChores: ChoreOccurrenceItem[];
  nextUpChore?: ChoreOccurrenceItem | null;
  onComplete?: (occurrenceId: number) => void;
  completingId?: number | null;
}

export function MyChores({
  activeChores,
  nextUpChore,
  onComplete,
  completingId,
}: MyChoresProps) {
  const isOverdue = (dueDate: string | null) => {
    if (!dueDate) return false;
    return new Date(dueDate) < new Date();
  };

  const getEffortBadge = (level: string) => {
    switch (level) {
      case "small":
        return <Badge variant="secondary" className="bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300">Small (1 pt)</Badge>;
      case "large":
        return <Badge variant="secondary" className="bg-purple-100 text-purple-800 dark:bg-purple-950 dark:text-purple-300">Large (3 pts)</Badge>;
      default:
        return <Badge variant="secondary" className="bg-blue-100 text-blue-800 dark:bg-blue-950 dark:text-blue-300">Medium (2 pts)</Badge>;
    }
  };

  return (
    <div className="space-y-6" data-testid="my-chores-section">
      <div>
        <h2 className="text-xl font-bold tracking-tight">My Active Responsibilities</h2>
        <p className="text-sm text-muted-foreground">
          Chores currently requiring your attention. Complete them to maintain your streak!
        </p>
      </div>

      {activeChores.length === 0 ? (
        <Card className="border-dashed bg-muted/20 text-center py-8">
          <CardContent className="space-y-2">
            <CheckCircle2 className="mx-auto h-10 w-10 text-emerald-500" />
            <p className="font-semibold text-foreground">You are all caught up!</p>
            <p className="text-sm text-muted-foreground">
              No active chores assigned to you right now. Sit back and relax.
            </p>
          </CardContent>
        </Card>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2">
          {activeChores.map((occ) => {
            const overdue = isOverdue(occ.due_date);
            return (
              <Card
                key={occ.id}
                data-testid={`active-chore-card-${occ.id}`}
                className={`shadow-sm border transition-all ${
                  overdue
                    ? "border-destructive/50 bg-destructive/5"
                    : "hover:border-primary/50"
                }`}
              >
                <CardHeader className="pb-3">
                  <div className="flex items-center justify-between gap-2">
                    <CardTitle className="text-base font-semibold truncate">
                      {occ.chore.title}
                    </CardTitle>
                    {getEffortBadge(occ.chore.effort_level)}
                  </div>
                  {overdue ? (
                    <CardDescription className="flex items-center gap-1.5 text-xs text-destructive font-semibold">
                      <AlertTriangle className="h-3.5 w-3.5 shrink-0" />
                      <span>Past Due / Missed</span>
                    </CardDescription>
                  ) : occ.due_date ? (
                    <CardDescription className="flex items-center gap-1.5 text-xs text-muted-foreground">
                      <Clock className="h-3.5 w-3.5 shrink-0" />
                      <span>Due: {new Date(occ.due_date).toLocaleDateString()}</span>
                    </CardDescription>
                  ) : (
                    <CardDescription className="text-xs text-muted-foreground">
                      Flexible window (no strict deadline)
                    </CardDescription>
                  )}
                </CardHeader>

                <CardFooter className="pt-2 flex justify-between items-center border-t">
                  <span className="text-xs text-muted-foreground font-medium">
                    1-Tap Completion
                  </span>
                  <Button
                    size="sm"
                    data-testid={`complete-button-${occ.id}`}
                    disabled={completingId === occ.id}
                    onClick={() => onComplete && onComplete(occ.id)}
                    className="gap-1.5"
                  >
                    <CheckCircle2 className="h-4 w-4" />
                    <span>Done</span>
                  </Button>
                </CardFooter>
              </Card>
            );
          })}
        </div>
      )}

      {nextUpChore && (
        <Card data-testid="next-up-card" className="bg-primary/5 border-primary/20">
          <CardHeader className="pb-2">
            <div className="flex items-center gap-2 text-primary font-semibold text-xs uppercase tracking-wider">
              <Sparkles className="h-4 w-4" />
              <span>You&apos;re Next Up</span>
            </div>
            <CardTitle className="text-base font-bold">
              {nextUpChore.chore.title}
            </CardTitle>
            <CardDescription className="text-xs">
              Scheduled start:{" "}
              {new Date(nextUpChore.scheduled_start).toLocaleDateString()} (Future rotation hidden)
            </CardDescription>
          </CardHeader>
          <CardContent className="pt-0 text-xs text-muted-foreground">
            Responsibility assigned early so you can plan ahead. Action window opens soon.
          </CardContent>
        </Card>
      )}
    </div>
  );
}
