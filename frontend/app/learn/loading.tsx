/**
 * Skeleton shown while `/learn` loads on the server.
 *
 * Next.js renders this automatically for the route's Suspense boundary. It
 * mirrors the real layout — banner, then a column of circular nodes — so the
 * page does not jump when the data arrives, and the learner never sees a blank
 * screen.
 */

export default function LearnLoading() {
  return (
    <div className="min-h-dvh lg:pl-64">
      <div className="h-16 border-b-2 border-border bg-surface" />
      <div className="mx-auto w-full max-w-path px-4 pt-6">
        <div className="flex animate-pulse flex-col gap-6" aria-hidden="true">
          <div className="h-6 w-40 rounded-full bg-border" />
          <div className="h-24 rounded-2xl bg-border" />
          <div className="flex flex-col items-center gap-8 pt-4">
            {[0, 1, 2].map((index) => (
              <div key={index} className="flex flex-col items-center gap-2">
                <div className="h-22 w-22 rounded-full bg-border" style={{ height: 88, width: 88 }} />
                <div className="h-3 w-24 rounded-full bg-border" />
              </div>
            ))}
          </div>
        </div>
        <p className="sr-only" role="status">
          Loading your learning path…
        </p>
      </div>
    </div>
  );
}
