/**
 * Phase 1 placeholder shell.
 *
 * Deliberately minimal: a header, a centred content area, and proof that the
 * frontend can reach the backend. The real learning-path screen is Phase 6 —
 * this page exists only to show the foundation works end to end.
 */

import { BackendStatus } from "@/components/BackendStatus";

export default function Home() {
  return (
    <div className="flex min-h-full flex-col">
      <header className="border-b-2 border-border bg-surface">
        <div className="mx-auto flex h-16 max-w-content items-center px-4">
          <span className="text-headline-lg lowercase text-green">duolingo</span>
          <span className="ml-3 rounded-full bg-surface-subtle px-3 py-1 text-caption uppercase text-text-secondary">
            clone
          </span>
        </div>
      </header>

      <main className="mx-auto flex w-full max-w-content flex-1 flex-col items-center gap-8 px-4 py-16">
        <div className="text-center">
          <h1 className="text-display-hero text-text">Duolingo Clone</h1>
          <p className="mt-2 text-body-lg text-text-secondary">
            Phase 1 — foundation. Next.js and FastAPI are wired together.
          </p>
        </div>

        <div className="w-full max-w-xl">
          <BackendStatus />
        </div>

        {/* Tactile foundation preview: the extruded press behaviour every
            component in Phase 5 will inherit. */}
        <div className="flex flex-wrap items-center justify-center gap-4">
          <button type="button" className="tactile btn-primary">
            Primary
          </button>
          <button type="button" className="tactile btn-secondary">
            Secondary
          </button>
        </div>

        <p className="max-w-prose text-center text-body-sm text-text-secondary">
          Not implemented yet: database, learning path, lesson player, XP,
          hearts, streak, leaderboard and profile. See{" "}
          <code>docs/CODEBASE_LEARNING.md</code> for the current status.
        </p>
      </main>
    </div>
  );
}
