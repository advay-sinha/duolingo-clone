/**
 * Component tests for the login and register forms.
 *
 * These assert what someone filling the form experiences: which errors appear,
 * which are caught before a request is made, and — the security-relevant one —
 * that a failed login says nothing about *why*.
 *
 * The API modules are mocked, so nothing here touches a network. The router is
 * mocked too, because navigation is the success signal.
 */

import { beforeEach, describe, expect, test, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { ApiError } from "@/lib/api/client";

const push = vi.fn();
const refresh = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push, refresh }),
}));

const login = vi.fn();
const register = vi.fn();

vi.mock("@/lib/api/auth", () => ({
  login: (...args: unknown[]) => login(...args),
  register: (...args: unknown[]) => register(...args),
}));

const { LoginForm } = await import("./LoginForm");
const { RegisterForm } = await import("./RegisterForm");

beforeEach(() => {
  push.mockClear();
  refresh.mockClear();
  login.mockReset();
  register.mockReset();
});

// --------------------------------------------------------------------------
// Login
// --------------------------------------------------------------------------

describe("LoginForm", () => {
  async function fill(email: string, password: string) {
    await userEvent.type(screen.getByLabelText("Email"), email);
    await userEvent.type(screen.getByLabelText("Password"), password);
  }

  test("valid credentials sign in and land on the learning path", async () => {
    login.mockResolvedValue({ user: { display_name: "Alex" } });
    render(<LoginForm />);

    await fill("alex@example.com", "password123");
    await userEvent.click(screen.getByRole("button", { name: "Log in" }));

    expect(login).toHaveBeenCalledWith({
      email: "alex@example.com",
      password: "password123",
    });
    expect(push).toHaveBeenCalledWith("/learn");
    // Server Components cached before the login must not be replayed after it.
    expect(refresh).toHaveBeenCalled();
  });

  test("an empty form is caught without calling the API", async () => {
    render(<LoginForm />);

    await userEvent.click(screen.getByRole("button", { name: "Log in" }));

    expect(login).not.toHaveBeenCalled();
    expect(screen.getByRole("alert").textContent).toContain("email and password");
  });

  test("a rejected login shows the server's generic message", async () => {
    // The backend answers "unknown email" and "wrong password" identically on
    // purpose; the form must not embellish that into something more specific.
    login.mockRejectedValue(
      new ApiError("Email or password is incorrect.", 401, { code: "unauthenticated" }),
    );
    render(<LoginForm />);

    await fill("alex@example.com", "wrong-password");
    await userEvent.click(screen.getByRole("button", { name: "Log in" }));

    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toBe("Email or password is incorrect.");
    // Nothing about which half was wrong.
    expect(alert.textContent).not.toMatch(/no account|not found|unknown/i);
    expect(push).not.toHaveBeenCalled();
  });

  test("a backend failure does not masquerade as bad credentials", async () => {
    login.mockRejectedValue(new ApiError("boom", 500));
    render(<LoginForm />);

    await fill("alex@example.com", "password123");
    await userEvent.click(screen.getByRole("button", { name: "Log in" }));

    expect((await screen.findByRole("alert")).textContent).toContain(
      "Could not sign in",
    );
  });

  test("the submit button reports that it is working", async () => {
    login.mockImplementation(() => new Promise(() => {}));
    render(<LoginForm />);

    await fill("alex@example.com", "password123");
    await userEvent.click(screen.getByRole("button", { name: "Log in" }));

    const button = screen.getByRole("button", {
      name: "Signing in…",
    }) as HTMLButtonElement;
    expect(button.disabled).toBe(true);
  });

  test("the password field is a password field", () => {
    render(<LoginForm />);

    const input = screen.getByLabelText("Password") as HTMLInputElement;
    expect(input.type).toBe("password");
    // Tells a password manager what this is, which is why autofill works.
    expect(input.autocomplete).toBe("current-password");
  });
});

// --------------------------------------------------------------------------
// Register
// --------------------------------------------------------------------------

describe("RegisterForm", () => {
  async function fill(over: Partial<Record<string, string>> = {}) {
    const values = {
      "Display name": "Alice",
      Email: "alice@example.com",
      Password: "password123",
      "Confirm password": "password123",
      ...over,
    };
    for (const [label, value] of Object.entries(values)) {
      if (value) await userEvent.type(screen.getByLabelText(label), value);
    }
  }

  test("a valid registration signs in without a second login step", async () => {
    register.mockResolvedValue({ user: { display_name: "Alice" } });
    render(<RegisterForm />);

    await fill();
    await userEvent.click(screen.getByRole("button", { name: "Create account" }));

    expect(register).toHaveBeenCalledWith({
      email: "alice@example.com",
      password: "password123",
      display_name: "Alice",
    });
    // Phase 9.5: a new account goes to onboarding, not straight to the path.
    expect(push).toHaveBeenCalledWith("/onboarding/course");
  });

  test("mismatched passwords are caught before any request", async () => {
    render(<RegisterForm />);

    await fill({ "Confirm password": "different1" });
    await userEvent.click(screen.getByRole("button", { name: "Create account" }));

    // The one rule the server cannot check: it never sees the second field.
    expect(screen.getByText("Passwords do not match.")).toBeDefined();
    expect(register).not.toHaveBeenCalled();
  });

  test("a short password is caught before any request", async () => {
    render(<RegisterForm />);

    await fill({ Password: "short", "Confirm password": "short" });
    await userEvent.click(screen.getByRole("button", { name: "Create account" }));

    expect(screen.getByText(/at least 8 characters/i)).toBeDefined();
    expect(register).not.toHaveBeenCalled();
  });

  test("a duplicate email is attached to the email field", async () => {
    register.mockRejectedValue(
      new ApiError("An account with that email already exists.", 409),
    );
    render(<RegisterForm />);

    await fill();
    await userEvent.click(screen.getByRole("button", { name: "Create account" }));

    const input = (await screen.findByLabelText("Email")) as HTMLInputElement;
    expect(input.getAttribute("aria-invalid")).toBe("true");
    expect(screen.getByText(/already exists/)).toBeDefined();
  });

  test("a duplicate display name is attached to the display name field", async () => {
    register.mockRejectedValue(new ApiError("That display name is taken.", 409));
    render(<RegisterForm />);

    await fill();
    await userEvent.click(screen.getByRole("button", { name: "Create account" }));

    const input = (await screen.findByLabelText("Display name")) as HTMLInputElement;
    expect(input.getAttribute("aria-invalid")).toBe("true");
  });

  test("an error message is linked to its field for screen readers", async () => {
    render(<RegisterForm />);

    await fill({ "Confirm password": "different1" });
    await userEvent.click(screen.getByRole("button", { name: "Create account" }));

    const input = screen.getByLabelText("Confirm password");
    const describedBy = input.getAttribute("aria-describedby");
    expect(describedBy).toBeTruthy();
    expect(document.getElementById(describedBy!)?.textContent).toBe(
      "Passwords do not match.",
    );
  });

  test("an unexpected failure does not blame a field", async () => {
    register.mockRejectedValue(new ApiError("boom", 500));
    render(<RegisterForm />);

    await fill();
    await userEvent.click(screen.getByRole("button", { name: "Create account" }));

    expect((await screen.findByRole("alert")).textContent).toContain(
      "Could not create your account",
    );
  });
});
