"use client";

import * as React from "react";
import { Plus, Search, Filter, Lightbulb, CheckCircle2, RefreshCw, AlertCircle } from "lucide-react";
import { useAuth } from "@/context/auth-context";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { ChoreCard, ChoreItem } from "@/components/chores/chore-card";
import { CompletionModal } from "@/components/chores/completion-modal";
import { SuggestionModal } from "@/components/chores/suggestion-modal";
import { SuggestionList, SuggestionItem } from "@/components/chores/suggestion-list";

export default function ChoresPage() {
  const { user, isAuthenticated } = useAuth();

  const [activeTab, setActiveTab] = React.useState<"catalog" | "suggestions">("catalog");
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);

  const [chores, setChores] = React.useState<ChoreItem[]>([]);
  const [suggestions, setSuggestions] = React.useState<SuggestionItem[]>([]);

  // Filtering
  const [searchQuery, setSearchQuery] = React.useState("");
  const [effortFilter, setEffortFilter] = React.useState<"all" | "small" | "medium" | "large">("all");

  // Modals state
  const [completionModalOpen, setCompletionModalOpen] = React.useState(false);
  const [selectedOccurrence, setSelectedOccurrence] = React.useState<{ id: number; title: string } | null>(null);

  const [suggestionModalOpen, setSuggestionModalOpen] = React.useState(false);
  const [votingId, setVotingId] = React.useState<number | null>(null);

  const loadData = React.useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [choresData, occurrencesData, suggestionsData] = await Promise.all([
        api.chores.list().catch(() => []),
        api.chores.occurrences().catch(() => []),
        api.chores.suggestions.list().catch(() => []),
      ]);

      // Map active occurrences to chores
      const occurrencesList = Array.isArray(occurrencesData) ? occurrencesData : [];
      const mappedChores: ChoreItem[] = (Array.isArray(choresData) ? choresData : []).map((chore: any) => {
        const occ = occurrencesList.find(
          (o: any) =>
            o.chore?.id === chore.id &&
            (o.status === "active" || o.status === "upcoming" || o.status === "unassigned")
        );

        return {
          id: chore.id,
          title: chore.title,
          description: chore.description,
          effort_level: chore.effort_level,
          frequency: chore.frequency || "weekly",
          is_active: chore.is_active,
          active_occurrence: occ
            ? {
                id: occ.id,
                assigned_member_name: occ.assigned_member?.user?.display_name || occ.assigned_to_display_name,
                assigned_to_user_id: occ.assigned_member?.user?.id || occ.assigned_to,
                status: occ.status,
                due_date: occ.due_date,
              }
            : null,
        };
      });

      setChores(mappedChores);
      setSuggestions(Array.isArray(suggestionsData) ? suggestionsData : []);
    } catch (err: any) {
      setError(err.message || "Failed to load chores data.");
    } finally {
      setLoading(false);
    }
  }, []);

  React.useEffect(() => {
    loadData();
  }, [loadData]);

  const handleOpenComplete = (occurrenceId: number, choreTitle: string) => {
    setSelectedOccurrence({ id: occurrenceId, title: choreTitle });
    setCompletionModalOpen(true);
  };

  const handleVote = async (suggestionId: number, voteType: "up" | "down") => {
    try {
      setVotingId(suggestionId);
      await api.chores.suggestions.vote(suggestionId, voteType);
      // Optimistic update of suggestion vote count
      setSuggestions((prev) =>
        prev.map((s) => {
          if (s.id !== suggestionId) return s;
          const upDiff = voteType === "up" ? 1 : 0;
          const downDiff = voteType === "down" ? 1 : 0;
          return {
            ...s,
            upvotes_count: s.upvotes_count + upDiff,
            downvotes_count: s.downvotes_count + downDiff,
            my_vote: voteType,
          };
        })
      );
    } catch (err: any) {
      alert(err.message || "Failed to record vote.");
    } finally {
      setVotingId(null);
    }
  };

  const filteredChores = React.useMemo(() => {
    return chores.filter((c) => {
      const matchesSearch =
        c.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
        (c.description && c.description.toLowerCase().includes(searchQuery.toLowerCase()));
      const matchesEffort = effortFilter === "all" || c.effort_level === effortFilter;
      return matchesSearch && matchesEffort;
    });
  }, [chores, searchQuery, effortFilter]);

  return (
    <div className="space-y-6" data-testid="chores-page">
      {/* Top Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Household Chores</h1>
          <p className="text-sm text-muted-foreground">
            Explore shared responsibilities, complete tasks with photo proof, and vote on new chore suggestions.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => loadData()}
            className="gap-1.5"
            data-testid="refresh-chores-btn"
          >
            <RefreshCw className="h-4 w-4" />
            <span className="hidden sm:inline">Refresh</span>
          </Button>

          <Button
            size="sm"
            onClick={() => setSuggestionModalOpen(true)}
            className="gap-1.5"
            data-testid="open-suggestion-btn"
          >
            <Lightbulb className="h-4 w-4" />
            <span>Propose Chore</span>
          </Button>
        </div>
      </div>

      {error && (
        <div className="p-4 rounded-lg bg-destructive/10 text-destructive flex items-center gap-2 text-sm" data-testid="chores-error">
          <AlertCircle className="h-5 w-5 shrink-0" />
          <span>{error}</span>
          <Button variant="outline" size="sm" onClick={() => loadData()} className="ml-auto">
            Retry
          </Button>
        </div>
      )}

      {/* Tabs */}
      <div className="flex border-b border-border text-sm">
        <button
          type="button"
          data-testid="tab-catalog"
          onClick={() => setActiveTab("catalog")}
          className={`px-4 py-2 font-medium border-b-2 transition-colors -mb-px ${
            activeTab === "catalog"
              ? "border-primary text-primary"
              : "border-transparent text-muted-foreground hover:text-foreground"
          }`}
        >
          Chores Catalog ({chores.length})
        </button>
        <button
          type="button"
          data-testid="tab-suggestions"
          onClick={() => setActiveTab("suggestions")}
          className={`px-4 py-2 font-medium border-b-2 transition-colors -mb-px flex items-center gap-1.5 ${
            activeTab === "suggestions"
              ? "border-primary text-primary"
              : "border-transparent text-muted-foreground hover:text-foreground"
          }`}
        >
          <Lightbulb className="h-3.5 w-3.5" />
          <span>Anonymous Proposals ({suggestions.length})</span>
        </button>
      </div>

      {loading ? (
        <div className="flex items-center justify-center min-h-[300px]" data-testid="chores-loading">
          <RefreshCw className="h-8 w-8 animate-spin text-primary" />
        </div>
      ) : activeTab === "catalog" ? (
        <div className="space-y-6">
          {/* Filters Bar */}
          <div className="flex flex-col sm:flex-row gap-3 items-stretch sm:items-center justify-between">
            <div className="relative flex-1 max-w-sm">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder="Search chores..."
                data-testid="chores-search-input"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-9 text-xs"
              />
            </div>

            <div className="flex items-center gap-1.5 flex-wrap" data-testid="effort-filters">
              <span className="text-xs text-muted-foreground mr-1 flex items-center gap-1">
                <Filter className="h-3 w-3" /> Effort:
              </span>
              {(["all", "small", "medium", "large"] as const).map((lvl) => (
                <Button
                  key={lvl}
                  size="sm"
                  variant={effortFilter === lvl ? "default" : "outline"}
                  data-testid={`effort-filter-${lvl}`}
                  onClick={() => setEffortFilter(lvl)}
                  className="h-8 text-xs capitalize px-3"
                >
                  {lvl === "all" ? "All Levels" : lvl}
                </Button>
              ))}
            </div>
          </div>

          {/* Chores Grid */}
          {filteredChores.length === 0 ? (
            <div className="p-8 text-center rounded-lg border border-dashed bg-muted/20" data-testid="no-chores-found">
              <p className="font-medium text-foreground">No chores match your criteria.</p>
              <p className="text-xs text-muted-foreground mt-1">
                Try clearing filters or search keywords.
              </p>
            </div>
          ) : (
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3" data-testid="chores-grid">
              {filteredChores.map((chore) => (
                <ChoreCard
                  key={chore.id}
                  chore={chore}
                  currentUserId={user?.id}
                  onOpenCompleteModal={handleOpenComplete}
                />
              ))}
            </div>
          )}
        </div>
      ) : (
        /* Anonymous Proposals Tab */
        <div className="space-y-6" data-testid="suggestions-tab-content">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-lg font-semibold tracking-tight">Household Proposals</h2>
              <p className="text-xs text-muted-foreground">
                Vote on chores submitted anonymously by roommates. High approval triggers automatic rotation adoption.
              </p>
            </div>
            <Button
              size="sm"
              onClick={() => setSuggestionModalOpen(true)}
              className="gap-1.5"
              data-testid="propose-chore-btn-tab"
            >
              <Plus className="h-4 w-4" />
              <span>Propose Chore</span>
            </Button>
          </div>

          <SuggestionList
            suggestions={suggestions}
            onVote={handleVote}
            votingId={votingId}
          />
        </div>
      )}

      {/* Completion Modal */}
      <CompletionModal
        open={completionModalOpen}
        onOpenChange={setCompletionModalOpen}
        occurrenceId={selectedOccurrence?.id || null}
        choreTitle={selectedOccurrence?.title || "Chore"}
        onSuccess={loadData}
        onCompleteApi={(id, data) => api.chores.completeOccurrence(id, data)}
      />

      {/* Anonymous Chore Suggestion Modal */}
      <SuggestionModal
        open={suggestionModalOpen}
        onOpenChange={setSuggestionModalOpen}
        onSuccess={loadData}
        onCreateApi={(data) => api.chores.suggestions.create(data)}
      />
    </div>
  );
}
