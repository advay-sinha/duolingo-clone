import { cookies } from "next/headers";
import { redirect } from "next/navigation";

import { ApiError } from "./client.ts";

/**
 * Cookie forwarding for Server Components.
 *
 * **The problem this solves.** `/learn`, `/leaderboard` and `/profile` fetch on
 * the server, which means the request to FastAPI is made by Node, not by the
 * browser — and Node has no cookie jar. The learner's session cookie arrived on
 * the *incoming* request to Next.js and has to be copied onto the *outgoing*
 * request to the API, or every server-rendered screen would look logged out.
 *
 * **Why the browser has that cookie at all**, given the API answers on a
 * different port: cookies are scoped by domain and ignore the port. FastAPI on
 * `localhost:8000` sets a cookie for `localhost`, and the browser then sends it
 * to `localhost:3000` as well. Convenient locally; worth remembering that it also
 * means the two apps share a cookie namespace, which a real deployment on
 * separate hosts would not.
 *
 * This module must only be imported by Server Components — `next/headers` throws
 * anywhere else — which is why it is a separate file from `client.ts`.
 */
export async function forwardedAuth(): Promise<RequestInit> {
  const store = await cookies();
  const header = store.toString();
  return header ? { headers: { cookie: header } } : {};
}

/**
 * Redirect to the login page if a failure was "you are not signed in".
 *
 * Called from a page's error path, so an expired session sends the learner to
 * `/login` instead of showing them an error screen about a 401 they cannot act
 * on. Any other failure is returned to the caller to render normally — a backend
 * that is down is not a reason to demand a password.
 *
 * `redirect()` works by throwing, so this never returns when it fires.
 */
export function redirectIfUnauthenticated(error: unknown): void {
  if (error instanceof ApiError && error.status === 401) {
    redirect("/login");
  }
}
