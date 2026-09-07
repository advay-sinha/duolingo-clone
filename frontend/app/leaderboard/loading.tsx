/**
 * Skeleton shown while `/leaderboard` loads on the server.
 *
 * `/learn` had one from Phase 6; the leaderboard and profile did not, so moving
 * between tabs left the previous screen frozen with no sign that anything was
 * happening. Same shape as the real page — a header, then a column of rows — so
 * nothing jumps when the data lands.
 */

export default function LeaderboardLoading() {
  return (
    <div className="min-h-dvh lg:pl-64">
      <div className="h-16 border-b-2 border-border bg-surface" />
      <div className="mx-auto w-full max-w-path px-4 pt-6">
        <div className="flex animate-pulse flex-col gap-4" aria-hidden="true">
          <div className="h-8 w-48 rounded-full bg-border" />
          <div className="h-4 w-64 rounded-full bg-border" />
          <div className="mt-2 flex flex-col gap-3">
            {[0, 1, 2, 3, 4].map((index) => (
              <div key={index} className="h-16 rounded-2xl bg-border" />
            ))}
          </div>
        </div>
        {/* Visually redundant with the skeleton, but the skeleton says nothing
            to a screen reader — it is `aria-hidden` on purpose. */}
        <p className="sr-only" role="status">
          Loading the leaderboard…
        </p>
      </div>
    </div>
  );
}
