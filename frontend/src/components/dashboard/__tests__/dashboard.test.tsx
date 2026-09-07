import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { MyChores, ChoreOccurrenceItem } from "../my-chores";
import { HouseholdOverview } from "../household-overview";
import { ActivityTicker } from "../activity-ticker";
import DashboardPage from "@/app/page";
import * as authContext from "@/context/auth-context";
import { api } from "@/lib/api";

vi.mock("@/lib/api", () => ({
  api: {
    chores: {
      occurrences: vi.fn(),
      completeOccurrence: vi.fn(),
    },
    stats: {
      household: vi.fn(),
      personal: vi.fn(),
    },
    activity: {
      list: vi.fn(),
    },
  },
}));

describe("Dashboard Components", () => {
  describe("MyChores Component", () => {
    it("renders empty caught up state when no active chores", () => {
      render(<MyChores activeChores={[]} />);
      expect(screen.getByText("You are all caught up!")).toBeInTheDocument();
    });

    it("renders active chore cards and handles 1-tap completion", () => {
      const mockComplete = vi.fn();
      const mockChores: ChoreOccurrenceItem[] = [
        {
          id: 101,
          chore: { id: 1, title: "Take out recycling", effort_level: "small" },
          status: "active",
          scheduled_start: "2026-03-01T00:00:00Z",
          due_date: "2099-03-05T00:00:00Z",
        },
        {
          id: 102,
          chore: { id: 2, title: "Deep clean bathroom", effort_level: "large" },
          status: "active",
          scheduled_start: "2026-02-01T00:00:00Z",
          due_date: "2026-02-10T00:00:00Z", // overdue
        },
      ];

      const nextUp: ChoreOccurrenceItem = {
        id: 103,
        chore: { id: 3, title: "Mop kitchen floor", effort_level: "medium" },
        status: "upcoming",
        scheduled_start: "2026-04-01T00:00:00Z",
        due_date: null,
      };

      render(
        <MyChores
          activeChores={mockChores}
          nextUpChore={nextUp}
          onComplete={mockComplete}
        />
      );

      expect(screen.getByText("Take out recycling")).toBeInTheDocument();
      expect(screen.getByText("Small (1 pt)")).toBeInTheDocument();
      expect(screen.getByText("Deep clean bathroom")).toBeInTheDocument();
      expect(screen.getByText("Large (3 pts)")).toBeInTheDocument();
      expect(screen.getByText("Past Due / Missed")).toBeInTheDocument();

      // Next up card
      expect(screen.getByTestId("next-up-card")).toBeInTheDocument();
      expect(screen.getByText("Mop kitchen floor")).toBeInTheDocument();

      // Click complete button
      const completeBtn = screen.getByTestId("complete-button-101");
      fireEvent.click(completeBtn);
      expect(mockComplete).toHaveBeenCalledWith(101);
    });
  });

  describe("HouseholdOverview Component", () => {
    it("renders household stats and unassigned chore alert when count > 0", () => {
      render(
        <HouseholdOverview
          summary={{
            household_name: "Baker Street 221B",
            total_active: 8,
            total_completed: 42,
            unassigned_count: 2,
            completion_rate: 95.5,
          }}
        />
      );

      expect(screen.getByText(/Baker Street 221B/)).toBeInTheDocument();
      expect(screen.getByTestId("unassigned-alert-banner")).toBeInTheDocument();
      expect(screen.getByText("2 unassigned chores")).toBeInTheDocument();
      expect(screen.getByText("8")).toBeInTheDocument();
      expect(screen.getByText("42")).toBeInTheDocument();
      expect(screen.getByText("96%")).toBeInTheDocument();
    });

    it("hides unassigned alert when count is 0", () => {
      render(
        <HouseholdOverview
          summary={{
            household_name: "Baker Street 221B",
            total_active: 6,
            total_completed: 20,
            unassigned_count: 0,
            completion_rate: 100,
          }}
        />
      );

      expect(screen.queryByTestId("unassigned-alert-banner")).not.toBeInTheDocument();
    });
  });

  describe("ActivityTicker Component", () => {
    it("renders compact list of recent activities", () => {
      const events = [
        {
          id: 1,
          event_type: "chore_completed",
          description: "Alex completed Kitchen Dishes",
          user_name: "Alex",
          created_at: "2026-03-01T10:00:00Z",
        },
        {
          id: 2,
          event_type: "swap_completed",
          description: "Jordan swapped Trash Duty with Taylor",
          user_name: "Jordan",
          created_at: "2026-03-01T12:00:00Z",
        },
      ];

      render(<ActivityTicker events={events} />);

      expect(screen.getByText("Live Activity")).toBeInTheDocument();
      expect(screen.getByText("Alex completed Kitchen Dishes")).toBeInTheDocument();
      expect(screen.getByText("Jordan swapped Trash Duty with Taylor")).toBeInTheDocument();
    });

    it("renders placeholder when events list is empty", () => {
      render(<ActivityTicker events={[]} />);
      expect(
        screen.getByText("No recent household events recorded yet.")
      ).toBeInTheDocument();
    });
  });

  describe("DashboardPage Integration", () => {
    beforeEach(() => {
      vi.clearAllMocks();
    });

    it("renders guest welcome when unauthenticated", () => {
      vi.spyOn(authContext, "useAuth").mockReturnValue({
        user: null,
        token: null,
        isAuthenticated: false,
        isLoading: false,
        login: vi.fn(),
        register: vi.fn(),
        logout: vi.fn(),
        refreshUser: vi.fn(),
      });

      render(<DashboardPage />);
      expect(screen.getByTestId("guest-welcome")).toBeInTheDocument();
      expect(screen.getByTestId("guest-login-btn")).toBeInTheDocument();
    });

    it("renders dashboard when authenticated and loads data", async () => {
      vi.spyOn(authContext, "useAuth").mockReturnValue({
        user: { id: 1, email: "alex@example.com", display_name: "Alex Smith" },
        token: "token-123",
        isAuthenticated: true,
        isLoading: false,
        login: vi.fn(),
        register: vi.fn(),
        logout: vi.fn(),
        refreshUser: vi.fn(),
      });

      vi.mocked(api.chores.occurrences).mockResolvedValue([
        {
          id: 10,
          assigned_to: 1,
          status: "active",
          chore: { id: 1, title: "Vacuum Living Room", effort_level: "medium" },
          scheduled_start: "2026-03-01T00:00:00Z",
          due_date: "2099-03-05T00:00:00Z",
        },
      ]);
      vi.mocked(api.stats.household).mockResolvedValue({
        household_name: "Sunny Flat",
        total_active_chores: 5,
        completed_count: 15,
        unassigned_count: 0,
        completion_rate: 90,
      });
      vi.mocked(api.stats.personal).mockResolvedValue({
        current_streak: 4,
        longest_streak: 7,
      });
      vi.mocked(api.activity.list).mockResolvedValue([]);

      render(<DashboardPage />);

      await waitFor(() => {
        expect(screen.getByTestId("welcome-heading")).toHaveTextContent(
          "Welcome back, Alex Smith!"
        );
      });

      expect(screen.getByText("Vacuum Living Room")).toBeInTheDocument();
      expect(screen.getByTestId("streak-count")).toHaveTextContent("4");
    });
  });
});
