/**
 * Skeleton shown while `/profile` loads on the server.
 *
 * See `app/leaderboard/loading.tsx` — same reasoning, shaped like the profile:
 * an identity block, a row of stat cards, then the achievement grid.
 */

export default function ProfileLoading() {
  return (
    <div className="min-h-dvh lg:pl-64">
      <div className="h-16 border-b-2 border-border bg-surface" />
      <div className="mx-auto w-full max-w-path px-4 pt-6">
        <div className="flex animate-pulse flex-col gap-6" aria-hidden="true">
          <div className="flex items-center gap-4">
            <div className="h-20 w-20 rounded-full bg-border" />
            <div className="flex flex-col gap-2">
              <div className="h-7 w-40 rounded-full bg-border" />
              <div className="h-4 w-28 rounded-full bg-border" />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            {[0, 1, 2, 3].map((index) => (
              <div key={index} className="h-24 rounded-2xl bg-border" />
            ))}
          </div>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            {[0, 1, 2, 3].map((index) => (
              <div key={index} className="h-24 rounded-2xl bg-border" />
            ))}
          </div>
        </div>
        <p className="sr-only" role="status">
          Loading your profile…
        </p>
      </div>
    </div>
  );
}
