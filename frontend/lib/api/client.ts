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
 * (404 vs 409) instead of parsing message strings.
 */
export class ApiError extends Error {
  readonly status: number;

  constructor(message: string, status: number, options?: { cause?: unknown }) {
    super(message, options);
    this.name = "ApiError";
    this.status = status;
  }
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
    throw new ApiError(
      `Request to ${path} failed with status ${response.status}.`,
      response.status,
    );
  }

  return (await response.json()) as T;
}
