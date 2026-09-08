import type { NextConfig } from "next";

/**
 * The API origin, as seen **from the Next.js server process**.
 *
 * Not `NEXT_PUBLIC_`, and that is the point: this value is used to build the
 * rewrite below and by Server Components, both of which run on the server. It is
 * never inlined into the browser bundle, so the API's real address is not
 * published to every visitor, and it can be changed by restarting the server
 * rather than by rebuilding the app.
 */
const API_ORIGIN = process.env.API_ORIGIN ?? "http://localhost:8000";

const nextConfig: NextConfig = {
  /**
   * Proxy the API under the frontend's own origin.
   *
   * **This is the single most important line in the deployment, and it exists to
   * make authentication work at all.**
   *
   * The session cookie is `SameSite=Lax`. If the browser called the API directly
   * at, say, `https://api.example.dev` while the page was served from
   * `https://app.vercel.app`, those are different *sites*, so the browser would
   * refuse both to store the `Set-Cookie` from login and to send the cookie on
   * any later request. Login, logout, onboarding, placement and every answer
   * submission would fail — while server-rendered pages kept working, because
   * they forward the cookie over server-to-server HTTP where SameSite does not
   * apply. A confusing, half-broken deployment.
   *
   * With this rewrite the browser only ever talks to its own origin. The cookie
   * is first-party, `SameSite=Lax` keeps its full CSRF value, and **there is no
   * cross-origin request left for CORS to govern**.
   *
   * It works locally for the same reason it works in production, which is worth
   * something on its own: dev and prod exercise the same path rather than
   * differing in exactly the area that is hardest to test.
   *
   * The cost is one extra network hop for browser-initiated calls. Server
   * Components skip it — they call `API_ORIGIN` directly.
   */
  async rewrites() {
    return [
      {
        source: "/api/v1/:path*",
        destination: `${API_ORIGIN}/api/v1/:path*`,
      },
    ];
  },
};

export default nextConfig;
