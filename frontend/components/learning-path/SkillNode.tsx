"use client";

/**
 * One node on the learning path.
 *
 * Renders the state the **server** decided — `skill.state` — in four visual
 * variants. The fourth, "in progress", is not a backend state: it is
 * `AVAILABLE` with `lessons_completed > 0`, derived in `lib/learn/path.ts`. No
 * unlock logic exists here or anywhere else in the frontend.
 *
 * A locked skill renders as a `<button disabled>`, not a styled `<div>`, so
 * assistive technology reports it as a disabled control rather than silently
 * ignoring it — and so it cannot be clicked into a lesson.
 */

import type { SkillNode as SkillNodeData } from "@/lib/api/types";
import {
  isSkillPlayable,
  ringFraction,
  skillStateLabel,
  skillVisual,
} from "@/lib/learn/path";

import { SkillProgressRing } from "./SkillProgressRing";

const NODE_SIZE = 88;

/** Glyph per state. Crown for completed, lock for locked, star otherwise. */
function NodeGlyph({ variant }: { variant: ReturnType<typeof skillVisual> }) {
  if (variant === "locked") {
    return (
      <svg width="30" height="30" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
        <path d="M12 2a5 5 0 0 0-5 5v3H6a2 2 0 0 0-2 2v8a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-8a2 2 0 0 0-2-2h-1V7a5 5 0 0 0-5-5zm0 2a3 3 0 0 1 3 3v3H9V7a3 3 0 0 1 3-3z" />
      </svg>
    );
  }
  if (variant === "completed") {
    return (
      <svg width="34" height="34" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
        <path d="M5 16 3 6l5 3 4-6 4 6 5-3-2 10H5zm0 2h14v2H5v-2z" />
      </svg>
    );
  }
  return (
    <svg width="32" height="32" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
      <path d="M12 2.5 14.9 8l6.1.9-4.4 4.3 1 6.1-5.6-3-5.6 3 1-6.1L3 8.9 9.1 8 12 2.5z" />
    </svg>
  );
}

interface Props {
  skill: SkillNodeData;
  /** Horizontal offset in px, producing the winding path. Dropped on mobile. */
  offset: number;
  onSelect: (skill: SkillNodeData) => void;
}

export function SkillNode({ skill, offset, onSelect }: Props) {
  const variant = skillVisual(skill);
  const playable = isSkillPlayable(skill);

  const palette = {
    locked: {
      bg: "bg-border",
      border: "border-border",
      depth: "var(--color-border-depth)",
      text: "text-text-disabled",
      ring: "var(--color-border)",
    },
    available: {
      bg: "bg-blue",
      border: "border-blue",
      depth: "var(--color-blue-depth)",
      text: "text-white",
      ring: "var(--color-blue)",
    },
    "in-progress": {
      bg: "bg-green",
      border: "border-green",
      depth: "var(--color-green-depth)",
      text: "text-white",
      ring: "var(--color-green)",
    },
    completed: {
      bg: "bg-gold",
      border: "border-gold",
      depth: "var(--color-gold-depth)",
      text: "text-white",
      ring: "var(--color-gold)",
    },
  }[variant];

  return (
    <li
      className="flex flex-col items-center gap-2"
      // The wind is decorative and is dropped below `sm`, where a narrow screen
      // needs the full width for the node itself.
      style={{ ["--wind" as string]: `${offset}px` }}
    >
      <div className="translate-x-0 sm:translate-x-[var(--wind)]">
        <SkillProgressRing
          fraction={ringFraction(skill)}
          size={NODE_SIZE}
          color={palette.ring}
        >
          <button
            type="button"
            disabled={!playable}
            aria-disabled={!playable}
            onClick={() => onSelect(skill)}
            className={`tactile flex h-16 w-16 items-center justify-center rounded-full ${palette.bg} ${palette.border} ${palette.text} disabled:cursor-not-allowed`}
            style={{ borderBottomColor: palette.depth }}
          >
            <NodeGlyph variant={variant} />
            {/* The visual state is colour and iconography; this is what a
                screen reader hears instead. */}
            <span className="sr-only">
              {skill.title}. {skillStateLabel(skill)}
            </span>
          </button>
        </SkillProgressRing>
      </div>

      <div className="flex flex-col items-center gap-0.5 sm:translate-x-[var(--wind)]">
        <span
          className={`text-label-md uppercase ${
            variant === "locked" ? "text-text-disabled" : "text-text"
          }`}
          aria-hidden="true"
        >
          {skill.title}
        </span>
        <span className="text-caption tabular-nums text-text-secondary" aria-hidden="true">
          {variant === "locked"
            ? "Locked"
            : `${skill.lessons_completed}/${skill.total_lessons}`}
          {skill.crowns > 0 && ` · ${skill.crowns} 👑`}
        </span>
      </div>
    </li>
  );
}
