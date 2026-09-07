"use client";

import * as React from "react";
import {
  Users,
  Copy,
  Check,
  PauseCircle,
  PlayCircle,
  Shield,
  Clock,
  UserCheck,
  UserX,
  RefreshCw,
  AlertCircle,
  Share2,
} from "lucide-react";
import { useAuth } from "@/context/auth-context";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

interface HouseholdMemberData {
  id: number;
  user: {
    id: number;
    email: string;
    display_name: string;
  };
  role: string;
  status: "active" | "paused" | "departed";
  joined_at: string;
}

interface JoinRequestData {
  id: number;
  user: {
    id: number;
    email: string;
    display_name: string;
  };
  status: "pending" | "approved" | "rejected";
  created_at: string;
}

export default function HouseholdPage() {
  const { household, user, refreshState } = useAuth();

  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);

  const [members, setMembers] = React.useState<HouseholdMemberData[]>([]);
  const [joinRequests, setJoinRequests] = React.useState<JoinRequestData[]>([]);
  const [copiedCode, setCopiedCode] = React.useState(false);
  const [copiedLink, setCopiedLink] = React.useState(false);

  // Pause Modal
  const [pauseModalOpen, setPauseModalOpen] = React.useState(false);
  const [pauseReason, setPauseReason] = React.useState("");
  const [isPaused, setIsPaused] = React.useState(false);
  const [togglingPause, setTogglingPause] = React.useState(false);
  const [votingRequestId, setVotingRequestId] = React.useState<number | null>(null);

  const loadHouseholdData = React.useCallback(async () => {
    if (!household?.id) {
      setLoading(false);
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const [membersData, requestsData] = await Promise.all([
        api.households.members(household.id).catch(() => []),
        api.households.joinRequests(household.id).catch(() => []),
      ]);

      setMembers(Array.isArray(membersData) ? membersData : []);
      setJoinRequests(Array.isArray(requestsData) ? requestsData : []);
    } catch (err: any) {
      setError(err.message || "Failed to load household details.");
    } finally {
      setLoading(false);
    }
  }, [household?.id]);

  React.useEffect(() => {
    loadHouseholdData();
  }, [loadHouseholdData]);

  const handleCopyCode = () => {
    if (!household?.invite_code) return;
    navigator.clipboard.writeText(household.invite_code);
    setCopiedCode(true);
    setTimeout(() => setCopiedCode(false), 2000);
  };

  const handleCopyLink = () => {
    if (!household?.invite_code) return;
    const link = `${window.location.origin}/onboarding?code=${household.invite_code}`;
    navigator.clipboard.writeText(link);
    setCopiedLink(true);
    setTimeout(() => setCopiedLink(false), 2000);
  };

  const handleTogglePause = async () => {
    if (!household?.id) return;
    setTogglingPause(true);
    try {
      const nextPausedState = !isPaused;
      await api.households.pause(household.id, {
        paused: nextPausedState,
        pause_reason: nextPausedState ? pauseReason || "Holiday / Exam Break" : undefined,
      });
      setIsPaused(nextPausedState);
      setPauseModalOpen(false);
      setPauseReason("");
      await refreshState();
      await loadHouseholdData();
    } catch (err: any) {
      alert(err.message || "Failed to update household pause state.");
    } finally {
      setTogglingPause(false);
    }
  };

  const handleVoteJoinRequest = async (requestId: number, approved: boolean) => {
    if (!household?.id) return;
    setVotingRequestId(requestId);
    try {
      await api.households.voteJoinRequest(household.id, requestId, approved);
      await loadHouseholdData();
    } catch (err: any) {
      alert(err.message || "Failed to cast vote.");
    } finally {
      setVotingRequestId(null);
    }
  };

  if (!household) {
    return (
      <div className="max-w-xl mx-auto py-12 text-center space-y-4" data-testid="no-household-view">
        <Users className="mx-auto h-12 w-12 text-muted-foreground" />
        <h2 className="text-xl font-bold">No Household Connected</h2>
        <p className="text-sm text-muted-foreground">
          You are not currently part of an active household. Create or join one on the onboarding page.
        </p>
        <Button asChild>
          <a href="/onboarding">Go to Onboarding</a>
        </Button>
      </div>
    );
  }

  return (
    <div className="space-y-8" data-testid="household-page">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-bold tracking-tight" data-testid="household-title">
              {household.name}
            </h1>
            {isPaused ? (
              <Badge variant="destructive" className="text-xs">
                Rotations Paused
              </Badge>
            ) : (
              <Badge variant="secondary" className="bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300 text-xs">
                Active Rotation
              </Badge>
            )}
          </div>
          <p className="text-sm text-muted-foreground">
            Manage household policies, roommate memberships, invite codes, and approvals.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => loadHouseholdData()}
            className="gap-1.5"
            data-testid="refresh-household-btn"
          >
            <RefreshCw className="h-4 w-4" />
            <span>Refresh</span>
          </Button>

          <Button
            variant={isPaused ? "default" : "outline"}
            size="sm"
            onClick={() => {
              if (isPaused) {
                handleTogglePause();
              } else {
                setPauseModalOpen(true);
              }
            }}
            className="gap-1.5"
            data-testid="toggle-pause-btn"
          >
            {isPaused ? (
              <>
                <PlayCircle className="h-4 w-4" />
                <span>Resume Rotations</span>
              </>
            ) : (
              <>
                <PauseCircle className="h-4 w-4 text-amber-500" />
                <span>Pause Rotations</span>
              </>
            )}
          </Button>
        </div>
      </div>

      {error && (
        <div className="p-4 rounded-lg bg-destructive/10 text-destructive flex items-center gap-2 text-sm" data-testid="household-error">
          <AlertCircle className="h-5 w-5 shrink-0" />
          <span>{error}</span>
          <Button variant="outline" size="sm" onClick={() => loadHouseholdData()} className="ml-auto">
            Retry
          </Button>
        </div>
      )}

      {/* Invite Code Card */}
      <Card data-testid="invite-code-card" className="border shadow-sm bg-primary/5 border-primary/20">
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <div className="space-y-1">
              <CardTitle className="text-base font-semibold flex items-center gap-2">
                <Share2 className="h-4 w-4 text-primary" />
                Invite Roommates
              </CardTitle>
              <CardDescription className="text-xs">
                Share this unique invite code or link with housemates to join this household.
              </CardDescription>
            </div>
            <div className="flex items-center gap-2">
              <span className="font-mono text-sm font-bold bg-background px-3 py-1.5 rounded-md border text-foreground" data-testid="invite-code-display">
                {household.invite_code || "CHORE-ROOM"}
              </span>
              <Button
                size="sm"
                variant="outline"
                onClick={handleCopyCode}
                data-testid="copy-code-btn"
                className="gap-1.5 text-xs h-9"
              >
                {copiedCode ? <Check className="h-3.5 w-3.5 text-emerald-500" /> : <Copy className="h-3.5 w-3.5" />}
                <span>{copiedCode ? "Copied!" : "Copy Code"}</span>
              </Button>
              <Button
                size="sm"
                variant="default"
                onClick={handleCopyLink}
                data-testid="copy-link-btn"
                className="gap-1.5 text-xs h-9"
              >
                {copiedLink ? <Check className="h-3.5 w-3.5" /> : <Share2 className="h-3.5 w-3.5" />}
                <span>{copiedLink ? "Link Copied!" : "Share Link"}</span>
              </Button>
            </div>
          </div>
        </CardHeader>
      </Card>

      {/* Pending Approvals */}
      {joinRequests.length > 0 && (
        <div className="space-y-4" data-testid="pending-approvals-section">
          <div>
            <h2 className="text-lg font-semibold tracking-tight text-amber-600 dark:text-amber-400 flex items-center gap-2">
              <Clock className="h-5 w-5" />
              <span>Pending Roommate Approvals ({joinRequests.length})</span>
            </h2>
            <p className="text-xs text-muted-foreground">
              Unanimous household approval is required before new roommates enter the chore rotation.
            </p>
          </div>

          <div className="grid gap-3 sm:grid-cols-2" data-testid="join-requests-grid">
            {joinRequests.map((req) => (
              <Card key={req.id} data-testid={`join-request-card-${req.id}`} className="border border-amber-300 bg-amber-50/50 dark:bg-amber-950/20 shadow-sm">
                <CardHeader className="pb-2">
                  <div className="flex items-center justify-between">
                    <CardTitle className="text-sm font-semibold">
                      {req.user?.display_name || req.user?.email}
                    </CardTitle>
                    <Badge variant="outline" className="text-xs border-amber-400 text-amber-800 dark:text-amber-300">
                      Pending Vote
                    </Badge>
                  </div>
                  <CardDescription className="text-xs">
                    {req.user?.email} • Requested {new Date(req.created_at).toLocaleDateString()}
                  </CardDescription>
                </CardHeader>
                <CardFooter className="pt-2 border-t flex justify-end gap-2">
                  <Button
                    size="sm"
                    data-testid={`approve-join-btn-${req.id}`}
                    disabled={votingRequestId === req.id}
                    onClick={() => handleVoteJoinRequest(req.id, true)}
                    className="h-8 gap-1.5 text-xs"
                  >
                    <UserCheck className="h-3.5 w-3.5" />
                    <span>Approve</span>
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    data-testid={`reject-join-btn-${req.id}`}
                    disabled={votingRequestId === req.id}
                    onClick={() => handleVoteJoinRequest(req.id, false)}
                    className="h-8 gap-1.5 text-xs text-destructive hover:text-destructive"
                  >
                    <UserX className="h-3.5 w-3.5" />
                    <span>Reject</span>
                  </Button>
                </CardFooter>
              </Card>
            ))}
          </div>
        </div>
      )}

      {/* Member Directory */}
      <div className="space-y-4" data-testid="member-directory-section">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-lg font-semibold tracking-tight flex items-center gap-2">
              <Users className="h-5 w-5 text-primary" />
              <span>Roommate Directory ({members.length})</span>
            </h2>
            <p className="text-xs text-muted-foreground">
              All registered roommates currently sharing household chores.
            </p>
          </div>
        </div>

        {loading ? (
          <div className="flex items-center justify-center min-h-[150px]">
            <RefreshCw className="h-6 w-6 animate-spin text-primary" />
          </div>
        ) : members.length === 0 ? (
          <p className="text-xs text-muted-foreground py-6 text-center italic">
            No active members found.
          </p>
        ) : (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3" data-testid="members-grid">
            {members.map((mem) => (
              <Card key={mem.id} data-testid={`member-card-${mem.id}`} className="shadow-sm">
                <CardHeader className="pb-3">
                  <div className="flex items-start justify-between gap-2">
                    <div className="space-y-0.5">
                      <CardTitle className="text-base font-semibold">
                        {mem.user?.display_name || mem.user?.email}
                      </CardTitle>
                      <CardDescription className="text-xs">
                        {mem.user?.email}
                      </CardDescription>
                    </div>
                    <Badge
                      variant="outline"
                      className={`capitalize text-xs ${
                        mem.status === "active"
                          ? "text-emerald-600 border-emerald-500"
                          : mem.status === "paused"
                          ? "text-amber-600 border-amber-500"
                          : "text-muted-foreground"
                      }`}
                    >
                      {mem.status}
                    </Badge>
                  </div>
                </CardHeader>
                <CardContent className="pt-0 text-xs text-muted-foreground border-t pt-2 flex items-center justify-between">
                  <span className="flex items-center gap-1">
                    <Shield className="h-3 w-3 text-muted-foreground" />
                    Role: <span className="font-medium text-foreground capitalize">{mem.role || "Member"}</span>
                  </span>
                  <span>Joined {new Date(mem.joined_at).toLocaleDateString()}</span>
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </div>

      {/* Pause Confirmation Dialog */}
      <Dialog open={pauseModalOpen} onOpenChange={setPauseModalOpen}>
        <DialogContent className="sm:max-w-[420px]" data-testid="pause-confirm-dialog">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-amber-600 dark:text-amber-400">
              <PauseCircle className="h-5 w-5" />
              Pause Household Rotations
            </DialogTitle>
            <DialogDescription>
              Temporarily halt chore deadlines and rotation advancement for all roommates (e.g. during holidays or exam periods).
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-2 py-4">
            <label htmlFor="pause-reason" className="text-xs font-semibold text-foreground">
              Reason for pause (Optional)
            </label>
            <Input
              id="pause-reason"
              data-testid="pause-reason-input"
              placeholder="e.g., Winter Holiday Recess"
              value={pauseReason}
              onChange={(e) => setPauseReason(e.target.value)}
              className="text-xs"
            />
          </div>

          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => setPauseModalOpen(false)}
              disabled={togglingPause}
            >
              Cancel
            </Button>
            <Button
              type="button"
              variant="default"
              data-testid="confirm-pause-btn"
              onClick={handleTogglePause}
              disabled={togglingPause}
            >
              {togglingPause ? "Pausing..." : "Confirm Pause"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
