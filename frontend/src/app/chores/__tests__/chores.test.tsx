import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import ChoresPage from "../page";
import { CompletionModal } from "@/components/chores/completion-modal";
import { SuggestionModal } from "@/components/chores/suggestion-modal";
import { SuggestionList } from "@/components/chores/suggestion-list";
import { ChoreCard } from "@/components/chores/chore-card";
import { api } from "@/lib/api";
import * as authContext from "@/context/auth-context";

vi.mock("@/lib/api", () => ({
  api: {
    chores: {
      list: vi.fn(),
      occurrences: vi.fn(),
      completeOccurrence: vi.fn(),
      suggestions: {
        list: vi.fn(),
        create: vi.fn(),
        vote: vi.fn(),
      },
    },
  },
}));

describe("Chores Catalog and Modals", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.spyOn(authContext, "useAuth").mockReturnValue({
      user: { id: 1, email: "roomie@example.com", display_name: "Roomie 1" },
      household: { id: 1, name: "Flat 42", timezone: "UTC" },
      loading: false,
      isLoading: false,
      isAuthenticated: true,
      login: vi.fn(),
      register: vi.fn(),
      logout: vi.fn(),
      createHousehold: vi.fn(),
      joinHousehold: vi.fn(),
      refreshState: vi.fn(),
    });
  });

  describe("ChoresPage", () => {
    it("renders chore list and filters by search and effort", async () => {
      vi.mocked(api.chores.list).mockResolvedValue([
        {
          id: 1,
          title: "Dishes & Sink",
          description: "Wash and put away dishes",
          effort_level: "small",
          frequency: "daily",
        },
        {
          id: 2,
          title: "Deep Clean Bathroom",
          description: "Scrub shower and toilet",
          effort_level: "large",
          frequency: "weekly",
        },
      ]);
      vi.mocked(api.chores.occurrences).mockResolvedValue([
        {
          id: 101,
          chore: { id: 1 },
          status: "active",
          assigned_to: 1,
          due_date: "2099-01-01T00:00:00Z",
        },
      ]);
      vi.mocked(api.chores.suggestions.list).mockResolvedValue([]);

      render(<ChoresPage />);

      await waitFor(() => {
        expect(screen.getByText("Dishes & Sink")).toBeInTheDocument();
        expect(screen.getByText("Deep Clean Bathroom")).toBeInTheDocument();
      });

      // Filter by effort 'large'
      const largeBtn = screen.getByTestId("effort-filter-large");
      fireEvent.click(largeBtn);

      expect(screen.queryByText("Dishes & Sink")).not.toBeInTheDocument();
      expect(screen.getByText("Deep Clean Bathroom")).toBeInTheDocument();

      // Search by query
      const searchInput = screen.getByTestId("chores-search-input");
      fireEvent.change(searchInput, { target: { value: "toilet" } });
      expect(screen.getByText("Deep Clean Bathroom")).toBeInTheDocument();
    });

    it("switches to anonymous proposals tab", async () => {
      vi.mocked(api.chores.list).mockResolvedValue([]);
      vi.mocked(api.chores.occurrences).mockResolvedValue([]);
      vi.mocked(api.chores.suggestions.list).mockResolvedValue([
        {
          id: 5,
          title: "Organize spice cabinet",
          description: "Sort spices alphabetically",
          suggested_frequency: "monthly",
          suggested_effort: "small",
          status: "pending",
          upvotes_count: 3,
          downvotes_count: 0,
        },
      ]);

      render(<ChoresPage />);

      await waitFor(() => {
        expect(screen.getByTestId("tab-suggestions")).toBeInTheDocument();
      });

      fireEvent.click(screen.getByTestId("tab-suggestions"));
      expect(screen.getByText("Organize spice cabinet")).toBeInTheDocument();
      expect(screen.getByText("Sort spices alphabetically")).toBeInTheDocument();
    });
  });

  describe("CompletionModal", () => {
    it("submits completion notes and photo proof", async () => {
      const mockCompleteApi = vi.fn().mockResolvedValue({ id: 101, status: "completed" });
      const mockSuccess = vi.fn();
      const mockOpenChange = vi.fn();

      render(
        <CompletionModal
          open={true}
          onOpenChange={mockOpenChange}
          occurrenceId={101}
          choreTitle="Clean Kitchen"
          onSuccess={mockSuccess}
          onCompleteApi={mockCompleteApi}
        />
      );

      expect(screen.getByText(/Clean Kitchen/)).toBeInTheDocument();

      // Add notes
      const notesInput = screen.getByTestId("completion-notes-input");
      fireEvent.change(notesInput, { target: { value: "Replaced sponges and swept floor" } });

      // Submit
      const submitBtn = screen.getByTestId("submit-completion-button");
      fireEvent.click(submitBtn);

      await waitFor(() => {
        expect(mockCompleteApi).toHaveBeenCalledWith(101, {
          notes: "Replaced sponges and swept floor",
          photo_proof: undefined,
        });
        expect(mockSuccess).toHaveBeenCalled();
        expect(mockOpenChange).toHaveBeenCalledWith(false);
      });
    });
  });

  describe("SuggestionModal", () => {
    it("validates and submits anonymous suggestion", async () => {
      const mockCreateApi = vi.fn().mockResolvedValue({ id: 10 });
      const mockSuccess = vi.fn();
      const mockOpenChange = vi.fn();

      render(
        <SuggestionModal
          open={true}
          onOpenChange={mockOpenChange}
          onSuccess={mockSuccess}
          onCreateApi={mockCreateApi}
        />
      );

      const titleInput = screen.getByTestId("suggestion-title-input");
      fireEvent.change(titleInput, { target: { value: "Wipe down baseboards" } });

      const descInput = screen.getByTestId("suggestion-description-input");
      fireEvent.change(descInput, { target: { value: "Hallway and living room baseboards" } });

      const submitBtn = screen.getByTestId("submit-suggestion-button");
      fireEvent.click(submitBtn);

      await waitFor(() => {
        expect(mockCreateApi).toHaveBeenCalledWith({
          title: "Wipe down baseboards",
          description: "Hallway and living room baseboards",
          suggested_frequency: "weekly",
          suggested_effort: "medium",
        });
        expect(mockSuccess).toHaveBeenCalled();
        expect(mockOpenChange).toHaveBeenCalledWith(false);
      });
    });
  });

  describe("SuggestionList and Voting", () => {
    it("handles voting interactions", async () => {
      const mockVote = vi.fn().mockResolvedValue({});
      const suggestions = [
        {
          id: 7,
          title: "Clean refrigerator coils",
          suggested_frequency: "monthly",
          suggested_effort: "large",
          status: "pending" as const,
          upvotes_count: 2,
          downvotes_count: 1,
        },
      ];

      render(<SuggestionList suggestions={suggestions} onVote={mockVote} />);

      expect(screen.getByText("Clean refrigerator coils")).toBeInTheDocument();

      const upvoteBtn = screen.getByTestId("upvote-button-7");
      fireEvent.click(upvoteBtn);
      expect(mockVote).toHaveBeenCalledWith(7, "up");

      const downvoteBtn = screen.getByTestId("downvote-button-7");
      fireEvent.click(downvoteBtn);
      expect(mockVote).toHaveBeenCalledWith(7, "down");
    });
  });
});
