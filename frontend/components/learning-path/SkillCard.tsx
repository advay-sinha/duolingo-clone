"use client";

/**
 * The popover shown when a playable skill is tapped.
 *
 * A lightweight confirmation step before entering a lesson — it names the skill,
 * shows progress from the API, and says which lesson the button will open. That
 * last part matters: "Continue" is otherwise a slightly mysterious action, and
 * naming the lesson makes the selection rule visible to the learner.
 *
 * Deliberately not a modal framework: a fixed-position card, a scrim, `Escape`
 * to close, and focus moved to the primary action. Anything more would be
 * infrastructure this screen does not need.
 */

import { useEffect, useRef } from "react";

import type { LessonNode, SkillNode } from "@/lib/api/types";
import { skillVisual } from "@/lib/learn/path";

interface Props {
  skill: SkillNode;
  lesson: LessonNode | null;
  onStart: () => void;
  onClose: () => void;
}

export function SkillCard({ skill, lesson, onStart, onClose }: Props) {
  const startRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    startRef.current?.focus();

    function onKey(event: KeyboardEvent) {
      if (event.key === "Escape") onClose();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const variant = skillVisual(skill);
  const replaying = variant === "completed";
  const started = skill.lessons_completed > 0;

  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center sm:items-center">
      <button
        type="button"
        aria-label="Close"
        onClick={onClose}
        className="absolute inset-0 bg-black/40"
      />

      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="skill-card-title"
        className="animate-pop-in relative m-4 w-full max-w-sm rounded-2xl border-2 border-border bg-surface p-5"
        style={{ borderBottomWidth: 4, borderBottomColor: "var(--color-border-depth)" }}
      >
        <h3 id="skill-card-title" className="text-headline-lg text-text">
          {skill.title}
        </h3>
        {skill.description && (
          <p className="mt-1 text-body-md text-text-secondary">
            {skill.description}
          </p>
        )}

        <div className="mt-4 flex items-center justify-between text-body-sm text-text-secondary">
          <span className="tabular-nums">
            {skill.lessons_completed} of {skill.total_lessons} lessons
          </span>
          {skill.crowns > 0 && (
            <span className="text-gold-depth">
              {skill.crowns} crown{skill.crowns === 1 ? "" : "s"}
            </span>
          )}
        </div>

        <div className="mt-2 h-3 overflow-hidden rounded-full bg-border">
          <div
            className="h-full rounded-full bg-green transition-[width] duration-500"
            style={{
              width: `${
                skill.total_lessons > 0
                  ? (skill.lessons_completed / skill.total_lessons) * 100
                  : 0
              }%`,
            }}
          />
        </div>

        {lesson ? (
          <>
            <p className="mt-4 text-body-sm text-text-secondary">
              Next: <strong className="text-text">{lesson.title}</strong>
              {/* Replay is a real backend capability -- Phase 4 accepts a repeat
                  completion and awards no XP -- so the UI says so plainly
                  rather than pretending it is a fresh lesson. */}
              {replaying && " · practice, no XP"}
            </p>
            <button
              ref={startRef}
              type="button"
              onClick={onStart}
              className="tactile btn-primary mt-4 w-full"
            >
              {replaying ? "Practise" : started ? "Continue" : "Start"}
            </button>
          </>
        ) : (
          <p className="mt-4 text-body-sm text-text-secondary">
            This skill has no lessons yet.
          </p>
        )}

        <button
          type="button"
          onClick={onClose}
          className="mt-2 w-full py-2 text-label-md uppercase text-text-secondary hover:text-text"
        >
          Close
        </button>
      </div>
    </div>
  );
}
