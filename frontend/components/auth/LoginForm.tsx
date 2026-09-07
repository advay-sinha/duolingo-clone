"use client";

/**
 * The sign-in form.
 *
 * A Client Component because it holds input state and calls the API. It stores
 * exactly two strings and an error message — and, importantly, **nothing about
 * the session**. The token never reaches JavaScript: it arrives as an HttpOnly
 * cookie the browser stores by itself, so there is no "auth state" here to keep
 * in sync, no `localStorage` write, and nothing for a script on the page to
 * steal.
 *
 * On success it uses `router.refresh()` before navigating, so the Server
 * Components that render `/learn` re-fetch with the new cookie instead of
 * replaying a cached payload from before the login.
 */

import { useRouter } from "next/navigation";
import { useState } from "react";

import { ApiError } from "@/lib/api/client";
import { login } from "@/lib/api/auth";

import { AuthField } from "./AuthField";

export function LoginForm() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (busy) return;

    // A local check purely to save a round trip on an obviously empty form. The
    // server validates everything again; this is convenience, not security.
    if (!email.trim() || !password) {
      setError("Enter your email and password.");
      return;
    }

    setBusy(true);
    setError(null);
    try {
      await login({ email: email.trim(), password });
      router.refresh();
      router.push("/learn");
    } catch (cause) {
      // The backend answers "unknown email" and "wrong password" identically on
      // purpose, so this shows whatever it said rather than guessing which.
      setError(
        cause instanceof ApiError && cause.status === 401
          ? cause.message
          : "Could not sign in. Please try again.",
      );
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} className="flex flex-col gap-5" noValidate>
      {error && (
        // One live region for the form, announced when it appears.
        <p
          role="alert"
          className="rounded-2xl border-2 border-red/40 bg-feedback-incorrect px-4 py-3 text-body-sm text-on-incorrect"
        >
          {error}
        </p>
      )}

      <AuthField
        id="email"
        label="Email"
        type="email"
        value={email}
        onChange={setEmail}
        autoComplete="email"
        disabled={busy}
      />
      <AuthField
        id="password"
        label="Password"
        type="password"
        value={password}
        onChange={setPassword}
        autoComplete="current-password"
        disabled={busy}
      />

      <button
        type="submit"
        disabled={busy}
        className="tactile btn-primary min-h-12 w-full disabled:cursor-not-allowed disabled:opacity-70"
      >
        {busy ? "Signing in…" : "Log in"}
      </button>
    </form>
  );
}
