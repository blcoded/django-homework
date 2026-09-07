import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import LoginPage from "../page";
import RegisterPage from "../../register/page";
import OnboardingPage from "../../onboarding/page";

const mockPush = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: mockPush,
  }),
}));

const mockLogin = vi.fn();
const mockRegister = vi.fn();
const mockCreateHousehold = vi.fn();
const mockJoinHousehold = vi.fn();

vi.mock("@/context/auth-context", () => ({
  useAuth: () => ({
    user: null,
    household: null,
    loading: false,
    login: mockLogin,
    register: mockRegister,
    createHousehold: mockCreateHousehold,
    joinHousehold: mockJoinHousehold,
  }),
}));

describe("Authentication & Onboarding Pages", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe("LoginPage", () => {
    it("renders login form and validates fields", async () => {
      render(<LoginPage />);

      expect(screen.getByText("Welcome Back")).toBeInTheDocument();
      expect(screen.getByLabelText(/Email Address/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/Password/i)).toBeInTheDocument();

      const submitButton = screen.getByTestId("login-submit");
      fireEvent.click(submitButton);

      await waitFor(() => {
        expect(screen.getByTestId("login-error")).toHaveTextContent(
          "Please enter your email address"
        );
      });
    });

    it("submits valid credentials and navigates", async () => {
      mockLogin.mockResolvedValueOnce(undefined);
      render(<LoginPage />);

      fireEvent.change(screen.getByLabelText(/Email Address/i), {
        target: { value: "test@example.com" },
      });
      fireEvent.change(screen.getByLabelText(/Password/i), {
        target: { value: "password123" },
      });

      fireEvent.click(screen.getByTestId("login-submit"));

      await waitFor(() => {
        expect(mockLogin).toHaveBeenCalledWith("test@example.com", "password123");
        expect(mockPush).toHaveBeenCalledWith("/");
      });
    });
  });

  describe("RegisterPage", () => {
    it("validates password length and password match", async () => {
      render(<RegisterPage />);

      fireEvent.change(screen.getByLabelText(/Your Name/i), {
        target: { value: "Alice" },
      });
      fireEvent.change(screen.getByLabelText(/Email Address/i), {
        target: { value: "alice@example.com" },
      });
      fireEvent.change(screen.getByLabelText(/^Password/i), {
        target: { value: "short" },
      });
      fireEvent.change(screen.getByLabelText(/Confirm Password/i), {
        target: { value: "short" },
      });

      fireEvent.click(screen.getByTestId("register-submit"));

      await waitFor(() => {
        expect(screen.getByTestId("register-error")).toHaveTextContent(
          "Password must be at least 8 characters long"
        );
      });

      // Passwords mismatch
      fireEvent.change(screen.getByLabelText(/^Password/i), {
        target: { value: "longpassword1" },
      });
      fireEvent.change(screen.getByLabelText(/Confirm Password/i), {
        target: { value: "longpassword2" },
      });

      fireEvent.click(screen.getByTestId("register-submit"));

      await waitFor(() => {
        expect(screen.getByTestId("register-error")).toHaveTextContent(
          "Passwords do not match"
        );
      });
    });
  });

  describe("OnboardingPage", () => {
    it("allows switching between create and join tabs", () => {
      render(<OnboardingPage />);

      expect(screen.getByTestId("create-household-form")).toBeInTheDocument();

      fireEvent.click(screen.getByTestId("tab-join"));
      expect(screen.getByTestId("join-household-form")).toBeInTheDocument();

      fireEvent.click(screen.getByTestId("tab-create"));
      expect(screen.getByTestId("create-household-form")).toBeInTheDocument();
    });

    it("creates household on valid input", async () => {
      mockCreateHousehold.mockResolvedValueOnce({
        id: 1,
        name: "Maple Suite",
      });

      render(<OnboardingPage />);

      fireEvent.change(screen.getByLabelText(/Household Name/i), {
        target: { value: "Maple Suite" },
      });

      fireEvent.click(screen.getByTestId("create-household-submit"));

      await waitFor(() => {
        expect(mockCreateHousehold).toHaveBeenCalledWith("Maple Suite", "UTC");
        expect(screen.getByTestId("onboarding-success")).toBeInTheDocument();
      });
    });
  });
});
