"use client";

/**
 * The lesson's top bar: exit, progress, hearts.
 *
 * Follows the Stitch lesson player, which deliberately has no sidebar and no
 * app HUD — the lesson is a focus mode. The progress bar carries the glossy
 * highlight strip from the design spec.
 */

interface Props {
  /** Exercises answered so far. */
  completed: number;
  total: number;
  hearts: number;
  maxHearts: number;
  onExit: () => void;
}

export function LessonHeader({
  completed,
  total,
  hearts,
  maxHearts,
  onExit,
}: Props) {
  const percent = total > 0 ? Math.round((completed / total) * 100) : 0;

  return (
    <header className="flex w-full items-center gap-4 px-4 py-4 sm:gap-6">
      <button
        type="button"
        onClick={onExit}
        aria-label="Exit lesson"
        className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl text-text-secondary transition-colors hover:bg-surface-subtle hover:text-text"
      >
        <svg width="22" height="22" viewBox="0 0 24 24" aria-hidden="true">
          <path
            d="M6 6l12 12M18 6L6 18"
            stroke="currentColor"
            strokeWidth="3"
            strokeLinecap="round"
          />
        </svg>
      </button>

      {/* Progress. The local exercise index drives this -- it is a measure of
          how far through the lesson the learner is, not a claim about server
          state, which is why it does not wait for the completion response. */}
      <div
        className="relative h-4 flex-1 overflow-hidden rounded-full bg-border"
        role="progressbar"
        aria-valuenow={completed}
        aria-valuemin={0}
        aria-valuemax={total}
        aria-label={`Exercise ${Math.min(completed + 1, total)} of ${total}`}
      >
        <div
          className="relative h-full rounded-full bg-green transition-[width] duration-500 ease-out"
          style={{ width: `${percent}%` }}
        >
          {percent > 6 && (
            <span className="absolute inset-x-1 top-1 h-1 rounded-full bg-white/40" />
          )}
        </div>
      </div>

      <div
        className="flex shrink-0 items-center gap-1.5 rounded-full bg-red/10 px-3 py-1"
        aria-label={`${hearts} of ${maxHearts} hearts remaining`}
      >
        <svg width="20" height="20" viewBox="0 0 24 24" aria-hidden="true">
          <path
            d="M12 21s-7.5-4.7-9.3-9A5.2 5.2 0 0 1 12 6.5 5.2 5.2 0 0 1 21.3 12c-1.8 4.3-9.3 9-9.3 9z"
            fill="var(--color-red)"
          />
        </svg>
        <span className="text-headline-sm tabular-nums text-red">{hearts}</span>
      </div>
    </header>
  );
}
