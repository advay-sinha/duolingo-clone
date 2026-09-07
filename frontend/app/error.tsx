"use client";

/**
 * The last line of defence for an unexpected rendering error.
 *
 * Every page already turns a *failed request* into a value and renders its own
 * error screen — that is the common case and it stays where it is. What was not
 * covered is the uncommon one: a response that arrives successfully but is
 * shaped wrongly, so the failure happens during render rather than during fetch.
 * Without this file Next.js falls back to its own error page, which in
 * production is an unstyled "Application error" with no way back into the app.
 *
 * `error.tsx` must be a Client Component — React needs an error boundary, and
 * error boundaries only exist on the client.
 *
 * The thrown message is deliberately **not** shown. It is written by whatever
 * threw, could be an internal stack or a serialisation detail, and means nothing
 * to a learner. `digest` is the hash Next.js also logs on the server, so it is
 * the one thing worth surfacing: it lets the same incident be found in the logs.
 */

import Link from "next/link";

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <main className="mx-auto flex min-h-dvh max-w-md flex-col items-center justify-center gap-5 px-4 text-center">
      <div className="flex h-20 w-20 items-center justify-center rounded-full bg-border/60">
        <span className="text-4xl" aria-hidden="true">
          ⚠️
        </span>
      </div>
      <h1 className="text-headline-lg text-text">Something went wrong</h1>
      <p className="text-body-md text-text-secondary">
        This screen could not be displayed. Trying again usually fixes it.
      </p>
      <div className="flex w-full flex-col gap-2">
        <button type="button" onClick={reset} className="tactile btn-primary w-full">
          Try again
        </button>
        <Link
          href="/learn"
          className="text-label-md uppercase text-text-secondary underline"
        >
          Back to learning path
        </Link>
      </div>
      {error.digest && (
        <p className="text-caption text-text-disabled">
          Reference: {error.digest}
        </p>
      )}
    </main>
  );
}
