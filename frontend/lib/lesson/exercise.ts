/**
 * Turning the backend's generic exercise payload into a discriminated union.
 *
 * The API sends `data` as an untyped JSON object, because five exercise types
 * carry five different shapes and the backend deliberately validates them in its
 * graders rather than in a Pydantic union (backend ADR-33). That is the right
 * call server-side, but it leaves the client with `Record<string, unknown>`,
 * which every renderer would otherwise have to cast its way out of.
 *
 * This module narrows once, at the boundary, into a real discriminated union.
 * After `narrowExercise`, each renderer receives a precisely typed shape and
 * needs no casts and no `any`. TypeScript also enforces exhaustiveness: adding a
 * sixth exercise type produces a compile error in `ExerciseRenderer` until it is
 * handled.
 *
 * Narrowing validates as it goes and returns `null` for a payload it does not
 * recognise, so a malformed exercise renders an error card instead of crashing
 * the lesson.
 */

import type { AnswerPayload, ExercisePublic } from "@/lib/api/types";

/** An `{id, text}` pair, used by choice options and both match-pairs columns. */
export interface ChoiceOption {
  id: string;
  text: string;
}

export type NarrowedExercise =
  | { type: "MULTIPLE_CHOICE"; base: ExercisePublic; options: ChoiceOption[] }
  | { type: "TRANSLATE"; base: ExercisePublic; tokens: string[] }
  | {
      type: "MATCH_PAIRS";
      base: ExercisePublic;
      left: ChoiceOption[];
      right: ChoiceOption[];
    }
  | {
      type: "FILL_BLANK";
      base: ExercisePublic;
      sentence: string;
      options: string[];
    }
  | { type: "TYPE_ANSWER"; base: ExercisePublic; language: string };

function isChoiceOptionArray(value: unknown): value is ChoiceOption[] {
  return (
    Array.isArray(value) &&
    value.every(
      (item) =>
        typeof item === "object" &&
        item !== null &&
        typeof (item as ChoiceOption).id === "string" &&
        typeof (item as ChoiceOption).text === "string",
    )
  );
}

function isStringArray(value: unknown): value is string[] {
  return Array.isArray(value) && value.every((item) => typeof item === "string");
}

/**
 * Narrow a raw exercise into its typed variant.
 *
 * @returns the narrowed exercise, or `null` if `data` does not match the shape
 *   its `type` promises.
 */
export function narrowExercise(
  exercise: ExercisePublic,
): NarrowedExercise | null {
  const data = exercise.data;

  switch (exercise.type) {
    case "MULTIPLE_CHOICE": {
      const options = data.options;
      return isChoiceOptionArray(options)
        ? { type: "MULTIPLE_CHOICE", base: exercise, options }
        : null;
    }
    case "TRANSLATE": {
      const tokens = data.tokens;
      return isStringArray(tokens)
        ? { type: "TRANSLATE", base: exercise, tokens }
        : null;
    }
    case "MATCH_PAIRS": {
      const { left, right } = data;
      return isChoiceOptionArray(left) && isChoiceOptionArray(right)
        ? { type: "MATCH_PAIRS", base: exercise, left, right }
        : null;
    }
    case "FILL_BLANK": {
      const { sentence, options } = data;
      return typeof sentence === "string" && isStringArray(options)
        ? { type: "FILL_BLANK", base: exercise, sentence, options }
        : null;
    }
    case "TYPE_ANSWER": {
      const language = data.language;
      return {
        type: "TYPE_ANSWER",
        base: exercise,
        language: typeof language === "string" ? language : "es",
      };
    }
    default:
      return null;
  }
}

/**
 * The instruction line shown above a prompt, when the backend has not supplied
 * one. Purely presentational — it never affects grading.
 */
export const DEFAULT_INSTRUCTIONS: Record<ExercisePublic["type"], string> = {
  MULTIPLE_CHOICE: "Select the correct translation",
  TRANSLATE: "Translate this sentence",
  MATCH_PAIRS: "Match the pairs",
  FILL_BLANK: "Fill in the blank",
  TYPE_ANSWER: "Type this in Spanish",
};

/**
 * A draft answer, or `null` when the learner has not supplied enough to submit.
 *
 * Exercise components own their own input state and report upward through this
 * type. `null` is the UI-level "not ready" signal — nothing selected, an empty
 * input, or incomplete pairs — and it is the *only* judgement the client makes
 * about an answer. Whether it is *correct* is never decided here.
 */
export type DraftAnswer = AnswerPayload | null;

/**
 * Compile-time exhaustiveness guard.
 *
 * Passing a value typed `never` proves every variant of a union has been
 * handled; if a new variant is added, the call stops compiling. Returning the
 * fallback keeps the runtime behaviour sane if bad data ever slips through.
 */
export function assertNever<T>(value: never, fallback: T): T {
  void value;
  return fallback;
}
