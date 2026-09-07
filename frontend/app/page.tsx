/**
 * `/` — redirects to the learning path.
 *
 * Until Phase 8 this was the Phase 1 foundation page, showing a backend-status
 * widget. That was the right thing when there was no product to show; now it
 * means the app opens on a developer diagnostic. `/learn` is the home screen.
 *
 * `redirect()` in a Server Component issues the redirect before any HTML is
 * sent, so there is no flash of an intermediate page.
 */

import { redirect } from "next/navigation";

export default function RootPage() {
  redirect("/learn");
}
