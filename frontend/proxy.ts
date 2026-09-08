import { NextResponse, type NextRequest } from "next/server";

/**
 * Bounce obviously-signed-out visitors before a page starts rendering.
 *
 * Named `proxy.ts`, not `middleware.ts`: Next 16 renamed the convention and
 * warns on the old filename. The exported function must be called `proxy`, and
 * it always runs on the Node.js runtime.
 *
 * **This is not the security boundary, and it must not be mistaken for one.**
 * All it checks is whether a session cookie is *present*. It does not — and
 * deliberately cannot — check whether that cookie names a live session: doing so
 * would mean a database or API round trip on every request, including every
 * static asset, to duplicate a check the API already performs correctly. Every
 * learner endpoint on the backend resolves the session properly and answers 401
 * if it does not exist, has expired, or was logged out; that is the boundary.
 *
 * What this buys is purely user experience. Without it the sequence for a
 * signed-out visitor is: start rendering `/learn`, stream the loading skeleton,
 * discover the 401, and — because the response has already begun — fall back to
 * a `<meta http-equiv="refresh">` redirect a second later. With it, the browser
 * gets a plain 307 before any of that happens.
 *
 * A forged or stale cookie therefore reaches the page, which then gets a 401
 * from the API and redirects properly. That is the correct division: cheap guess
 * here, real answer there.
 *
 * **Onboarding routing is not done here either**, for the same reason: deciding
 * whether a learner has finished onboarding needs their row, and that is an API
 * call. Each page asks the server directly — see `lib/onboarding/guard.ts`. All
 * this file knows about `/onboarding` is that it needs a session.
 */

/**
 * The session cookie's name.
 *
 * **Read from the environment because it has to agree with the backend.** The
 * Phase 10 audit found this as a bare literal here and a setting
 * (`SESSION_COOKIE_NAME`) there, with nothing keeping the two in step: renaming
 * it on the backend alone would leave this file looking for a cookie that no
 * longer exists, so every signed-in visitor would be bounced to `/login` while
 * the API happily authenticated them. A silent, confusing half-failure.
 *
 * One variable now sets both. The default matches the backend's default, so
 * neither side needs configuring for local development.
 *
 * Not `NEXT_PUBLIC_`: the proxy runs on the server, and the cookie's *name* is
 * not something the browser bundle needs to know.
 */
const SESSION_COOKIE = process.env.SESSION_COOKIE_NAME ?? "duolingo_session";

/** Routes that require a learner. Everything else is public. */
const PROTECTED = ["/learn", "/leaderboard", "/profile", "/onboarding"];

export function proxy(request: NextRequest) {
  const { pathname } = request.nextUrl;

  const isProtected = PROTECTED.some(
    (route) => pathname === route || pathname.startsWith(`${route}/`),
  );
  if (!isProtected) return NextResponse.next();

  if (request.cookies.has(SESSION_COOKIE)) return NextResponse.next();

  const url = request.nextUrl.clone();
  url.pathname = "/login";
  // `redirect` and not `rewrite`: the address bar should say `/login`, so a
  // refresh does not bounce again and the learner can see where they are.
  return NextResponse.redirect(url);
}

export const config = {
  // Static assets and the API proxy never need this check, and running
  // middleware on them would cost a function invocation per file.
  matcher: [
    "/learn/:path*",
    "/leaderboard/:path*",
    "/profile/:path*",
    "/onboarding/:path*",
  ],
};
