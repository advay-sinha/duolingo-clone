/**
 * Authentication endpoints.
 *
 * The session token is never handled here. It lives in an HttpOnly cookie the
 * browser sets from the login response and attaches to later requests, which is
 * exactly why there is nothing to store: JavaScript cannot read the cookie, so
 * there is no credential for this module — or for `localStorage` — to hold.
 *
 * The one piece of state the frontend keeps is *who the user is*, and even that
 * is not cached: `getCurrentUser` asks the server. A session that expires
 * mid-visit is therefore discovered on the next request rather than believed
 * until the page is reloaded.
 */

import { request } from "./client.ts";
import type { AuthResponse, LogoutResponse } from "./types";

/** Create an account. The response also establishes the session. */
export function register(body: {
  email: string;
  password: string;
  display_name: string;
}): Promise<AuthResponse> {
  return request<AuthResponse>("/auth/register", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

/** Sign in. Both failure modes return the same 401, deliberately. */
export function login(body: {
  email: string;
  password: string;
}): Promise<AuthResponse> {
  return request<AuthResponse>("/auth/login", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

/**
 * Sign out.
 *
 * The server deletes the session row; clearing the cookie alone would leave a
 * usable key behind.
 */
export function logout(): Promise<LogoutResponse> {
  return request<LogoutResponse>("/auth/logout", { method: "POST" });
}

/**
 * Who the current session belongs to.
 *
 * Throws `ApiError` with status 401 when there is no session — which is what
 * the protected pages turn into a redirect.
 */
export function getAuthenticatedUser(init?: RequestInit): Promise<AuthResponse> {
  return request<AuthResponse>("/auth/me", init);
}
