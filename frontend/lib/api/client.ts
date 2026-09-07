/**
 * The single place in the frontend that knows how to talk HTTP to the backend.
 *
 * Every future feature call goes through `request<T>()` rather than calling
 * `fetch` directly, so the base URL, headers, and error shape are defined once.
 * When authentication arrives in a later phase, it is added here and nowhere
 * else.
 */

/** Base URL of the FastAPI backend, e.g. "http://localhost:8000/api/v1". */
export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";

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

  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      ...init,
      headers: {
        "Content-Type": "application/json",
        ...init?.headers,
      },
      // The session cookie is set by the API on a different port. Cookies are
      // scoped by *domain*, not by port, so the browser holds one "localhost"
      // cookie and this tells it to attach it to a cross-origin request. Without
      // this, every browser call would arrive unauthenticated. The backend's
      // CORS config already allows credentials from these exact origins.
      credentials: "include",
      // Progress data changes after every lesson, so nothing from this API is
      // safe to serve from a cache.
      cache: "no-store",
    });
  } catch (cause) {
    // fetch only rejects on transport failure — backend down, DNS, CORS block.
    throw new ApiError(
      `Could not reach the API at ${API_BASE_URL}. Is the backend running?`,
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
