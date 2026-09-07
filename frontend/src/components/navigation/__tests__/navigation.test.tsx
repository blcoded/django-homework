import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { usePathname } from "next/navigation";
import { Sidebar } from "../sidebar";
import { MobileNav } from "../mobile-nav";
import { AppShell } from "../app-shell";

vi.mock("next/navigation", () => ({
  usePathname: vi.fn(),
}));

describe("Navigation Components", () => {
  it("renders all sidebar navigation links and highlights active route", () => {
    vi.mocked(usePathname).mockReturnValue("/chores");

    render(<Sidebar />);

    expect(screen.getByTestId("desktop-sidebar")).toBeInTheDocument();
    expect(screen.getByText("RoommateOS")).toBeInTheDocument();

    const homeLink = screen.getByTestId("nav-item-home");
    const choresLink = screen.getByTestId("nav-item-chores");
    const activityLink = screen.getByTestId("nav-item-activity");
    const statsLink = screen.getByTestId("nav-item-stats");
    const householdLink = screen.getByTestId("nav-item-household");

    expect(homeLink).toBeInTheDocument();
    expect(choresLink).toBeInTheDocument();
    expect(activityLink).toBeInTheDocument();
    expect(statsLink).toBeInTheDocument();
    expect(householdLink).toBeInTheDocument();

    // Check that /chores is marked active with bg-primary
    expect(choresLink).toHaveClass("bg-primary");
    // Check that /home is not active
    expect(homeLink).not.toHaveClass("bg-primary");
  });

  it("renders mobile navigation bar with all navigation items", () => {
    vi.mocked(usePathname).mockReturnValue("/stats");

    render(<MobileNav />);

    expect(screen.getByTestId("mobile-nav")).toBeInTheDocument();
    expect(screen.getByTestId("mobile-nav-home")).toBeInTheDocument();
    expect(screen.getByTestId("mobile-nav-chores")).toBeInTheDocument();
    expect(screen.getByTestId("mobile-nav-stats")).toBeInTheDocument();

    const statsMobile = screen.getByTestId("mobile-nav-stats");
    expect(statsMobile).toHaveClass("text-primary");
  });

  it("renders AppShell wrapping page content", () => {
    vi.mocked(usePathname).mockReturnValue("/");

    render(
      <AppShell>
        <div data-testid="test-content">Dashboard Content</div>
      </AppShell>
    );

    expect(screen.getByTestId("test-content")).toBeInTheDocument();
    expect(screen.getByTestId("desktop-sidebar")).toBeInTheDocument();
    expect(screen.getByTestId("mobile-nav")).toBeInTheDocument();
  });
});
