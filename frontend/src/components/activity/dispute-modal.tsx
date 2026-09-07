"use client";

import * as React from "react";
import { AlertTriangle, Loader2, AlertCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

interface DisputeModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  occurrenceId: number | null;
  choreTitle: string;
  onSuccess: () => void;
  onSubmitDispute: (occurrenceId: number, reason: string) => Promise<any>;
}

export function DisputeModal({
  open,
  onOpenChange,
  occurrenceId,
  choreTitle,
  onSuccess,
  onSubmitDispute,
}: DisputeModalProps) {
  const [reason, setReason] = React.useState("");
  const [submitting, setSubmitting] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!occurrenceId) return;
    if (!reason.trim()) {
      setError("Please provide a constructive explanation for the dispute.");
      return;
    }

    setSubmitting(true);
    setError(null);

    try {
      await onSubmitDispute(occurrenceId, reason.trim());
      setReason("");
      onOpenChange(false);
      onSuccess();
    } catch (err: any) {
      setError(err.message || "Failed to submit dispute.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[480px]" data-testid="dispute-modal">
        <form onSubmit={handleSubmit} noValidate>
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-destructive">
              <AlertTriangle className="h-5 w-5" />
              Open Completion Dispute
            </DialogTitle>
            <DialogDescription>
              Flagging <strong className="text-foreground">{choreTitle}</strong> as incomplete or unsatisfactory.
              The completion record and photo evidence remain intact for transparent household review.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-4">
            {error && (
              <div
                data-testid="dispute-error"
                className="flex items-center gap-2 p-3 text-xs rounded-md bg-destructive/10 text-destructive"
              >
                <AlertCircle className="h-4 w-4 shrink-0" />
                <span>{error}</span>
              </div>
            )}

            <div className="space-y-1.5">
              <label htmlFor="dispute-reason" className="text-xs font-semibold text-foreground">
                Explanation / Reason *
              </label>
              <textarea
                id="dispute-reason"
                name="reason"
                data-testid="dispute-reason-input"
                rows={3}
                placeholder="e.g., Recycling bin was not taken to the curb, or dishes were left in sink..."
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                className="w-full rounded-md border border-input bg-transparent px-3 py-2 text-sm shadow-sm placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                required
              />
            </div>
          </div>

          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
              disabled={submitting}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              variant="destructive"
              data-testid="submit-dispute-button"
              disabled={submitting}
              className="gap-1.5"
            >
              {submitting ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  <span>Submitting...</span>
                </>
              ) : (
                <>
                  <AlertTriangle className="h-4 w-4" />
                  <span>Confirm Dispute</span>
                </>
              )}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
