"use client";

/**
 * The celebration screen.
 *
 * Every figure here comes from the completion response — XP, accuracy, streak,
 * crowns. None of it is recomputed client-side, which matters: if the learner
 * replays a finished lesson the server returns `first_completion: false` and
 * `xp_earned: 0`, and this screen says so honestly rather than showing a number
 * it made up.
 */

import type { CompleteLessonResponse } from "@/lib/api/types";

interface Props {
  result: CompleteLessonResponse;
  onDone: () => void;
}

function Stat({
  label,
  value,
  tone,
}: {
  label: string;
  value: string;
  tone: "gold" | "green" | "orange" | "blue";
}) {
  const colors = {
    gold: "border-gold text-gold-depth",
    green: "border-green text-green-depth",
    orange: "border-orange text-orange-depth",
    blue: "border-blue text-blue-depth",
  } as const;

  return (
    <div
      className={`flex flex-col items-center gap-1 rounded-2xl border-2 ${colors[tone]} bg-surface px-4 py-3`}
    >
      <span className="text-label-md uppercase opacity-80">{label}</span>
      <span className="text-headline-lg tabular-nums">{value}</span>
    </div>
  );
}

export function LessonComplete({ result, onDone }: Props) {
  const accuracy = Math.round(result.accuracy * 100);

  return (
    <div className="mx-auto flex w-full max-w-2xl flex-1 flex-col items-center justify-center gap-8 px-4 py-10 text-center">
      <div className="animate-pop-in flex flex-col items-center gap-4">
        <div className="flex h-24 w-24 items-center justify-center rounded-full bg-gold/20">
          <svg width="56" height="56" viewBox="0 0 24 24" aria-hidden="true">
            <path
              d="M12 2l2.6 6.3 6.8.5-5.2 4.4 1.6 6.6L12 16.3 6.2 19.8l1.6-6.6L2.6 8.8l6.8-.5z"
              fill="var(--color-gold)"
              stroke="var(--color-gold-depth)"
              strokeWidth="1"
            />
          </svg>
        </div>
        <h1 className="text-display-hero text-green-depth">Lesson complete!</h1>
        <p className="text-body-lg text-text-secondary">
          {result.first_completion
            ? "Great work — your progress is saved."
            : "Practice run — no extra XP this time, but your streak counts."}
        </p>
      </div>

      <div className="grid w-full grid-cols-2 gap-3 sm:grid-cols-4">
        <Stat label="XP earned" value={`+${result.xp_earned}`} tone="gold" />
        <Stat label="Accuracy" value={`${accuracy}%`} tone="green" />
        <Stat label="Streak" value={`${result.current_streak}`} tone="orange" />
        <Stat
          label="Hearts"
          value={`${result.hearts_remaining}`}
          tone="blue"
        />
      </div>

      <div className="w-full rounded-2xl border-2 border-border bg-surface p-5 text-left"
           style={{ borderBottomWidth: "4px", borderBottomColor: "var(--color-border-depth)" }}>
        <div className="flex items-center justify-between gap-3">
          <span className="text-label-md uppercase text-text-secondary">
            Skill progress
          </span>
          <span className="text-body-sm text-text-secondary tabular-nums">
            {result.lessons_completed} / {result.total_lessons} lessons
          </span>
        </div>
        <div className="mt-2 h-3 overflow-hidden rounded-full bg-border">
          <div
            className="h-full rounded-full bg-green transition-[width] duration-700"
            style={{
              width: `${
                result.total_lessons > 0
                  ? (result.lessons_completed / result.total_lessons) * 100
                  : 0
              }%`,
            }}
          />
        </div>
        {result.crown_earned && (
          <p className="mt-3 flex items-center gap-2 text-body-md text-gold-depth">
            <span aria-hidden="true">👑</span> Crown earned — the next skill is
            unlocked.
          </p>
        )}
      </div>

      <div className="flex w-full flex-col gap-2">
        <p className="text-body-sm text-text-secondary tabular-nums">
          Total XP {result.total_xp} · Today {result.daily_xp} / {result.daily_goal}
        </p>
        <button
          type="button"
          onClick={onDone}
          className="tactile btn-primary w-full"
        >
          Continue
        </button>
      </div>
    </div>
  );
}
