"use client";

/**
 * "Which course do you want?" — the Stitch course grid.
 *
 * **The real course comes from the API; the rest are honestly labelled scenery.**
 * The brief is explicit that no fake courses should be invented to fill the grid,
 * so none were: `courses` below is whatever `GET /courses` returned (one row,
 * English → Spanish), and everything after it is a disabled tile from a static
 * list that makes no request and has no id to send. A learner cannot select one,
 * and neither can a hand-written request — the backend validates the id against
 * the courses table.
 *
 * Not a `role="radiogroup"`, unlike the proficiency list: a group whose options
 * are mostly disabled is a poor fit for the roving-tabindex pattern, and the
 * disabled tiles are genuinely not options. They are `<button disabled>` rather
 * than styled `<div>`s so assistive technology reports them as unavailable
 * controls instead of ignoring them.
 */

import { useRouter } from "next/navigation";
import { useState } from "react";

import { selectCourse } from "@/lib/api/onboarding";
import type { CourseSummary } from "@/lib/api/types";
import { COMING_SOON_COURSES, courseFlag } from "@/lib/onboarding/options";

import { OnboardingError } from "./OnboardingError";

export function CoursePicker({
  courses,
  initial,
}: {
  courses: CourseSummary[];
  /** The learner's existing choice, so a refresh shows it selected. */
  initial: number | null;
}) {
  const router = useRouter();
  const [selected, setSelected] = useState<number | null>(
    initial ?? (courses.length === 1 ? courses[0].id : null),
  );
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit() {
    if (selected === null || busy) return;
    setBusy(true);
    setError(null);
    try {
      await selectCourse(selected);
      router.refresh();
      router.push("/onboarding/proficiency");
    } catch {
      setError("That course could not be selected. Please try again.");
      setBusy(false);
    }
  }

  return (
    <>
      <ul className="grid grid-cols-2 gap-3 sm:grid-cols-3">
        {courses.map((course) => {
          const isSelected = course.id === selected;
          return (
            <li key={course.id}>
              <button
                type="button"
                aria-pressed={isSelected}
                // Explicit, because a name assembled from adjacent elements has
                // no reliable word separator — the tile below announces as
                // "FrenchComing soon" without one.
                aria-label={`${course.title}, ${course.source_language} to ${course.target_language}`}
                disabled={busy}
                onClick={() => setSelected(course.id)}
                className={[
                  "tactile flex min-h-32 w-full flex-col items-center justify-center gap-2 p-4",
                  isSelected
                    ? "border-blue bg-blue/10"
                    : "border-border bg-surface hover:bg-surface-subtle",
                ].join(" ")}
                style={{
                  borderBottomColor: isSelected
                    ? "var(--color-blue-depth)"
                    : "var(--color-border-depth)",
                }}
              >
                <span aria-hidden="true" className="text-4xl">
                  {courseFlag(course.flag_emoji)}
                </span>
                <span className="text-label-bold text-text">{course.title}</span>
                <span className="text-caption text-text-secondary">
                  {course.source_language} → {course.target_language}
                </span>
              </button>
            </li>
          );
        })}

        {COMING_SOON_COURSES.map((course) => (
          <li key={course.key}>
            <button
              type="button"
              disabled
              aria-disabled="true"
              aria-label={`${course.title}, coming soon`}
              className="card flex min-h-32 w-full cursor-not-allowed flex-col items-center justify-center gap-2 p-4 opacity-60"
            >
              <span aria-hidden="true" className="text-4xl grayscale">
                {course.flag}
              </span>
              <span className="text-label-bold text-text-disabled">
                {course.title}
              </span>
              {/* Part of the accessible name, not decoration: without it the
                  control announces only "French, dimmed" and the reason is
                  carried by colour alone. */}
              <span className="text-caption uppercase text-text-disabled">
                Coming soon
              </span>
            </button>
          </li>
        ))}
      </ul>

      <OnboardingError message={error} />

      <div className="fixed inset-x-0 bottom-0 z-30 border-t-2 border-border bg-surface">
        <div className="mx-auto w-full max-w-2xl px-4 py-4">
          <button
            type="button"
            onClick={() => void submit()}
            disabled={selected === null || busy}
            className="tactile btn-primary w-full disabled:cursor-not-allowed disabled:bg-border disabled:text-text-disabled"
            style={
              selected === null || busy
                ? {
                    borderColor: "var(--color-border)",
                    borderBottomColor: "var(--color-border-depth)",
                  }
                : undefined
            }
          >
            {busy ? "Saving…" : "Continue"}
          </button>
        </div>
      </div>
    </>
  );
}
