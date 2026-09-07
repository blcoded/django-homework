"use client";

import * as React from "react";
import { ThumbsUp, ThumbsDown, CheckCircle, Clock } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";

export interface SuggestionItem {
  id: number;
  title: string;
  description?: string;
  suggested_frequency: string;
  suggested_effort: string;
  status: "pending" | "approved" | "rejected";
  upvotes_count: number;
  downvotes_count: number;
  has_voted?: boolean;
  my_vote?: "up" | "down" | null;
}

interface SuggestionListProps {
  suggestions: SuggestionItem[];
  onVote: (id: number, voteType: "up" | "down") => Promise<void>;
  votingId?: number | null;
}

export function SuggestionList({ suggestions, onVote, votingId }: SuggestionListProps) {
  if (suggestions.length === 0) {
    return (
      <Card className="border-dashed bg-muted/20 text-center py-8">
        <CardContent className="space-y-2">
          <p className="font-semibold text-foreground">No proposals active</p>
          <p className="text-sm text-muted-foreground">
            Have a chore in mind that should be added to the rotation? Submit an anonymous suggestion!
          </p>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-4" data-testid="suggestions-list">
      {suggestions.map((sug) => {
        const isVoting = votingId === sug.id;
        return (
          <Card key={sug.id} data-testid={`suggestion-card-${sug.id}`} className="shadow-sm">
            <CardHeader className="pb-2">
              <div className="flex items-start justify-between gap-2">
                <div className="space-y-1">
                  <CardTitle className="text-base font-semibold">{sug.title}</CardTitle>
                  {sug.description && (
                    <CardDescription className="text-xs text-muted-foreground">
                      {sug.description}
                    </CardDescription>
                  )}
                </div>
                <div className="flex items-center gap-1.5 shrink-0">
                  <Badge variant="outline" className="text-xs capitalize">
                    {sug.suggested_frequency}
                  </Badge>
                  <Badge variant="secondary" className="text-xs capitalize">
                    {sug.suggested_effort}
                  </Badge>
                </div>
              </div>
            </CardHeader>

            <CardContent className="pt-2 flex items-center justify-between border-t text-xs">
              <div className="flex items-center gap-2 text-muted-foreground">
                <span className="italic">Anonymous Proposal</span>
                <span>•</span>
                <span
                  className={`font-semibold capitalize ${
                    sug.status === "approved"
                      ? "text-emerald-600 dark:text-emerald-400"
                      : sug.status === "rejected"
                      ? "text-destructive"
                      : "text-amber-600 dark:text-amber-400"
                  }`}
                >
                  {sug.status}
                </span>
              </div>

              <div className="flex items-center gap-2">
                <Button
                  size="sm"
                  variant={sug.my_vote === "up" ? "default" : "outline"}
                  data-testid={`upvote-button-${sug.id}`}
                  disabled={isVoting || sug.status !== "pending"}
                  onClick={() => onVote(sug.id, "up")}
                  className="h-8 px-2.5 gap-1.5 text-xs"
                >
                  <ThumbsUp className="h-3.5 w-3.5" />
                  <span>{sug.upvotes_count}</span>
                </Button>

                <Button
                  size="sm"
                  variant={sug.my_vote === "down" ? "destructive" : "outline"}
                  data-testid={`downvote-button-${sug.id}`}
                  disabled={isVoting || sug.status !== "pending"}
                  onClick={() => onVote(sug.id, "down")}
                  className="h-8 px-2.5 gap-1.5 text-xs"
                >
                  <ThumbsDown className="h-3.5 w-3.5" />
                  <span>{sug.downvotes_count}</span>
                </Button>
              </div>
            </CardContent>
          </Card>
        );
      })}
    </div>
  );
}
