"use client";

import * as React from "react";
import {
  Activity,
  CheckCircle2,
  Repeat,
  Plane,
  AlertTriangle,
  Award,
  Calendar,
  Image as ImageIcon,
  RefreshCw,
  AlertCircle,
  Plus,
  ArrowLeftRight,
} from "lucide-react";
import { useAuth } from "@/context/auth-context";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { SwapModal, SwapItem, MyOccurrenceOption, MemberOption } from "@/components/activity/swap-modal";
import { AbsenceModal, AbsenceItem } from "@/components/activity/absence-modal";
import { ProofModal } from "@/components/activity/proof-modal";
import { DisputeModal } from "@/components/activity/dispute-modal";

interface EventItem {
  id: number;
  event_type: string;
  title: string;
  description: string;
  actor_name?: string;
  actor_id?: number;
  chore_title?: string;
  occurrence_id?: number;
  photo_proof?: string;
  created_at: string;
  metadata?: any;
}

type EventFilter = "all" | "completion" | "swap" | "absence" | "dispute";

export default function ActivityPage() {
  const { user, household } = useAuth();

  const [filter, setFilter] = React.useState<EventFilter>("all");
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);

  const [events, setEvents] = React.useState<EventItem[]>([]);
  const [swaps, setSwaps] = React.useState<SwapItem[]>([]);
  const [absences, setAbsences] = React.useState<AbsenceItem[]>([]);
  const [myOccurrences, setMyOccurrences] = React.useState<MyOccurrenceOption[]>([]);
  const [householdMembers, setHouseholdMembers] = React.useState<MemberOption[]>([]);

  // Modals
  const [swapModalOpen, setSwapModalOpen] = React.useState(false);
  const [absenceModalOpen, setAbsenceModalOpen] = React.useState(false);
  const [proofModalOpen, setProofModalOpen] = React.useState(false);
  const [proofData, setProofData] = React.useState<{ title: string; url: string } | null>(null);
  const [disputeModalOpen, setDisputeModalOpen] = React.useState(false);
  const [disputeTarget, setDisputeTarget] = React.useState<{ occurrenceId: number; title: string } | null>(null);

  const loadData = React.useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const [activityLogs, swapsData, absencesData, occurrencesData] = await Promise.all([
        api.activity.list().catch(() => []),
        api.chores.swaps.list().catch(() => []),
        api.absences.list().catch(() => []),
        api.chores.occurrences().catch(() => []),
      ]);

      if (Array.isArray(activityLogs)) {
        const mapped: EventItem[] = activityLogs.map((log: any) => ({
          id: log.id,
          event_type: log.event_type,
          title: log.title || log.event_type.replace(/_/g, " "),
          description: log.description,
          actor_name: log.actor?.display_name || log.actor?.email || log.user_display_name,
          actor_id: log.actor?.id || log.actor,
          chore_title: log.chore?.title || log.chore_title,
          occurrence_id: log.occurrence?.id || log.occurrence_id || log.metadata?.occurrence_id,
          photo_proof: log.photo_proof || log.metadata?.photo_proof,
          created_at: log.created_at,
          metadata: log.metadata,
        }));
        setEvents(mapped);
      }

      setSwaps(Array.isArray(swapsData) ? swapsData : []);
      setAbsences(Array.isArray(absencesData) ? absencesData : []);

      // Filter current user's active occurrences for the swap modal
      if (Array.isArray(occurrencesData)) {
        const myActive = occurrencesData
          .filter(
            (o: any) =>
              (o.assigned_to === user?.id ||
                o.assigned_member?.user?.id === user?.id ||
                o.assigned_member?.user === user?.id) &&
              (o.status === "active" || o.status === "upcoming")
          )
          .map((o: any) => ({
            id: o.id,
            title: o.chore?.title || `Chore #${o.chore?.id || o.id}`,
          }));
        setMyOccurrences(myActive);
      }

      // Fetch household members if household ID available
      if (household?.id) {
        try {
          const membersData = await api.households.members(household.id);
          if (Array.isArray(membersData)) {
            setHouseholdMembers(
              membersData.map((m: any) => ({
                id: m.user?.id || m.id,
                name: m.user?.display_name || m.user?.email || "Roommate",
              }))
            );
          }
        } catch {
          // ignore error fetching members
        }
      }
    } catch (err: any) {
      setError(err.message || "Failed to load activity logs.");
    } finally {
      setLoading(false);
    }
  }, [household?.id, user?.id]);

  React.useEffect(() => {
    loadData();
  }, [loadData]);

  // Swaps Handlers
  const handleCreateSwap = async (data: {
    proposer_occurrence_id: number;
    recipient_id: number;
    notes?: string;
  }) => {
    await api.chores.swaps.create(data);
    await loadData();
  };

  const handleAcceptSwap = async (swapId: number) => {
    await api.chores.swaps.accept(swapId);
    await loadData();
  };

  const handleDeclineSwap = async (swapId: number) => {
    await api.chores.swaps.decline(swapId);
    await loadData();
  };

  const handleCancelSwap = async (swapId: number) => {
    await api.chores.swaps.cancel(swapId);
    await loadData();
  };

  // Absences Handlers
  const handleCreateAbsence = async (data: {
    start_date: string;
    end_date: string;
    reason?: string;
  }) => {
    await api.absences.create(data);
    await loadData();
  };

  const handleVoteAbsence = async (absenceId: number, approved: boolean) => {
    await api.absences.vote(absenceId, approved);
    await loadData();
  };

  // Dispute Handler
  const handleOpenDispute = (occurrenceId: number, choreTitle: string) => {
    setDisputeTarget({ occurrenceId, title: choreTitle });
    setDisputeModalOpen(true);
  };

  const handleSubmitDispute = async (occurrenceId: number, reason: string) => {
    await api.chores.disputeOccurrence(occurrenceId, { reason });
    await loadData();
  };

  // Proof Handler
  const handleViewProof = (title: string, url: string) => {
    setProofData({ title, url });
    setProofModalOpen(true);
  };

  const filteredEvents = React.useMemo(() => {
    if (filter === "all") return events;
    return events.filter((e) => {
      if (filter === "completion") {
        return (
          e.event_type.includes("completed") ||
          e.event_type.includes("verified") ||
          e.event_type.includes("missed")
        );
      }
      if (filter === "swap") {
        return e.event_type.includes("swap");
      }
      if (filter === "absence") {
        return e.event_type.includes("absence") || e.event_type.includes("pause");
      }
      if (filter === "dispute") {
        return e.event_type.includes("dispute");
      }
      return true;
    });
  }, [events, filter]);

  const getEventBadge = (type: string) => {
    switch (type) {
      case "chore_completed":
      case "verification_approved":
        return <CheckCircle2 className="h-4 w-4 text-emerald-500" />;
      case "chore_missed":
        return <AlertCircle className="h-4 w-4 text-destructive" />;
      case "swap_completed":
      case "swap_accepted":
      case "swap_requested":
        return <Repeat className="h-4 w-4 text-blue-500" />;
      case "member_absence_approved":
      case "member_absence_requested":
      case "household_paused":
        return <Plane className="h-4 w-4 text-amber-500" />;
      case "dispute_opened":
      case "dispute_resolved":
        return <AlertTriangle className="h-4 w-4 text-purple-500" />;
      default:
        return <Activity className="h-4 w-4 text-muted-foreground" />;
    }
  };

  return (
    <div className="space-y-6" data-testid="activity-page">
      {/* Top Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Household Activity Feed</h1>
          <p className="text-sm text-muted-foreground">
            Complete audit trail of chore completions, proofs, personal swaps, absences, and disputes.
          </p>
        </div>

        <div className="flex items-center gap-2 flex-wrap">
          <Button
            variant="outline"
            size="sm"
            onClick={() => setSwapModalOpen(true)}
            className="gap-1.5"
            data-testid="open-swaps-modal-btn"
          >
            <ArrowLeftRight className="h-4 w-4" />
            <span>Swaps ({swaps.filter((s) => s.status === "pending").length})</span>
          </Button>

          <Button
            variant="outline"
            size="sm"
            onClick={() => setAbsenceModalOpen(true)}
            className="gap-1.5"
            data-testid="open-absences-modal-btn"
          >
            <Plane className="h-4 w-4" />
            <span>Absences / Pauses</span>
          </Button>

          <Button
            variant="ghost"
            size="sm"
            onClick={() => loadData()}
            className="gap-1.5"
            data-testid="refresh-activity-btn"
          >
            <RefreshCw className="h-4 w-4" />
          </Button>
        </div>
      </div>

      {error && (
        <div className="p-4 rounded-lg bg-destructive/10 text-destructive flex items-center gap-2 text-sm" data-testid="activity-error">
          <AlertCircle className="h-5 w-5 shrink-0" />
          <span>{error}</span>
          <Button variant="outline" size="sm" onClick={() => loadData()} className="ml-auto">
            Retry
          </Button>
        </div>
      )}

      {/* Filter Tabs */}
      <div className="flex items-center gap-2 overflow-x-auto pb-1" data-testid="activity-filters">
        {(["all", "completion", "swap", "absence", "dispute"] as const).map((cat) => (
          <Button
            key={cat}
            size="sm"
            variant={filter === cat ? "default" : "outline"}
            data-testid={`filter-${cat}`}
            onClick={() => setFilter(cat)}
            className="h-8 text-xs capitalize px-3 shrink-0"
          >
            {cat === "all" ? "All Activity" : cat}
          </Button>
        ))}
      </div>

      {/* Timeline Stream */}
      {loading ? (
        <div className="flex items-center justify-center min-h-[300px]" data-testid="activity-loading">
          <RefreshCw className="h-8 w-8 animate-spin text-primary" />
        </div>
      ) : filteredEvents.length === 0 ? (
        <div className="p-8 text-center rounded-lg border border-dashed bg-muted/20" data-testid="no-activity">
          <p className="font-semibold text-foreground">No events recorded yet.</p>
          <p className="text-xs text-muted-foreground mt-1">
            Chore completions, swaps, and member updates will appear here automatically.
          </p>
        </div>
      ) : (
        <div className="space-y-3" data-testid="events-timeline">
          {filteredEvents.map((evt) => {
            const isCompletion =
              evt.event_type === "chore_completed" ||
              evt.event_type === "chore_completed_late";
            const hasProof = !!evt.photo_proof;
            const canDispute =
              isCompletion && evt.occurrence_id && evt.actor_id !== user?.id;

            return (
              <Card
                key={evt.id}
                data-testid={`activity-item-${evt.id}`}
                className="shadow-sm hover:border-primary/40 transition-colors"
              >
                <CardContent className="p-4 flex items-start gap-3">
                  <div className="mt-1 p-2 rounded-full bg-muted/50 shrink-0">
                    {getEventBadge(evt.event_type)}
                  </div>

                  <div className="flex-1 min-w-0 space-y-1">
                    <div className="flex items-center justify-between gap-2">
                      <p className="text-sm font-medium text-foreground">
                        {evt.description}
                      </p>
                      <span className="text-[11px] text-muted-foreground shrink-0">
                        {new Date(evt.created_at).toLocaleDateString(undefined, {
                          month: "short",
                          day: "numeric",
                          hour: "2-digit",
                          minute: "2-digit",
                        })}
                      </span>
                    </div>

                    <div className="flex items-center gap-3 text-xs text-muted-foreground flex-wrap pt-1">
                      {evt.actor_name && (
                        <span>
                          By <strong className="text-foreground">{evt.actor_name}</strong>
                        </span>
                      )}

                      {hasProof && (
                        <button
                          type="button"
                          data-testid={`view-proof-btn-${evt.id}`}
                          onClick={() => handleViewProof(evt.chore_title || "Chore", evt.photo_proof!)}
                          className="text-primary hover:underline flex items-center gap-1 font-medium"
                        >
                          <ImageIcon className="h-3 w-3" />
                          <span>View Photo Proof</span>
                        </button>
                      )}

                      {canDispute && (
                        <button
                          type="button"
                          data-testid={`dispute-btn-${evt.id}`}
                          onClick={() => handleOpenDispute(evt.occurrence_id!, evt.chore_title || "Chore")}
                          className="text-destructive hover:underline flex items-center gap-1 font-medium ml-auto"
                        >
                          <AlertTriangle className="h-3 w-3" />
                          <span>Dispute</span>
                        </button>
                      )}
                    </div>
                  </div>
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}

      {/* Swaps Modal */}
      <SwapModal
        open={swapModalOpen}
        onOpenChange={setSwapModalOpen}
        myOccurrences={myOccurrences}
        members={householdMembers}
        swaps={swaps}
        currentUserId={user?.id}
        onCreateSwap={handleCreateSwap}
        onAcceptSwap={handleAcceptSwap}
        onDeclineSwap={handleDeclineSwap}
        onCancelSwap={handleCancelSwap}
      />

      {/* Absence Modal */}
      <AbsenceModal
        open={absenceModalOpen}
        onOpenChange={setAbsenceModalOpen}
        absences={absences}
        currentUserId={user?.id}
        onCreateAbsence={handleCreateAbsence}
        onVoteAbsence={handleVoteAbsence}
      />

      {/* Proof Modal */}
      <ProofModal
        open={proofModalOpen}
        onOpenChange={setProofModalOpen}
        title={proofData?.title || "Chore"}
        photoUrl={proofData?.url || null}
      />

      {/* Dispute Modal */}
      <DisputeModal
        open={disputeModalOpen}
        onOpenChange={setDisputeModalOpen}
        occurrenceId={disputeTarget?.occurrenceId || null}
        choreTitle={disputeTarget?.title || "Chore"}
        onSuccess={loadData}
        onSubmitDispute={handleSubmitDispute}
      />
    </div>
  );
}
