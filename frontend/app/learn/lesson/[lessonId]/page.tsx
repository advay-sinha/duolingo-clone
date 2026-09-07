/**
 * The lesson route.
 *
 * A **Server Component that renders one Client Component**. The client boundary
 * is drawn here, as tightly as possible: this file reads and validates the URL
 * parameter on the server, and `LessonPlayer` (and everything below it) runs in
 * the browser because a lesson is entirely interactive — reducer state, input
 * handling, and API calls that must originate from the browser.
 *
 * The lesson deliberately has no app shell: no sidebar, no HUD. That matches the
 * Stitch design, where the lesson player is a focus mode, and it is why this
 * route sits outside any shell layout.
 */

import { notFound } from "next/navigation";

import { LessonPlayer } from "@/components/lesson/LessonPlayer";
import { getAuthenticatedUser } from "@/lib/api/auth";
import { forwardedAuth, redirectIfUnauthenticated } from "@/lib/api/server";

export const metadata = {
  title: "Lesson · Duolingo Clone",
};

export default async function LessonPage({
  params,
}: {
  // Params are async in the App Router, so they are awaited below.
  params: Promise<{ lessonId: string }>;
}) {
  const { lessonId } = await params;
  const id = Number(lessonId);

  // Reject a non-numeric id here rather than letting it reach the API as a
  // guaranteed 422.
  if (!Number.isInteger(id) || id <= 0) notFound();

  // Checked on the server, before the player mounts. The API would refuse an
  // unauthenticated `POST /start` anyway — this is not the security boundary,
  // that is — but bouncing here means a signed-out learner sees the login page
  // rather than a lesson screen that fails a moment later.
  try {
    await getAuthenticatedUser(await forwardedAuth());
  } catch (error) {
    redirectIfUnauthenticated(error);
    // Any other failure (the API being down) is left to the player, which
    // already has an error screen with a way back.
  }

  return <LessonPlayer lessonId={id} />;
}
