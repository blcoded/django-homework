"use client";

import * as React from "react";
import { CheckCircle2, User, Clock, AlertTriangle } from "lucide-react";
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

export interface ChoreItem {
  id: number;
  title: string;
  description?: string;
  effort_level: "small" | "medium" | "large";
  frequency?: string;
  is_active?: boolean;
  active_occurrence?: {
    id: number;
    assigned_member_name?: string;
    assigned_to_user_id?: number;
    status: string;
    due_date?: string | null;
  } | null;
}

interface ChoreCardProps {
  chore: ChoreItem;
  currentUserId?: number;
  onOpenCompleteModal?: (occurrenceId: number, choreTitle: string) => void;
}

export function ChoreCard({ chore, currentUserId, onOpenCompleteModal }: ChoreCardProps) {
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

  const occ = chore.active_occurrence;
  const isAssignedToMe = occ && occ.assigned_to_user_id === currentUserId;
  const isUnassigned = !occ || !occ.assigned_to_user_id;

  return (
    <Card data-testid={`chore-card-${chore.id}`} className="flex flex-col justify-between shadow-sm">
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between gap-2">
          <div className="space-y-1">
            <CardTitle className="text-base font-semibold">{chore.title}</CardTitle>
            {chore.description && (
              <CardDescription className="text-xs line-clamp-2">
                {chore.description}
              </CardDescription>
            )}
          </div>
          {getEffortBadge(chore.effort_level)}
        </div>
      </CardHeader>

      <CardContent className="py-2 space-y-2 border-t text-xs">
        <div className="flex items-center justify-between text-muted-foreground">
          <span>Cadence:</span>
          <span className="font-medium text-foreground capitalize">
            {chore.frequency || "Weekly"}
          </span>
        </div>

        <div className="flex items-center justify-between">
          <span className="text-muted-foreground flex items-center gap-1">
            <User className="h-3 w-3" />
            Current Assignee:
          </span>
          <span className="font-semibold text-foreground">
            {isUnassigned
              ? "Unassigned"
              : isAssignedToMe
              ? "You"
              : occ.assigned_member_name || "Housemate"}
          </span>
        </div>

        {occ?.due_date && (
          <div className="flex items-center justify-between text-muted-foreground">
            <span className="flex items-center gap-1">
              <Clock className="h-3 w-3" />
              Due:
            </span>
            <span>{new Date(occ.due_date).toLocaleDateString()}</span>
          </div>
        )}
      </CardContent>

      <CardFooter className="pt-2 border-t flex justify-between items-center bg-muted/10">
        <div className="text-[11px] text-muted-foreground">
          {isUnassigned ? (
            <span className="text-amber-600 dark:text-amber-400 font-medium">Needs Coverage</span>
          ) : isAssignedToMe ? (
            <span className="text-primary font-semibold">Assigned to you</span>
          ) : (
            <span>In progress</span>
          )}
        </div>

        {occ && onOpenCompleteModal && (
          <Button
            size="sm"
            data-testid={`chore-card-complete-btn-${chore.id}`}
            onClick={() => onOpenCompleteModal(occ.id, chore.title)}
            className="h-8 gap-1.5 text-xs"
          >
            <CheckCircle2 className="h-3.5 w-3.5" />
            <span>Complete</span>
          </Button>
        )}
      </CardFooter>
    </Card>
  );
}
