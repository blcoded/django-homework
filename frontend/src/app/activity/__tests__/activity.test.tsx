import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import ActivityPage from "../page";
import { SwapModal } from "@/components/activity/swap-modal";
import { AbsenceModal } from "@/components/activity/absence-modal";
import { DisputeModal } from "@/components/activity/dispute-modal";
import { api } from "@/lib/api";
import * as authContext from "@/context/auth-context";

vi.mock("@/lib/api", () => ({
  api: {
    activity: {
      list: vi.fn(),
    },
    chores: {
      occurrences: vi.fn(),
      disputeOccurrence: vi.fn(),
      swaps: {
        list: vi.fn(),
        create: vi.fn(),
        accept: vi.fn(),
        decline: vi.fn(),
        cancel: vi.fn(),
      },
    },
    absences: {
      list: vi.fn(),
      create: vi.fn(),
      vote: vi.fn(),
    },
    households: {
      members: vi.fn(),
    },
  },
}));

describe("Activity Feed, Swaps, Absences, and Disputes", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.spyOn(authContext, "useAuth").mockReturnValue({
      user: { id: 1, email: "charlie@example.com", display_name: "Charlie" },
      household: { id: 1, name: "Cozy Flat", timezone: "UTC" },
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

  describe("ActivityPage", () => {
    it("renders chronological activity feed and filters by category", async () => {
      vi.mocked(api.activity.list).mockResolvedValue([
        {
          id: 1,
          event_type: "chore_completed",
          description: "Dana completed Kitchen Deep Clean",
          actor: { id: 2, display_name: "Dana" },
          chore_title: "Kitchen Deep Clean",
          occurrence_id: 10,
          photo_proof: "data:image/png;base64,mockphoto",
          created_at: "2026-03-01T12:00:00Z",
        },
        {
          id: 2,
          event_type: "swap_accepted",
          description: "Swap accepted between Charlie and Dana",
          actor: { id: 1, display_name: "Charlie" },
          created_at: "2026-03-01T13:00:00Z",
        },
      ]);
      vi.mocked(api.chores.swaps.list).mockResolvedValue([]);
      vi.mocked(api.absences.list).mockResolvedValue([]);
      vi.mocked(api.chores.occurrences).mockResolvedValue([]);

      render(<ActivityPage />);

      await waitFor(() => {
        expect(screen.getByText("Dana completed Kitchen Deep Clean")).toBeInTheDocument();
        expect(screen.getByText("Swap accepted between Charlie and Dana")).toBeInTheDocument();
      });

      // Filter by swap
      const swapFilterBtn = screen.getByTestId("filter-swap");
      fireEvent.click(swapFilterBtn);

      expect(screen.queryByText("Dana completed Kitchen Deep Clean")).not.toBeInTheDocument();
      expect(screen.getByText("Swap accepted between Charlie and Dana")).toBeInTheDocument();

      // Check view proof button exists for Dana's completion
      const allFilterBtn = screen.getByTestId("filter-all");
      fireEvent.click(allFilterBtn);

      const viewProofBtn = screen.getByTestId("view-proof-btn-1");
      expect(viewProofBtn).toBeInTheDocument();
      fireEvent.click(viewProofBtn);

      expect(screen.getByTestId("proof-modal")).toBeInTheDocument();
    });

    it("opens dispute modal on eligible completion", async () => {
      vi.mocked(api.activity.list).mockResolvedValue([
        {
          id: 3,
          event_type: "chore_completed",
          description: "Sam completed Recycling",
          actor: { id: 3, display_name: "Sam" },
          chore_title: "Recycling",
          occurrence_id: 12,
          created_at: "2026-03-01T12:00:00Z",
        },
      ]);
      vi.mocked(api.chores.swaps.list).mockResolvedValue([]);
      vi.mocked(api.absences.list).mockResolvedValue([]);
      vi.mocked(api.chores.occurrences).mockResolvedValue([]);

      render(<ActivityPage />);

      await waitFor(() => {
        expect(screen.getByTestId("dispute-btn-3")).toBeInTheDocument();
      });

      fireEvent.click(screen.getByTestId("dispute-btn-3"));
      expect(screen.getByTestId("dispute-modal")).toBeInTheDocument();
      expect(screen.getByText(/Open Completion Dispute/)).toBeInTheDocument();
    });
  });

  describe("SwapModal", () => {
    it("handles swap proposal and acceptance", async () => {
      const mockCreateSwap = vi.fn().mockResolvedValue(undefined);
      const mockAcceptSwap = vi.fn().mockResolvedValue(undefined);
      const mockDeclineSwap = vi.fn().mockResolvedValue(undefined);
      const mockCancelSwap = vi.fn().mockResolvedValue(undefined);

      const swaps = [
        {
          id: 1,
          proposer: { id: 2, email: "dana@example.com", display_name: "Dana" },
          recipient: { id: 1, email: "charlie@example.com", display_name: "Charlie" },
          proposer_occurrence: { id: 10, chore: { id: 1, title: "Bathroom" } },
          status: "pending" as const,
          created_at: "2026-03-01T10:00:00Z",
        },
      ];

      render(
        <SwapModal
          open={true}
          onOpenChange={vi.fn()}
          myOccurrences={[{ id: 20, title: "Kitchen" }]}
          members={[{ id: 2, name: "Dana" }]}
          swaps={swaps}
          currentUserId={1}
          onCreateSwap={mockCreateSwap}
          onAcceptSwap={mockAcceptSwap}
          onDeclineSwap={mockDeclineSwap}
          onCancelSwap={mockCancelSwap}
        />
      );

      // Charlie is recipient of swap 1 -> can accept
      const acceptBtn = screen.getByTestId("accept-swap-btn-1");
      fireEvent.click(acceptBtn);
      expect(mockAcceptSwap).toHaveBeenCalledWith(1);

      // Switch to propose tab
      fireEvent.click(screen.getByTestId("tab-swap-propose"));
      expect(screen.getByTestId("swap-form")).toBeInTheDocument();

      fireEvent.change(screen.getByTestId("swap-occurrence-select"), { target: { value: "20" } });
      fireEvent.change(screen.getByTestId("swap-recipient-select"), { target: { value: "2" } });
      fireEvent.change(screen.getByTestId("swap-notes-input"), { target: { value: "Busy Friday" } });

      fireEvent.click(screen.getByTestId("submit-swap-button"));
      await waitFor(() => {
        expect(mockCreateSwap).toHaveBeenCalledWith({
          proposer_occurrence_id: 20,
          recipient_id: 2,
          notes: "Busy Friday",
        });
      });
    });
  });

  describe("AbsenceModal", () => {
    it("submits absence request and handles voting", async () => {
      const mockCreateAbsence = vi.fn().mockResolvedValue(undefined);
      const mockVoteAbsence = vi.fn().mockResolvedValue(undefined);

      const absences = [
        {
          id: 5,
          member: { id: 2, user: { id: 2, email: "dana@example.com", display_name: "Dana" } },
          start_date: "2026-03-10",
          end_date: "2026-03-15",
          reason: "Vacation",
          status: "pending" as const,
        },
      ];

      render(
        <AbsenceModal
          open={true}
          onOpenChange={vi.fn()}
          absences={absences}
          currentUserId={1}
          onCreateAbsence={mockCreateAbsence}
          onVoteAbsence={mockVoteAbsence}
        />
      );

      // Approve Dana's absence
      const approveBtn = screen.getByTestId("approve-absence-btn-5");
      fireEvent.click(approveBtn);
      expect(mockVoteAbsence).toHaveBeenCalledWith(5, true);

      // Switch to request tab
      fireEvent.click(screen.getByTestId("tab-absence-request"));
      fireEvent.change(screen.getByTestId("absence-start-input"), { target: { value: "2026-04-01" } });
      fireEvent.change(screen.getByTestId("absence-end-input"), { target: { value: "2026-04-07" } });
      fireEvent.change(screen.getByTestId("absence-reason-input"), { target: { value: "Conference" } });

      fireEvent.click(screen.getByTestId("submit-absence-button"));
      await waitFor(() => {
        expect(mockCreateAbsence).toHaveBeenCalledWith({
          start_date: "2026-04-01",
          end_date: "2026-04-07",
          reason: "Conference",
        });
      });
    });
  });

  describe("DisputeModal", () => {
    it("validates and submits dispute", async () => {
      const mockSubmitDispute = vi.fn().mockResolvedValue({});
      const mockSuccess = vi.fn();
      const mockOpenChange = vi.fn();

      render(
        <DisputeModal
          open={true}
          onOpenChange={mockOpenChange}
          occurrenceId={10}
          choreTitle="Trash & Bins"
          onSuccess={mockSuccess}
          onSubmitDispute={mockSubmitDispute}
        />
      );

      const reasonInput = screen.getByTestId("dispute-reason-input");
      fireEvent.change(reasonInput, { target: { value: "Recycling bin was not put out" } });

      const submitBtn = screen.getByTestId("submit-dispute-button");
      fireEvent.click(submitBtn);

      await waitFor(() => {
        expect(mockSubmitDispute).toHaveBeenCalledWith(10, "Recycling bin was not put out");
        expect(mockSuccess).toHaveBeenCalled();
        expect(mockOpenChange).toHaveBeenCalledWith(false);
      });
    });
  });
});
