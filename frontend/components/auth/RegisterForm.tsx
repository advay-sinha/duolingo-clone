"use client";

/**
 * The sign-up form.
 *
 * Two kinds of validation, and the distinction matters:
 *
 * * **Client-side** — password confirmation and obviously empty fields. These
 *   exist to save a round trip and to put the message next to the field. They
 *   are convenience, never protection.
 * * **Server-side** — email format, password length, duplicate email, duplicate
 *   display name. Only the server can answer the duplicate questions at all, and
 *   it re-checks the others regardless of what the browser did.
 *
 * A 409 comes back with a message naming which field clashed, so it is attached
 * to that field rather than shown as a generic banner — "That display name is
 * taken" is only useful next to the display name box.
 *
 * Registration establishes the session, so there is no second login step.
 */

import { useRouter } from "next/navigation";
import { useState } from "react";

import { ApiError } from "@/lib/api/client";
import { register } from "@/lib/api/auth";

import { AuthField } from "./AuthField";

/** Mirrors `MIN_PASSWORD_LENGTH` in the backend's `auth_service`. */
const MIN_PASSWORD_LENGTH = 8;

type FieldErrors = {
  display_name?: string;
  email?: string;
  password?: string;
  confirm?: string;
};

export function RegisterForm() {
  const router = useRouter();
  const [displayName, setDisplayName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [fields, setFields] = useState<FieldErrors>({});
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  function validate(): FieldErrors {
    const next: FieldErrors = {};
    if (!displayName.trim()) next.display_name = "Choose a display name.";
    if (!email.trim()) next.email = "Enter your email address.";
    if (password.length < MIN_PASSWORD_LENGTH) {
      next.password = `Use at least ${MIN_PASSWORD_LENGTH} characters.`;
    }
    // The one rule the server cannot check: it never sees the second field.
    if (confirm !== password) next.confirm = "Passwords do not match.";
    return next;
  }

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (busy) return;

    const problems = validate();
    if (Object.keys(problems).length > 0) {
      setFields(problems);
      setError(null);
      return;
    }

    setBusy(true);
    setFields({});
    setError(null);
    try {
      await register({
        email: email.trim(),
        password,
        display_name: displayName.trim(),
      });
      router.refresh();
      // Phase 9.5: a new account always starts onboarding. Sending them to
      // `/learn` would work — its guard would bounce them here — but it would
      // cost a round trip and a flash of the wrong screen. The guard remains the
      // authority; this is just the shortcut to the right first screen.
      router.push("/onboarding/course");
    } catch (cause) {
      if (cause instanceof ApiError && (cause.status === 409 || cause.status === 422)) {
        const message = cause.message;
        const lower = message.toLowerCase();
        if (lower.includes("display name")) setFields({ display_name: message });
        else if (lower.includes("email")) setFields({ email: message });
        else if (lower.includes("password")) setFields({ password: message });
        else setError(message);
      } else {
        setError("Could not create your account. Please try again.");
      }
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} className="flex flex-col gap-5" noValidate>
      {error && (
        <p
          role="alert"
          className="rounded-2xl border-2 border-red/40 bg-feedback-incorrect px-4 py-3 text-body-sm text-on-incorrect"
        >
          {error}
        </p>
      )}

      <AuthField
        id="display_name"
        label="Display name"
        type="text"
        value={displayName}
        onChange={setDisplayName}
        autoComplete="nickname"
        error={fields.display_name}
        disabled={busy}
        hint="This is the name other learners see on the leaderboard."
      />
      <AuthField
        id="email"
        label="Email"
        type="email"
        value={email}
        onChange={setEmail}
        autoComplete="email"
        error={fields.email}
        disabled={busy}
      />
      <AuthField
        id="password"
        label="Password"
        type="password"
        value={password}
        onChange={setPassword}
        autoComplete="new-password"
        error={fields.password}
        disabled={busy}
        hint={`At least ${MIN_PASSWORD_LENGTH} characters.`}
      />
      <AuthField
        id="confirm"
        label="Confirm password"
        type="password"
        value={confirm}
        onChange={setConfirm}
        autoComplete="new-password"
        error={fields.confirm}
        disabled={busy}
      />

      <button
        type="submit"
        disabled={busy}
        className="tactile btn-primary min-h-12 w-full disabled:cursor-not-allowed disabled:opacity-70"
      >
        {busy ? "Creating your account…" : "Create account"}
      </button>
    </form>
  );
}
