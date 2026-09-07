"use client";

import * as React from "react";
import { Plane, Calendar, Check, X, Loader2, AlertCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

export interface AbsenceItem {
  id: number;
  member: { id: number; user: { id: number; email: string; display_name: string } };
  start_date: string;
  end_date: string;
  reason?: string;
  status: "pending" | "approved" | "rejected" | "ended";
  votes?: Array<{ voter_id: number; approved: boolean }>;
}

interface AbsenceModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  absences: AbsenceItem[];
  currentUserId?: number;
  onCreateAbsence: (data: {
    start_date: string;
    end_date: string;
    reason?: string;
  }) => Promise<void>;
  onVoteAbsence: (absenceId: number, approved: boolean) => Promise<void>;
}

export function AbsenceModal({
  open,
  onOpenChange,
  absences,
  currentUserId,
  onCreateAbsence,
  onVoteAbsence,
}: AbsenceModalProps) {
  const [activeTab, setActiveTab] = React.useState<"list" | "request">("list");
  const [startDate, setStartDate] = React.useState("");
  const [endDate, setEndDate] = React.useState("");
  const [reason, setReason] = React.useState("");
  const [submitting, setSubmitting] = React.useState(false);
  const [votingId, setVotingId] = React.useState<number | null>(null);
  const [error, setError] = React.useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!startDate || !endDate) {
      setError("Please specify both start and end dates.");
      return;
    }

    if (new Date(startDate) > new Date(endDate)) {
      setError("End date must be on or after start date.");
      return;
    }

    setSubmitting(true);
    setError(null);

    try {
      await onCreateAbsence({
        start_date: startDate,
        end_date: endDate,
        reason: reason.trim() || undefined,
      });
      setStartDate("");
      setEndDate("");
      setReason("");
      setActiveTab("list");
    } catch (err: any) {
      setError(err.message || "Failed to submit absence request.");
    } finally {
      setSubmitting(false);
    }
  };

  const handleVote = async (id: number, approved: boolean) => {
    setVotingId(id);
    try {
      await onVoteAbsence(id, approved);
    } catch (err: any) {
      alert(err.message || "Vote failed.");
    } finally {
      setVotingId(null);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[520px] max-h-[85vh] overflow-y-auto" data-testid="absence-modal">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Plane className="h-5 w-5 text-primary" />
            Temporary Absence & Pause
          </DialogTitle>
          <DialogDescription>
            Going out of town? Chores will automatically skip you during approved absence windows.
          </DialogDescription>
        </DialogHeader>

        {/* Tab switcher */}
        <div className="flex border-b text-xs font-medium">
          <button
            type="button"
            data-testid="tab-absence-list"
            onClick={() => setActiveTab("list")}
            className={`px-4 py-2 border-b-2 -mb-px transition-colors ${
              activeTab === "list"
                ? "border-primary text-primary"
                : "border-transparent text-muted-foreground hover:text-foreground"
            }`}
          >
            Scheduled Absences ({absences.length})
          </button>
          <button
            type="button"
            data-testid="tab-absence-request"
            onClick={() => setActiveTab("request")}
            className={`px-4 py-2 border-b-2 -mb-px transition-colors ${
              activeTab === "request"
                ? "border-primary text-primary"
                : "border-transparent text-muted-foreground hover:text-foreground"
            }`}
          >
            Request New Pause
          </button>
        </div>

        {error && (
          <div
            data-testid="absence-error"
            className="flex items-center gap-2 p-3 text-xs rounded-md bg-destructive/10 text-destructive"
          >
            <AlertCircle className="h-4 w-4 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {activeTab === "list" ? (
          <div className="space-y-3 py-2" data-testid="absences-list-content">
            {absences.length === 0 ? (
              <p className="text-xs text-muted-foreground py-6 text-center italic">
                No active or scheduled household absences.
              </p>
            ) : (
              absences.map((ab) => {
                const isRequester = ab.member?.user?.id === currentUserId;
                const isPending = ab.status === "pending";

                return (
                  <div
                    key={ab.id}
                    data-testid={`absence-card-${ab.id}`}
                    className="p-3 rounded-lg border bg-card text-xs space-y-2"
                  >
                    <div className="flex items-center justify-between">
                      <div className="font-semibold text-foreground flex items-center gap-1.5">
                        <Calendar className="h-3.5 w-3.5 text-muted-foreground" />
                        <span>
                          {ab.member?.user?.display_name || ab.member?.user?.email || "Roommate"}
                        </span>
                      </div>
                      <Badge
                        variant="outline"
                        className={`capitalize text-[10px] ${
                          ab.status === "approved"
                            ? "text-emerald-600 border-emerald-500"
                            : ab.status === "rejected"
                            ? "text-destructive border-destructive"
                            : "text-amber-600 border-amber-500"
                        }`}
                      >
                        {ab.status}
                      </Badge>
                    </div>

                    <div className="text-muted-foreground">
                      {ab.start_date} to {ab.end_date}
                    </div>

                    {ab.reason && <p className="italic text-muted-foreground">&quot;{ab.reason}&quot;</p>}

                    {isPending && !isRequester && (
                      <div className="pt-2 border-t flex justify-end gap-2">
                        <Button
                          size="sm"
                          data-testid={`approve-absence-btn-${ab.id}`}
                          disabled={votingId === ab.id}
                          onClick={() => handleVote(ab.id, true)}
                          className="h-7 px-2.5 gap-1 text-[11px]"
                        >
                          <Check className="h-3 w-3" />
                          <span>Approve</span>
                        </Button>
                        <Button
                          size="sm"
                          variant="outline"
                          data-testid={`reject-absence-btn-${ab.id}`}
                          disabled={votingId === ab.id}
                          onClick={() => handleVote(ab.id, false)}
                          className="h-7 px-2.5 gap-1 text-[11px] text-destructive hover:text-destructive"
                        >
                          <X className="h-3 w-3" />
                          <span>Reject</span>
                        </Button>
                      </div>
                    )}
                  </div>
                );
              })
            )}
          </div>
        ) : (
          <form onSubmit={handleSubmit} noValidate className="space-y-4 py-2" data-testid="absence-form">
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <label htmlFor="absence-start" className="text-xs font-semibold text-foreground">
                  Start Date *
                </label>
                <Input
                  id="absence-start"
                  type="date"
                  data-testid="absence-start-input"
                  value={startDate}
                  onChange={(e) => setStartDate(e.target.value)}
                  className="text-xs"
                  required
                />
              </div>

              <div className="space-y-1.5">
                <label htmlFor="absence-end" className="text-xs font-semibold text-foreground">
                  End Date *
                </label>
                <Input
                  id="absence-end"
                  type="date"
                  data-testid="absence-end-input"
                  value={endDate}
                  onChange={(e) => setEndDate(e.target.value)}
                  className="text-xs"
                  required
                />
              </div>
            </div>

            <div className="space-y-1.5">
              <label htmlFor="absence-reason" className="text-xs font-semibold text-foreground">
                Reason / Note (Optional)
              </label>
              <Input
                id="absence-reason"
                name="reason"
                data-testid="absence-reason-input"
                placeholder="e.g., Visiting family, conference travel"
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                className="text-xs"
              />
            </div>

            <DialogFooter className="pt-2">
              <Button type="button" variant="outline" onClick={() => setActiveTab("list")} disabled={submitting}>
                Back to list
              </Button>
              <Button type="submit" data-testid="submit-absence-button" disabled={submitting} className="gap-1.5">
                {submitting ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin" />
                    <span>Submitting...</span>
                  </>
                ) : (
                  <>
                    <Plane className="h-4 w-4" />
                    <span>Submit Request</span>
                  </>
                )}
              </Button>
            </DialogFooter>
          </form>
        )}
      </DialogContent>
    </Dialog>
  );
}
