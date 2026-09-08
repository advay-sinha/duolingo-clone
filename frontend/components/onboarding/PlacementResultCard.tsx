/**
 * "We found your starting point!"
 *
 * Shown once the test is scored. Three things are said, in this order, because
 * that is the order a learner cares about them:
 *
 * 1. where they start,
 * 2. how they did,
 * 3. what happens to the material they skipped.
 *
 * **No XP, no hearts, no crowns appear here** — not zeroed, absent. Placement is
 * an assessment, and a results screen that showed "0 XP" would invite the
 * question of why the learner had not earned any.
 */

import type { PlacementResult } from "@/lib/api/types";

export function PlacementResultCard({
  result,
  onContinue,
}: {
  result: PlacementResult;
  onContinue: () => void;
}) {
  const placedOut = result.skills_placed_out;

  return (
    <div className="mx-auto flex min-h-dvh w-full max-w-md flex-col items-center justify-center gap-6 px-4 py-10 text-center">
      <div className="animate-pop-in flex h-24 w-24 items-center justify-center rounded-full bg-green/15">
        <span aria-hidden="true" className="text-5xl">
          🎯
        </span>
      </div>

      <div className="flex flex-col gap-2">
        <h1 className="text-headline-xl text-text">
          We found your starting point!
        </h1>
        <p className="text-body-lg text-text-secondary">
          You can start learning from{" "}
          <strong className="text-text">{result.skill_title}</strong> in{" "}
          {result.unit_title}.
        </p>
      </div>

      <dl className="card grid w-full grid-cols-2 gap-4 p-5 text-left">
        <div>
          <dt className="text-caption uppercase text-text-secondary">Level</dt>
          <dd className="text-headline-md tabular-nums text-text">
            {result.level} / 5
          </dd>
        </div>
        <div>
          <dt className="text-caption uppercase text-text-secondary">Correct</dt>
          <dd className="text-headline-md tabular-nums text-text">
            {result.correct_answers} / {result.total_questions}
          </dd>
        </div>
        <div className="col-span-2">
          <dt className="text-caption uppercase text-text-secondary">
            Weighted score
          </dt>
          <dd className="text-body-md tabular-nums text-text">
            {result.score} of {result.max_score} — harder questions count for
            more
          </dd>
        </div>
      </dl>

      <p className="text-body-sm text-text-secondary">
        {placedOut === 0
          ? "You'll start at the very beginning of the course — the best place to build from."
          : `${placedOut} earlier ${placedOut === 1 ? "skill is" : "skills are"} marked as placed out. They stay unlocked, so you can practise them whenever you like.`}
      </p>

      <button
        type="button"
        onClick={onContinue}
        className="tactile btn-primary w-full"
      >
        Start learning
      </button>
    </div>
  );
}
