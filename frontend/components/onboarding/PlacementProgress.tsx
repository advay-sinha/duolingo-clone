/**
 * The placement test's header: how far through, and how hard.
 *
 * **It deliberately does not look like the lesson header.** The lesson shows
 * hearts and a green XP rail; this shows a question counter and a difficulty
 * badge, because placement spends no hearts and awards no XP and the screen
 * should not imply otherwise. The eyebrow says "Placement test" in as many words
 * — a learner who mistakes this for a lesson would reasonably expect to be
 * rewarded for it.
 */

export function PlacementProgress({
  number,
  total,
  difficulty,
  levels,
  onExit,
}: {
  /** 1-based question number. */
  number: number;
  total: number;
  /** The difficulty band this question came from, 1-`levels`. */
  difficulty: number;
  levels: number;
  onExit: () => void;
}) {
  const percent = Math.round((Math.max(0, number - 1) / total) * 100);

  return (
    <header className="sticky top-0 z-30 border-b-2 border-border bg-surface">
      <div className="mx-auto flex w-full max-w-2xl flex-col gap-2 px-4 py-3">
        <div className="flex items-center justify-between gap-3">
          <span className="text-label-md uppercase text-text-secondary">
            Placement test
          </span>
          <button
            type="button"
            onClick={onExit}
            className="text-label-md uppercase text-text-secondary underline"
          >
            Exit
          </button>
        </div>

        <div className="flex items-center gap-3">
          <progress
            className="onboarding-rail h-4 flex-1"
            value={percent}
            max={100}
          >
            {percent}%
          </progress>
          <span className="shrink-0 rounded-full border-2 border-border bg-surface-subtle px-3 py-0.5 text-caption tabular-nums text-text-secondary">
            Level {difficulty}/{levels}
          </span>
        </div>

        {/* The counter is the accessible progress statement; the bar above is
            decorative reinforcement of it. */}
        <p className="text-body-sm tabular-nums text-text-secondary" aria-live="polite">
          Question {number} of {total}
        </p>
      </div>
    </header>
  );
}
