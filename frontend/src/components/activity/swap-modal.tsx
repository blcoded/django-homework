"use client";

import * as React from "react";
import { ArrowLeftRight, Check, X, Ban, Loader2, AlertCircle } from "lucide-react";
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

export interface SwapItem {
  id: number;
  proposer: { id: number; email: string; display_name: string };
  recipient: { id: number; email: string; display_name: string };
  proposer_occurrence: { id: number; chore: { id: number; title: string } };
  recipient_occurrence?: { id: number; chore: { id: number; title: string } } | null;
  status: "pending" | "accepted" | "declined" | "cancelled";
  notes?: string;
  created_at: string;
}

export interface MyOccurrenceOption {
  id: number;
  title: string;
}

export interface MemberOption {
  id: number;
  name: string;
}

interface SwapModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  myOccurrences: MyOccurrenceOption[];
  members: MemberOption[];
  swaps: SwapItem[];
  currentUserId?: number;
  onCreateSwap: (data: {
    proposer_occurrence_id: number;
    recipient_id: number;
    notes?: string;
  }) => Promise<void>;
  onAcceptSwap: (swapId: number) => Promise<void>;
  onDeclineSwap: (swapId: number) => Promise<void>;
  onCancelSwap: (swapId: number) => Promise<void>;
}

export function SwapModal({
  open,
  onOpenChange,
  myOccurrences,
  members,
  swaps,
  currentUserId,
  onCreateSwap,
  onAcceptSwap,
  onDeclineSwap,
  onCancelSwap,
}: SwapModalProps) {
  const [activeTab, setActiveTab] = React.useState<"list" | "propose">("list");
  const [selectedOccurrence, setSelectedOccurrence] = React.useState<number | "">("");
  const [selectedRecipient, setSelectedRecipient] = React.useState<number | "">("");
  const [notes, setNotes] = React.useState("");
  const [submitting, setSubmitting] = React.useState(false);
  const [actionId, setActionId] = React.useState<number | null>(null);
  const [error, setError] = React.useState<string | null>(null);

  const handlePropose = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedOccurrence || !selectedRecipient) {
      setError("Please select a chore and a recipient roommate.");
      return;
    }

    setSubmitting(true);
    setError(null);

    try {
      await onCreateSwap({
        proposer_occurrence_id: Number(selectedOccurrence),
        recipient_id: Number(selectedRecipient),
        notes: notes.trim() || undefined,
      });
      setSelectedOccurrence("");
      setSelectedRecipient("");
      setNotes("");
      setActiveTab("list");
    } catch (err: any) {
      setError(err.message || "Failed to propose swap.");
    } finally {
      setSubmitting(false);
    }
  };

  const handleAction = async (action: () => Promise<void>, id: number) => {
    setActionId(id);
    try {
      await action();
    } catch (err: any) {
      alert(err.message || "Action failed");
    } finally {
      setActionId(null);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[550px] max-h-[85vh] overflow-y-auto" data-testid="swap-modal">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <ArrowLeftRight className="h-5 w-5 text-primary" />
            Chore Swaps & Exchanges
          </DialogTitle>
          <DialogDescription>
            Trade chore responsibilities as personal favors without disrupting long-term rotation balance.
          </DialogDescription>
        </DialogHeader>

        {/* Tab switcher */}
        <div className="flex border-b text-xs font-medium">
          <button
            type="button"
            data-testid="tab-swap-list"
            onClick={() => setActiveTab("list")}
            className={`px-4 py-2 border-b-2 -mb-px transition-colors ${
              activeTab === "list"
                ? "border-primary text-primary"
                : "border-transparent text-muted-foreground hover:text-foreground"
            }`}
          >
            Active Swaps ({swaps.length})
          </button>
          <button
            type="button"
            data-testid="tab-swap-propose"
            onClick={() => setActiveTab("propose")}
            className={`px-4 py-2 border-b-2 -mb-px transition-colors ${
              activeTab === "propose"
                ? "border-primary text-primary"
                : "border-transparent text-muted-foreground hover:text-foreground"
            }`}
          >
            Propose New Swap
          </button>
        </div>

        {error && (
          <div
            data-testid="swap-error"
            className="flex items-center gap-2 p-3 text-xs rounded-md bg-destructive/10 text-destructive"
          >
            <AlertCircle className="h-4 w-4 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {activeTab === "list" ? (
          <div className="space-y-3 py-2" data-testid="swaps-list-content">
            {swaps.length === 0 ? (
              <p className="text-xs text-muted-foreground py-6 text-center italic">
                No active or pending chore swap requests.
              </p>
            ) : (
              swaps.map((sw) => {
                const isRecipient = sw.recipient?.id === currentUserId;
                const isProposer = sw.proposer?.id === currentUserId;
                const isPending = sw.status === "pending";

                return (
                  <div
                    key={sw.id}
                    data-testid={`swap-card-${sw.id}`}
                    className="p-3 rounded-lg border bg-card text-xs space-y-2"
                  >
                    <div className="flex items-center justify-between">
                      <div className="font-semibold text-foreground">
                        {sw.proposer_occurrence?.chore?.title || "Chore"}
                      </div>
                      <Badge
                        variant="outline"
                        className={`capitalize text-[10px] ${
                          sw.status === "accepted"
                            ? "text-emerald-600 border-emerald-500"
                            : sw.status === "declined"
                            ? "text-destructive border-destructive"
                            : "text-amber-600 border-amber-500"
                        }`}
                      >
                        {sw.status}
                      </Badge>
                    </div>

                    <div className="text-muted-foreground">
                      <span className="font-medium text-foreground">
                        {sw.proposer?.display_name || sw.proposer?.email}
                      </span>{" "}
                      →{" "}
                      <span className="font-medium text-foreground">
                        {sw.recipient?.display_name || sw.recipient?.email}
                      </span>
                    </div>

                    {sw.notes && <p className="italic text-muted-foreground">&quot;{sw.notes}&quot;</p>}

                    {isPending && (
                      <div className="pt-2 border-t flex justify-end gap-2">
                        {isRecipient && (
                          <>
                            <Button
                              size="sm"
                              variant="default"
                              data-testid={`accept-swap-btn-${sw.id}`}
                              disabled={actionId === sw.id}
                              onClick={() => handleAction(() => onAcceptSwap(sw.id), sw.id)}
                              className="h-7 px-2.5 gap-1 text-[11px]"
                            >
                              <Check className="h-3 w-3" />
                              <span>Accept</span>
                            </Button>
                            <Button
                              size="sm"
                              variant="outline"
                              data-testid={`decline-swap-btn-${sw.id}`}
                              disabled={actionId === sw.id}
                              onClick={() => handleAction(() => onDeclineSwap(sw.id), sw.id)}
                              className="h-7 px-2.5 gap-1 text-[11px] text-destructive hover:text-destructive"
                            >
                              <X className="h-3 w-3" />
                              <span>Decline</span>
                            </Button>
                          </>
                        )}
                        {isProposer && (
                          <Button
                            size="sm"
                            variant="ghost"
                            data-testid={`cancel-swap-btn-${sw.id}`}
                            disabled={actionId === sw.id}
                            onClick={() => handleAction(() => onCancelSwap(sw.id), sw.id)}
                            className="h-7 px-2.5 gap-1 text-[11px] text-muted-foreground hover:text-destructive"
                          >
                            <Ban className="h-3 w-3" />
                            <span>Cancel Request</span>
                          </Button>
                        )}
                      </div>
                    )}
                  </div>
                );
              })
            )}
          </div>
        ) : (
          <form onSubmit={handlePropose} noValidate className="space-y-4 py-2" data-testid="swap-form">
            <div className="space-y-1.5">
              <label htmlFor="swap-occurrence" className="text-xs font-semibold text-foreground">
                Chore you want to swap / give away *
              </label>
              <select
                id="swap-occurrence"
                data-testid="swap-occurrence-select"
                value={selectedOccurrence}
                onChange={(e) => setSelectedOccurrence(e.target.value ? Number(e.target.value) : "")}
                className="w-full h-9 rounded-md border border-input bg-background px-3 py-1 text-xs shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                required
              >
                <option value="">Select your active chore...</option>
                {myOccurrences.map((occ) => (
                  <option key={occ.id} value={occ.id}>
                    {occ.title}
                  </option>
                ))}
              </select>
            </div>

            <div className="space-y-1.5">
              <label htmlFor="swap-recipient" className="text-xs font-semibold text-foreground">
                Swap recipient (Housemate) *
              </label>
              <select
                id="swap-recipient"
                data-testid="swap-recipient-select"
                value={selectedRecipient}
                onChange={(e) => setSelectedRecipient(e.target.value ? Number(e.target.value) : "")}
                className="w-full h-9 rounded-md border border-input bg-background px-3 py-1 text-xs shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                required
              >
                <option value="">Select a roommate...</option>
                {members
                  .filter((m) => m.id !== currentUserId)
                  .map((m) => (
                    <option key={m.id} value={m.id}>
                      {m.name}
                    </option>
                  ))}
              </select>
            </div>

            <div className="space-y-1.5">
              <label htmlFor="swap-notes" className="text-xs font-semibold text-foreground">
                Reason / Note (Optional)
              </label>
              <Input
                id="swap-notes"
                name="notes"
                data-testid="swap-notes-input"
                placeholder="e.g., Traveling this weekend, will pick up dishes next week"
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                className="text-xs"
              />
            </div>

            <DialogFooter className="pt-2">
              <Button type="button" variant="outline" onClick={() => setActiveTab("list")} disabled={submitting}>
                Back to list
              </Button>
              <Button type="submit" data-testid="submit-swap-button" disabled={submitting} className="gap-1.5">
                {submitting ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin" />
                    <span>Submitting...</span>
                  </>
                ) : (
                  <>
                    <ArrowLeftRight className="h-4 w-4" />
                    <span>Send Proposal</span>
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
