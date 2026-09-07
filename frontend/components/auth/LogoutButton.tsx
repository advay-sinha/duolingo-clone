"use client";

/**
 * Sign out, from the profile's settings area.
 *
 * **The server is what actually logs you out.** This calls
 * `POST /auth/logout`, which deletes the session row; clearing the cookie in the
 * browser alone would leave a working session behind that anyone holding a copy
 * of the token could continue to use.
 *
 * `router.refresh()` before navigating discards the cached Server Component
 * payloads, so no screen can briefly re-render with the signed-in data it
 * fetched a moment ago.
 *
 * If the request fails the learner is told, rather than being redirected to
 * `/login` as though it had worked — a silent "logout" that did not happen is
 * exactly the wrong thing to be reassuring about.
 */

import { useRouter } from "next/navigation";
import { useState } from "react";

import { logout } from "@/lib/api/auth";

export function LogoutButton({ displayName }: { displayName: string }) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function signOut() {
    if (busy) return;
    setBusy(true);
    setError(null);
    try {
      await logout();
      router.refresh();
      router.push("/login");
    } catch {
      setError("Could not sign out. Check your connection and try again.");
      setBusy(false);
    }
  }

  return (
    <div className="flex flex-col gap-2">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-body-md text-text-secondary">
          Signed in as <span className="font-bold text-text">{displayName}</span>
        </p>
        <button
          type="button"
          onClick={signOut}
          disabled={busy}
          className="tactile min-h-11 border-border bg-surface px-5 text-label-bold uppercase text-text disabled:cursor-not-allowed disabled:opacity-70"
          style={{ borderBottomColor: "var(--color-border-depth)" }}
        >
          {busy ? "Signing out…" : "Log out"}
        </button>
      </div>
      {error && (
        <p role="alert" className="text-body-sm text-on-incorrect">
          {error}
        </p>
      )}
    </div>
  );
}
