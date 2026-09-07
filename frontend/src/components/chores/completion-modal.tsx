"use client";

import * as React from "react";
import { CheckCircle2, Upload, AlertCircle, Loader2 } from "lucide-react";
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

interface CompletionModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  occurrenceId: number | null;
  choreTitle: string;
  onSuccess: () => void;
  onCompleteApi: (id: number, data: { notes?: string; photo_proof?: string }) => Promise<any>;
}

export function CompletionModal({
  open,
  onOpenChange,
  occurrenceId,
  choreTitle,
  onSuccess,
  onCompleteApi,
}: CompletionModalProps) {
  const [notes, setNotes] = React.useState("");
  const [photoProof, setPhotoProof] = React.useState("");
  const [submitting, setSubmitting] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      const reader = new FileReader();
      reader.onloadend = () => {
        setPhotoProof(reader.result as string);
      };
      reader.readAsDataURL(file);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!occurrenceId) return;

    setSubmitting(true);
    setError(null);

    try {
      await onCompleteApi(occurrenceId, {
        notes: notes.trim() || undefined,
        photo_proof: photoProof || undefined,
      });
      setNotes("");
      setPhotoProof("");
      onOpenChange(false);
      onSuccess();
    } catch (err: any) {
      setError(err.message || "Failed to mark chore completed.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[480px]" data-testid="completion-modal">
        <form onSubmit={handleSubmit} noValidate>
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <CheckCircle2 className="h-5 w-5 text-emerald-500" />
              Complete Chore
            </DialogTitle>
            <DialogDescription>
              Marking <strong className="text-foreground">{choreTitle}</strong> as completed.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-4">
            {error && (
              <div
                data-testid="completion-error"
                className="flex items-center gap-2 p-3 text-xs rounded-md bg-destructive/10 text-destructive"
              >
                <AlertCircle className="h-4 w-4 shrink-0" />
                <span>{error}</span>
              </div>
            )}

            <div className="space-y-1.5">
              <label htmlFor="notes" className="text-xs font-semibold text-foreground">
                Notes / Details (Optional)
              </label>
              <textarea
                id="notes"
                name="notes"
                data-testid="completion-notes-input"
                rows={3}
                placeholder="e.g., Replaced trash bag, wiped counters down"
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                className="w-full rounded-md border border-input bg-transparent px-3 py-2 text-sm shadow-sm placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
              />
            </div>

            <div className="space-y-1.5">
              <label htmlFor="photo" className="text-xs font-semibold text-foreground flex items-center gap-1.5">
                <Upload className="h-3.5 w-3.5" />
                Photo Proof / Verification (Optional)
              </label>
              <Input
                id="photo"
                type="file"
                accept="image/*"
                data-testid="completion-photo-input"
                onChange={handleFileChange}
                className="text-xs file:mr-4 file:py-1 file:px-2 file:rounded-md file:border-0 file:text-xs file:font-semibold file:bg-primary/10 file:text-primary hover:file:bg-primary/20"
              />
              {photoProof && (
                <p className="text-[11px] text-emerald-600 dark:text-emerald-400 font-medium" data-testid="photo-attached-notice">
                  ✓ Photo attached ({Math.round(photoProof.length / 1024)} KB)
                </p>
              )}
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
              data-testid="submit-completion-button"
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
                  <CheckCircle2 className="h-4 w-4" />
                  <span>Confirm Completion</span>
                </>
              )}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
