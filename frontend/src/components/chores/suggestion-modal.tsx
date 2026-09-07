"use client";

import * as React from "react";
import { Lightbulb, Loader2, AlertCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

interface SuggestionModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSuccess: () => void;
  onCreateApi: (data: {
    title: string;
    description?: string;
    suggested_frequency?: string;
    suggested_effort?: string;
  }) => Promise<any>;
}

export function SuggestionModal({
  open,
  onOpenChange,
  onSuccess,
  onCreateApi,
}: SuggestionModalProps) {
  const [title, setTitle] = React.useState("");
  const [description, setDescription] = React.useState("");
  const [frequency, setFrequency] = React.useState("weekly");
  const [effort, setEffort] = React.useState("medium");
  const [submitting, setSubmitting] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!title.trim()) {
      setError("Please provide a chore title.");
      return;
    }

    setSubmitting(true);
    setError(null);

    try {
      await onCreateApi({
        title: title.trim(),
        description: description.trim() || undefined,
        suggested_frequency: frequency,
        suggested_effort: effort,
      });
      setTitle("");
      setDescription("");
      setFrequency("weekly");
      setEffort("medium");
      onOpenChange(false);
      onSuccess();
    } catch (err: any) {
      setError(err.message || "Failed to submit anonymous suggestion.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[480px]" data-testid="suggestion-modal">
        <form onSubmit={handleSubmit} noValidate>
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Lightbulb className="h-5 w-5 text-amber-500" />
              Propose Chore (Anonymous)
            </DialogTitle>
            <DialogDescription>
              Suggest a new chore for your household to vote on. Your identity will never be revealed to housemates.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-4">
            {error && (
              <div
                data-testid="suggestion-error"
                className="flex items-center gap-2 p-3 text-xs rounded-md bg-destructive/10 text-destructive"
              >
                <AlertCircle className="h-4 w-4 shrink-0" />
                <span>{error}</span>
              </div>
            )}

            <div className="space-y-1.5">
              <label htmlFor="suggestion-title" className="text-xs font-semibold text-foreground">
                Chore Title *
              </label>
              <Input
                id="suggestion-title"
                name="title"
                data-testid="suggestion-title-input"
                placeholder="e.g., Clean microwave & oven"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                required
              />
            </div>

            <div className="space-y-1.5">
              <label htmlFor="suggestion-description" className="text-xs font-semibold text-foreground">
                Description / Expectations (Optional)
              </label>
              <textarea
                id="suggestion-description"
                name="description"
                data-testid="suggestion-description-input"
                rows={3}
                placeholder="Describe what needs to be done..."
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                className="w-full rounded-md border border-input bg-transparent px-3 py-2 text-sm shadow-sm placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
              />
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <label htmlFor="suggestion-frequency" className="text-xs font-semibold text-foreground">
                  Frequency
                </label>
                <select
                  id="suggestion-frequency"
                  data-testid="suggestion-frequency-select"
                  value={frequency}
                  onChange={(e) => setFrequency(e.target.value)}
                  className="w-full h-9 rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                >
                  <option value="daily">Daily</option>
                  <option value="weekly">Weekly</option>
                  <option value="biweekly">Bi-weekly</option>
                  <option value="monthly">Monthly</option>
                </select>
              </div>

              <div className="space-y-1.5">
                <label htmlFor="suggestion-effort" className="text-xs font-semibold text-foreground">
                  Effort Level
                </label>
                <select
                  id="suggestion-effort"
                  data-testid="suggestion-effort-select"
                  value={effort}
                  onChange={(e) => setEffort(e.target.value)}
                  className="w-full h-9 rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                >
                  <option value="small">Small (15 min / 1 pt)</option>
                  <option value="medium">Medium (30 min / 2 pts)</option>
                  <option value="large">Large (60+ min / 3 pts)</option>
                </select>
              </div>
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
              data-testid="submit-suggestion-button"
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
                  <Lightbulb className="h-4 w-4" />
                  <span>Submit Anonymously</span>
                </>
              )}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
