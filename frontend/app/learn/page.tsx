/**
 * `/learn` — the main application screen.
 *
 * A **Server Component**: it loads the path and the learner's stats on the
 * server and passes them down as props. Two consequences worth knowing:
 * the page arrives populated rather than flashing a spinner, and no skill node
 * fetches anything of its own, so the whole screen costs three requests
 * (courses, path, stats) regardless of how many skills the course has — two
 * round trips, because the stats request runs alongside the course/path chain
 * rather than after it.
 *
 * `AppShell` is rendered here rather than being a `layout.tsx`, because the
 * lesson player at `/learn/lesson/[lessonId]` is nested under this path and must
 * have no chrome — see the note in `AppShell`.
 */

import Link from "next/link";

import { getCoursePath, getCourses } from "@/lib/api/courses";
import { forwardedAuth, redirectIfUnauthenticated } from "@/lib/api/server";
import { getCurrentUserStats } from "@/lib/api/users";
import type { CoursePathResponse, UserStats } from "@/lib/api/types";
import { AppShell } from "@/components/shell/AppShell";
import { DailyGoal } from "@/components/shell/StatsBar";
import { LearningPath } from "@/components/learning-path/LearningPath";

export const metadata = {
  title: "Learn · Duolingo Clone",
};

// Progress changes after every lesson, so this page must never be cached.
export const dynamic = "force-dynamic";

function ErrorScreen({ message }: { message: string }) {
  return (
    <div className="mx-auto flex min-h-dvh max-w-md flex-col items-center justify-center gap-5 px-4 text-center">
      <div className="flex h-20 w-20 items-center justify-center rounded-full bg-border/60">
        <span className="text-4xl" aria-hidden="true">
          ⚠️
        </span>
      </div>
      <h1 className="text-headline-lg text-text">Could not load your course</h1>
      <p className="text-body-md text-text-secondary">{message}</p>
      <p className="text-body-sm text-text-secondary">
        Check that the backend is running on port 8000 and that the database has
        been seeded.
      </p>
      {/* A plain link, not a router call: reloading the route is exactly the
          retry, and it works even if the client bundle failed. */}
      <Link href="/learn" className="tactile btn-primary w-full">
        Try again
      </Link>
    </div>
  );
}

/**
 * Load everything the screen needs, converting failure into a value rather than
 * an exception.
 *
 * Kept separate from the component so no JSX is constructed inside a
 * `try`/`catch` — React renders lazily, so a `catch` around JSX would not
 * actually catch rendering errors, and the lint rule that flags it is right.
 */
async function loadScreen(): Promise<
  { ok: true; path: CoursePathResponse; stats: UserStats | null } | { ok: false; message: string }
> {
  // The two chains are independent, so they run at the same time. Inside the
  // path chain the requests must stay sequential — the path needs a course id
  // that only the first response can supply — but the stats request never
  // needed to wait for either of them.
  // The session cookie arrived on the request to Next.js; it has to be copied
  // onto the request to FastAPI, or this server-side fetch is anonymous. See
  // `lib/api/server.ts`.
  const auth = await forwardedAuth();

  async function loadPath(): Promise<CoursePathResponse | null> {
    // The default course is simply the first the API returns. The seed creates
    // exactly one (English -> Spanish), and course *selection* is deliberately
    // out of scope -- inventing a picker for a single-course database would be
    // building a feature the product does not have yet.
    const { courses } = await getCourses(auth);
    if (courses.length === 0) return null;
    return getCoursePath(courses[0].id, auth);
  }

  // Stats are decoration on this screen; the path is the point. A stats failure
  // hides the counters rather than blocking the whole page.
  const [path, stats] = await Promise.allSettled([
    loadPath(),
    getCurrentUserStats(auth),
  ]);

  if (path.status === "rejected") {
    const error: unknown = path.reason;
    // An expired or missing session is not an error screen — it is a redirect.
    redirectIfUnauthenticated(error);
    return {
      ok: false,
      message:
        error instanceof Error ? error.message : "The API could not be reached.",
    };
  }

  if (path.value === null) {
    return {
      ok: false,
      message: "No courses exist yet. Run the seed command to create one.",
    };
  }

  return {
    ok: true,
    path: path.value,
    stats: stats.status === "fulfilled" ? stats.value : null,
  };
}

export default async function LearnPage() {
  const screen = await loadScreen();

  if (!screen.ok) return <ErrorScreen message={screen.message} />;

  const { path, stats } = screen;

  return (
    <AppShell stats={stats}>
      <div className="mx-auto flex w-full max-w-path flex-col gap-6">
        <header className="flex flex-col gap-1">
          <span className="text-label-md uppercase text-text-secondary">
            {path.source_language} → {path.target_language}
          </span>
          <h1 className="text-headline-xl text-text">{path.course_title}</h1>
        </header>

        {stats && <DailyGoal stats={stats} />}

        <LearningPath path={path} />
      </div>
    </AppShell>
  );
}
