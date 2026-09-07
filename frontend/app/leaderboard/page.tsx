/**
 * `/leaderboard` — learner standings by lifetime XP.
 *
 * A Server Component, like `/learn`: two requests issued in parallel, no client
 * fetching, and the page arrives populated. Reuses `AppShell` rather than
 * reimplementing chrome.
 */

import Link from "next/link";

import { AppShell } from "@/components/shell/AppShell";
import { LeaderboardRow } from "@/components/leaderboard/LeaderboardRow";
import { getLeaderboard } from "@/lib/api/leaderboard";
import { forwardedAuth, redirectIfUnauthenticated } from "@/lib/api/server";
import { getCurrentUserStats } from "@/lib/api/users";
import type { LeaderboardResponse, UserStats } from "@/lib/api/types";

export const metadata = { title: "Leaderboard · Duolingo Clone" };

// XP changes after every lesson, so this must never be served from a cache.
export const dynamic = "force-dynamic";

const PERIOD_LABEL: Record<string, string> = {
  "all-time": "All-time XP",
};

async function load(): Promise<
  { ok: true; board: LeaderboardResponse; stats: UserStats | null } | { ok: false; message: string }
> {
  // The board and the stats bar are independent, so they are issued together.
  // Awaiting them one after the other cost a whole round trip for no reason.
  // `allSettled` rather than `all` because the two failures mean different
  // things: no board is an empty page, no stats is a missing counter.
  const auth = await forwardedAuth();
  const [board, stats] = await Promise.allSettled([
    getLeaderboard(auth),
    getCurrentUserStats(auth),
  ]);

  if (board.status === "rejected") {
    const error: unknown = board.reason;
    redirectIfUnauthenticated(error);
    return {
      ok: false,
      message:
        error instanceof Error ? error.message : "The API could not be reached.",
    };
  }

  return {
    ok: true,
    board: board.value,
    stats: stats.status === "fulfilled" ? stats.value : null,
  };
}

export default async function LeaderboardPage() {
  const result = await load();

  if (!result.ok) {
    return (
      <AppShell>
        <div className="mx-auto max-w-md py-16 text-center">
          <div className="mx-auto flex h-20 w-20 items-center justify-center rounded-full bg-border/60">
            <span className="text-4xl" aria-hidden="true">
              ⚠️
            </span>
          </div>
          <h1 className="mt-4 text-headline-lg text-text">
            Could not load the leaderboard
          </h1>
          <p className="mt-1 text-body-md text-text-secondary">{result.message}</p>
          <Link href="/leaderboard" className="tactile btn-primary mt-5 inline-block">
            Try again
          </Link>
        </div>
      </AppShell>
    );
  }

  const { board, stats } = result;

  return (
    <AppShell stats={stats}>
      <div className="mx-auto flex w-full max-w-path flex-col gap-6">
        <header className="flex flex-col gap-1">
          <span className="text-label-md uppercase text-text-secondary">
            {/* Labelled from the response, so the screen cannot claim a period
                the backend does not actually rank by. */}
            {PERIOD_LABEL[board.period] ?? board.period}
          </span>
          <h1 className="text-headline-xl text-text">Leaderboard</h1>
          <p className="text-body-md text-text-secondary">
            Everyone learning Spanish, ranked by the XP they have earned so far.
          </p>
        </header>

        {board.entries.length === 0 ? (
          <div className="card p-8 text-center">
            <p className="text-headline-sm text-text">Nobody is ranked yet</p>
            <p className="mt-1 text-body-md text-text-secondary">
              Complete a lesson to appear on the leaderboard.
            </p>
          </div>
        ) : (
          <>
            <ol className="flex flex-col gap-2">
              {board.entries.map((entry) => (
                <LeaderboardRow key={entry.user_id} entry={entry} />
              ))}
            </ol>

            {/* Honest about a one-learner board rather than padding it out. */}
            {board.entries.length === 1 && (
              <p className="text-center text-body-sm text-text-secondary">
                You are the only learner so far — this board fills up as more
                people join.
              </p>
            )}
          </>
        )}
      </div>
    </AppShell>
  );
}
