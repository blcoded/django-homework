import { render, screen, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import StatsPage from "../page";
import { api } from "@/lib/api";
import * as authContext from "@/context/auth-context";

vi.mock("@/lib/api", () => ({
  api: {
    stats: {
      personal: vi.fn(),
      household: vi.fn(),
    },
  },
}));

describe("Stats and Streaks Page", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.spyOn(authContext, "useAuth").mockReturnValue({
      user: { id: 1, email: "taylor@example.com", display_name: "Taylor" },
      household: { id: 1, name: "Sunset Suite", timezone: "UTC" },
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

  it("renders personal streaks, unlocked milestone badges, and non-competitive household roster", async () => {
    vi.mocked(api.stats.personal).mockResolvedValue({
      display_name: "Taylor",
      current_streak: 8,
      longest_streak: 12,
      on_time_completions: 25,
      late_completions: 2,
      total_completed: 27,
      completion_rate: 96.2,
      milestones: [
        {
          badge_key: "streak_5",
          name: "5-Streak Warrior",
          description: "Completed 5 consecutive chores on-time",
          icon: "🔥",
          is_unlocked: true,
          unlocked_at: "2026-03-01T10:00:00Z",
        },
        {
          badge_key: "century_100",
          name: "Chore Centurion",
          description: "Completed 100 chores",
          icon: "🏛️",
          is_unlocked: false,
          unlocked_at: null,
        },
      ],
    });

    vi.mocked(api.stats.household).mockResolvedValue({
      household_name: "Sunset Suite",
      total_completed: 64,
      completion_rate: 94.0,
      members: [
        {
          user_id: 2,
          display_name: "Alex",
          total_completed: 22,
          on_time_completions: 20,
          current_streak: 4,
          completion_rate: 91.0,
        },
        {
          user_id: 1,
          display_name: "Taylor",
          total_completed: 27,
          on_time_completions: 25,
          current_streak: 8,
          completion_rate: 96.2,
        },
      ],
    });

    render(<StatsPage />);

    await waitFor(() => {
      // Streaks
      expect(screen.getByText("8")).toBeInTheDocument();
      expect(screen.getByText("12")).toBeInTheDocument();
      expect(screen.getByText("27")).toBeInTheDocument();
      expect(screen.getByText("96%")).toBeInTheDocument();
    });

    // Milestone badges
    expect(screen.getByText("5-Streak Warrior")).toBeInTheDocument();
    expect(screen.getByText("Chore Centurion")).toBeInTheDocument();
    expect(screen.getByText(/1 \/ 2 Unlocked/)).toBeInTheDocument();

    // Non-competitive principles & alphabetical roster
    expect(screen.getByText("Non-Competitive Household Principle")).toBeInTheDocument();
    expect(screen.getByText("Alex")).toBeInTheDocument();
    expect(screen.getByText("Taylor")).toBeInTheDocument();
  });
});
