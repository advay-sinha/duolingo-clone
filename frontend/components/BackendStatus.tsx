"use client";

/**
 * Live backend connection indicator.
 *
 * A Client Component on purpose. Calling the API from the browser (rather than
 * from a Server Component) is what actually exercises the cross-origin path
 * localhost:3000 -> localhost:8000, so this widget proves CORS is configured
 * correctly, not just that the two processes are running.
 */

import { useEffect, useState } from "react";

import { ApiError } from "@/lib/api/client";
import { getHealth } from "@/lib/api/health";

type State =
  | { kind: "checking" }
  | { kind: "online"; status: string }
  | { kind: "offline"; message: string };

export function BackendStatus() {
  const [state, setState] = useState<State>({ kind: "checking" });

  useEffect(() => {
    let cancelled = false;

    getHealth()
      .then((health) => {
        if (!cancelled) setState({ kind: "online", status: health.status });
      })
      .catch((error: unknown) => {
        if (cancelled) return;
        const message =
          error instanceof ApiError ? error.message : "Unexpected error.";
        setState({ kind: "offline", message });
      });

    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div className="card w-full p-6" aria-live="polite">
      <p className="text-label-md uppercase text-text-secondary">
        Backend connection
      </p>

      {state.kind === "checking" && (
        <p className="mt-2 text-body-md text-text-secondary">
          Checking <code>GET /api/v1/health</code>…
        </p>
      )}

      {state.kind === "online" && (
        <div className="mt-2 flex items-center gap-3">
          <span
            className="h-3 w-3 shrink-0 rounded-full bg-green"
            aria-hidden="true"
          />
          <p className="text-body-md text-text">
            Connected — the API replied{" "}
            <code className="font-bold text-green-depth">
              {`{ "status": "${state.status}" }`}
            </code>
          </p>
        </div>
      )}

      {state.kind === "offline" && (
        <div className="mt-2 flex items-start gap-3">
          <span
            className="mt-1.5 h-3 w-3 shrink-0 rounded-full bg-red"
            aria-hidden="true"
          />
          <div>
            <p className="text-body-md text-text">Not connected.</p>
            <p className="mt-1 text-body-sm text-text-secondary">
              {state.message}
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
