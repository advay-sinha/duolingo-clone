/**
 * The single place in the frontend that knows how to talk HTTP to the backend.
 *
 * Every future feature call goes through `request<T>()` rather than calling
 * `fetch` directly, so the base URL, headers, and error shape are defined once.
 * When authentication arrives in a later phase, it is added here and nowhere
 * else.
 */

/**
 * Where the API is, which depends on who is asking.
 *
 * **In the browser: a relative path.** Every client-side call goes to the app's
 * own origin and is proxied to FastAPI by the rewrite in `next.config.ts`. That
 * is what makes the session cookie first-party — see the long note there — and
 * it means the API's real address is never inlined into the browser bundle.
 *
 * **On the server: an absolute origin.** Server Components run in Node, which has
 * no notion of "the current origin", so they need the full address.
 * `API_ORIGIN` is a plain (non-`NEXT_PUBLIC_`) variable read at request time, so
 * changing it is a restart rather than a rebuild.
 *
 * **The Phase 10 audit found the previous version of this line to be a
 * production footgun.** It was
 * `process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1"`, and
 * `NEXT_PUBLIC_*` is inlined at *build* time — so forgetting to set it in the
 * deployment dashboard produced a bundle that asked every visitor's own machine
 * for the API, with no error anywhere. That exact failure happened during Phase
 * 9.5 verification and looked like an application bug for several minutes. The
 * browser now needs no configuration at all, which is the only reliable way not
 * to forget it.
 */
export function apiBaseUrl(): string {
  if (typeof window !== "undefined") return "/api/v1";
  const origin = process.env.API_ORIGIN ?? "http://localhost:8000";
  return `${origin}/api/v1`;
}

// There is deliberately no exported `API_BASE_URL` constant any more. A
// module-level constant would freeze whichever value `API_ORIGIN` held at import
// time — the wrong lifetime for configuration — and, worse, it would be computed
// on the server even for code that later runs in the browser. `apiBaseUrl()` is
// called per request instead, which costs nothing and cannot be stale.

/**
 * A failed API call. Carries the HTTP status so callers can branch on it
 * (404 vs 409) instead of parsing message strings, and the backend's error
 * `code` for the same reason.
 */
export class ApiError extends Error {
  readonly status: number;
  readonly code: string | null;

  constructor(
    message: string,
    status: number,
    options?: { cause?: unknown; code?: string | null },
  ) {
    super(message, options);
    this.name = "ApiError";
    this.status = status;
    this.code = options?.code ?? null;
  }
}

/** The error envelope every backend failure uses. See `backend/app/core/errors.py`. */
type ErrorEnvelope = { error: { code: string; message: string } };

function isErrorEnvelope(value: unknown): value is ErrorEnvelope {
  if (typeof value !== "object" || value === null) return false;
  const error = (value as { error?: unknown }).error;
  if (typeof error !== "object" || error === null) return false;
  const { code, message } = error as { code?: unknown; message?: unknown };
  return typeof code === "string" && typeof message === "string";
}

/**
 * Fallback copy for a failure the backend did not explain.
 *
 * Phase 8 review: the message shown to a learner used to be
 * "Request to /lessons/1/start failed with status 409." — a developer's
 * sentence in front of someone trying to learn Spanish. The backend's own
 * message ("No hearts remaining.") is written in domain terms and is the better
 * thing to show; this only covers the case where there isn't one.
 */
function fallbackMessage(status: number): string {
  if (status === 404) return "We couldn't find that.";
  if (status === 409) return "That isn't possible right now.";
  if (status >= 500) return "The server had a problem. Please try again.";
  return "Something went wrong. Please try again.";
}

/**
 * Perform a JSON request against the backend.
 *
 * @param path - Path below the API base, e.g. "/health".
 * @param init - Standard fetch options; headers are merged with the JSON defaults.
 * @returns The parsed JSON body, typed as `T`.
 * @throws {ApiError} When the network call fails or the response is not 2xx.
 */
export async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;

  const base = apiBaseUrl();

  try {
    response = await fetch(`${base}${path}`, {
      ...init,
      headers: {
        "Content-Type": "application/json",
        ...init?.headers,
      },
      // Since Phase 10 the browser calls its own origin, so cookies would be
      // attached anyway — "same-origin" is the default. This is kept explicit
      // because it is the behaviour the app depends on, and because it keeps a
      // split-origin deployment working for anyone who chooses one.
      credentials: "include",
      // Progress data changes after every lesson, so nothing from this API is
      // safe to serve from a cache.
      cache: "no-store",
    });
  } catch (cause) {
    // fetch only rejects on transport failure — backend down, DNS, CORS block.
    throw new ApiError(
      `Could not reach the API at ${base}. Is the backend running?`,
      0,
      { cause },
    );
  }

  if (!response.ok) {
    // The body is read defensively: a proxy, a crash before the handler, or a
    // gateway can all produce a non-JSON error page, and failing to parse one
    // must not replace a useful status code with a JSON syntax error.
    let body: unknown = null;
    try {
      body = await response.json();
    } catch {
      body = null;
    }

    const envelope = isErrorEnvelope(body) ? body.error : null;
    throw new ApiError(
      envelope?.message ?? fallbackMessage(response.status),
      response.status,
      { code: envelope?.code ?? null },
    );
  }

  return (await response.json()) as T;
}
