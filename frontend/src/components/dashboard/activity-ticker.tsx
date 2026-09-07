"use client";

import * as React from "react";
import Link from "next/link";
import { Activity, ArrowRight, CheckCircle, Repeat, Award, AlertCircle } from "lucide-react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";

export interface ActivityItem {
  id: number;
  event_type: string;
  description: string;
  user_name?: string;
  created_at: string;
}

interface ActivityTickerProps {
  events: ActivityItem[];
}

export function ActivityTicker({ events }: ActivityTickerProps) {
  const getEventIcon = (type: string) => {
    switch (type) {
      case "chore_completed":
      case "verification_approved":
        return <CheckCircle className="h-4 w-4 text-emerald-500 shrink-0" />;
      case "swap_completed":
      case "swap_requested":
        return <Repeat className="h-4 w-4 text-blue-500 shrink-0" />;
      case "milestone_unlocked":
      case "streak_milestone":
        return <Award className="h-4 w-4 text-purple-500 shrink-0" />;
      case "dispute_opened":
      case "chore_missed":
        return <AlertCircle className="h-4 w-4 text-amber-500 shrink-0" />;
      default:
        return <Activity className="h-4 w-4 text-muted-foreground shrink-0" />;
    }
  };

  const formatTimestamp = (iso: string) => {
    try {
      const date = new Date(iso);
      return date.toLocaleDateString(undefined, {
        month: "short",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      });
    } catch {
      return iso;
    }
  };

  return (
    <Card data-testid="activity-ticker-card" className="h-full flex flex-col justify-between">
      <div>
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Activity className="h-4 w-4 text-primary" />
              <CardTitle className="text-base font-semibold">Live Activity</CardTitle>
            </div>
            <Link href="/activity" className="text-xs text-primary hover:underline flex items-center gap-1 font-medium">
              View all
              <ArrowRight className="h-3 w-3" />
            </Link>
          </div>
          <CardDescription className="text-xs">
            Recent updates across your household
          </CardDescription>
        </CardHeader>

        <CardContent className="space-y-3">
          {events.length === 0 ? (
            <p className="text-xs text-muted-foreground py-4 text-center italic">
              No recent household events recorded yet.
            </p>
          ) : (
            <div className="space-y-2.5">
              {events.slice(0, 5).map((evt) => (
                <div
                  key={evt.id}
                  data-testid={`activity-event-item-${evt.id}`}
                  className="flex items-start gap-2.5 text-xs p-2 rounded-md hover:bg-muted/50 transition-colors"
                >
                  <div className="mt-0.5">{getEventIcon(evt.event_type)}</div>
                  <div className="flex-1 min-w-0">
                    <p className="text-foreground leading-snug line-clamp-2">
                      {evt.description}
                    </p>
                    <div className="flex items-center gap-2 mt-1 text-[11px] text-muted-foreground">
                      {evt.user_name && (
                        <span className="font-medium text-foreground/80">
                          {evt.user_name}
                        </span>
                      )}
                      <span>•</span>
                      <span>{formatTimestamp(evt.created_at)}</span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </div>

      <div className="p-4 pt-0">
        <Button variant="ghost" size="sm" asChild className="w-full text-xs text-muted-foreground hover:text-foreground">
          <Link href="/activity">Open Full Audit History</Link>
        </Button>
      </div>
    </Card>
  );
}
