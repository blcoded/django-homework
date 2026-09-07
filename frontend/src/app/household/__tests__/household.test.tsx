import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import HouseholdPage from "../page";
import { api } from "@/lib/api";
import * as authContext from "@/context/auth-context";

vi.mock("@/lib/api", () => ({
  api: {
    households: {
      members: vi.fn(),
      joinRequests: vi.fn(),
      voteJoinRequest: vi.fn(),
      pause: vi.fn(),
    },
  },
}));

describe("Household Management Page", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    Object.assign(navigator, {
      clipboard: {
        writeText: vi.fn().mockResolvedValue(undefined),
      },
    });

    vi.spyOn(authContext, "useAuth").mockReturnValue({
      user: { id: 1, email: "jordan@example.com", display_name: "Jordan" },
      household: { id: 10, name: "Maple Grove", timezone: "UTC", invite_code: "MAPLE-789" },
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

  it("renders household settings, member roster, and copies invite code", async () => {
    vi.mocked(api.households.members).mockResolvedValue([
      {
        id: 1,
        user: { id: 1, email: "jordan@example.com", display_name: "Jordan" },
        role: "admin",
        status: "active",
        joined_at: "2026-01-01T00:00:00Z",
      },
      {
        id: 2,
        user: { id: 2, email: "riley@example.com", display_name: "Riley" },
        role: "member",
        status: "active",
        joined_at: "2026-01-05T00:00:00Z",
      },
    ]);
    vi.mocked(api.households.joinRequests).mockResolvedValue([]);

    render(<HouseholdPage />);

    await waitFor(() => {
      expect(screen.getByTestId("household-title")).toHaveTextContent("Maple Grove");
      expect(screen.getByTestId("invite-code-display")).toHaveTextContent("MAPLE-789");
      expect(screen.getByText("Jordan")).toBeInTheDocument();
      expect(screen.getByText("Riley")).toBeInTheDocument();
    });

    // Copy code
    const copyBtn = screen.getByTestId("copy-code-btn");
    fireEvent.click(copyBtn);
    expect(navigator.clipboard.writeText).toHaveBeenCalledWith("MAPLE-789");

    // Copy link
    const copyLinkBtn = screen.getByTestId("copy-link-btn");
    fireEvent.click(copyLinkBtn);
    expect(navigator.clipboard.writeText).toHaveBeenCalledWith(expect.stringContaining("MAPLE-789"));
  });

  it("renders pending roommate join requests and handles approval voting", async () => {
    vi.mocked(api.households.members).mockResolvedValue([]);
    vi.mocked(api.households.joinRequests).mockResolvedValue([
      {
        id: 42,
        user: { id: 8, email: "newcomer@example.com", display_name: "Newcomer" },
        status: "pending",
        created_at: "2026-03-01T10:00:00Z",
      },
    ]);
    vi.mocked(api.households.voteJoinRequest).mockResolvedValue({});

    render(<HouseholdPage />);

    await waitFor(() => {
      expect(screen.getByText("Newcomer")).toBeInTheDocument();
      expect(screen.getByTestId("approve-join-btn-42")).toBeInTheDocument();
    });

    // Approve applicant
    fireEvent.click(screen.getByTestId("approve-join-btn-42"));
    expect(api.households.voteJoinRequest).toHaveBeenCalledWith(10, 42, true);
  });

  it("handles pause rotation modal confirmation", async () => {
    vi.mocked(api.households.members).mockResolvedValue([]);
    vi.mocked(api.households.joinRequests).mockResolvedValue([]);
    vi.mocked(api.households.pause).mockResolvedValue({ paused: true });

    render(<HouseholdPage />);

    await waitFor(() => {
      expect(screen.getByTestId("toggle-pause-btn")).toBeInTheDocument();
    });

    // Open pause modal
    fireEvent.click(screen.getByTestId("toggle-pause-btn"));
    expect(screen.getByTestId("pause-confirm-dialog")).toBeInTheDocument();

    // Fill pause reason
    fireEvent.change(screen.getByTestId("pause-reason-input"), {
      target: { value: "Final Exams Week" },
    });

    // Confirm pause
    fireEvent.click(screen.getByTestId("confirm-pause-btn"));
    await waitFor(() => {
      expect(api.households.pause).toHaveBeenCalledWith(10, {
        paused: true,
        pause_reason: "Final Exams Week",
      });
    });
  });
});
