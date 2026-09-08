"use client";

/**
 * Dispatches an exercise to the component that knows how to render it.
 *
 * A `switch` over a discriminated union, not a chain of `if (type === ...)`
 * checks — which means TypeScript narrows the payload for each branch (no casts,
 * no `any`) and the `never` in the default branch makes **exhaustiveness a
 * compile error**. Add a sixth exercise type to the union and this file stops
 * compiling until it is handled, which is exactly the reminder you want.
 *
 * Exercise components below this line know nothing about attempts, HTTP, XP or
 * hearts. They render a payload and report a draft answer upward. All API
 * coordination lives in `LessonPlayer`.
 */

import type { SubmitPairResponse } from "@/lib/api/types";
import { assertNever } from "@/lib/lesson/exercise";
import type {
  DraftAnswer,
  ExerciseVerdict,
  NarrowedExercise,
} from "@/lib/lesson/exercise";

import { FillBlankExercise } from "./exercises/FillBlankExercise";
import { MatchPairsExercise } from "./exercises/MatchPairsExercise";
import { MultipleChoiceExercise } from "./exercises/MultipleChoiceExercise";
import { TranslateExercise } from "./exercises/TranslateExercise";
import { TypeAnswerExercise } from "./exercises/TypeAnswerExercise";

/** Props every exercise component receives. */
export interface ExerciseComponentProps {
  /** True once submitted — inputs lock so a graded answer cannot be edited. */
  disabled: boolean;
  /**
   * The server's verdict, or null before submission. Drives result colours.
   *
   * Deliberately narrow: only `correct` is needed, which is what lets the
   * placement test reuse these renderers without inventing XP and heart fields
   * an assessment does not have.
   */
  verdict: ExerciseVerdict | null;
  /** Report the answer so far, or null when there is not enough to submit. */
  onDraftChange: (draft: DraftAnswer) => void;
  /** Request submission (used by Enter-to-submit in text exercises). */
  onSubmit: () => void;
}

interface Props extends ExerciseComponentProps {
  exercise: NarrowedExercise;
  /**
   * Grade one match-pairs selection.
   *
   * Only match pairs uses it, and only match pairs *can* — every other exercise
   * has a single answer submitted through `onSubmit`. It is required rather than
   * optional so the player cannot forget to supply it and leave the exercise
   * silently unplayable.
   */
  onSubmitPair: (leftId: string, rightId: string) => Promise<SubmitPairResponse>;
}

export function ExerciseRenderer({
  exercise,
  onSubmitPair,
  ...shared
}: Props) {
  switch (exercise.type) {
    case "MULTIPLE_CHOICE":
      return <MultipleChoiceExercise {...shared} options={exercise.options} />;

    case "TRANSLATE":
      return <TranslateExercise {...shared} tokens={exercise.tokens} />;

    case "MATCH_PAIRS":
      return (
        <MatchPairsExercise
          {...shared}
          left={exercise.left}
          right={exercise.right}
          onSubmitPair={onSubmitPair}
        />
      );

    case "FILL_BLANK":
      return (
        <FillBlankExercise
          {...shared}
          sentence={exercise.sentence}
          options={exercise.options}
        />
      );

    case "TYPE_ANSWER":
      return <TypeAnswerExercise {...shared} language={exercise.language} />;

    default:
      // Compile-time exhaustiveness: a new exercise type breaks this line
      // until it is handled above.
      return assertNever(exercise, null);
  }
}
