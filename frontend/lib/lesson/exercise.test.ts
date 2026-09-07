/**
 * Tests for exercise narrowing.
 *
 * The boundary where the backend's generic `data` object becomes a typed
 * discriminated union. Getting this wrong would surface as a renderer crash on
 * one exercise type only — worth covering all five plus the malformed case.
 */

import assert from "node:assert/strict";
import test from "node:test";

import type { ExercisePublic } from "@/lib/api/types";
import { narrowExercise } from "./exercise.ts";

function raw(
  type: ExercisePublic["type"],
  data: Record<string, unknown>,
): ExercisePublic {
  return { id: 1, type, order_index: 0, instruction: "", prompt: "p", data };
}

test("multiple choice narrows to its options", () => {
  const narrowed = narrowExercise(
    raw("MULTIPLE_CHOICE", {
      options: [
        { id: "o1", text: "Hola" },
        { id: "o2", text: "Adiós" },
      ],
    }),
  );

  assert.equal(narrowed?.type, "MULTIPLE_CHOICE");
  if (narrowed?.type !== "MULTIPLE_CHOICE") return;
  assert.equal(narrowed.options.length, 2);
  assert.equal(narrowed.options[0].text, "Hola");
});

test("translate narrows to its token pool", () => {
  const narrowed = narrowExercise(
    raw("TRANSLATE", { tokens: ["buenos", "días"] }),
  );

  assert.equal(narrowed?.type, "TRANSLATE");
  if (narrowed?.type !== "TRANSLATE") return;
  assert.deepEqual(narrowed.tokens, ["buenos", "días"]);
});

test("match pairs narrows to both columns", () => {
  const narrowed = narrowExercise(
    raw("MATCH_PAIRS", {
      left: [{ id: "l1", text: "hola" }],
      right: [{ id: "r1", text: "hello" }],
    }),
  );

  assert.equal(narrowed?.type, "MATCH_PAIRS");
  if (narrowed?.type !== "MATCH_PAIRS") return;
  assert.equal(narrowed.left[0].text, "hola");
  assert.equal(narrowed.right[0].id, "r1");
});

test("fill blank narrows to its sentence and options", () => {
  const narrowed = narrowExercise(
    raw("FILL_BLANK", { sentence: "___ días", options: ["Buenos", "Buenas"] }),
  );

  assert.equal(narrowed?.type, "FILL_BLANK");
  if (narrowed?.type !== "FILL_BLANK") return;
  assert.ok(narrowed.sentence.includes("___"));
  assert.equal(narrowed.options.length, 2);
});

test("type answer narrows and defaults its language", () => {
  const narrowed = narrowExercise(raw("TYPE_ANSWER", {}));

  assert.equal(narrowed?.type, "TYPE_ANSWER");
  if (narrowed?.type !== "TYPE_ANSWER") return;
  assert.equal(narrowed.language, "es");
});

test("a payload that does not match its type narrows to null", () => {
  // Renders an error card instead of crashing the whole lesson.
  assert.equal(narrowExercise(raw("MULTIPLE_CHOICE", {})), null);
  assert.equal(narrowExercise(raw("TRANSLATE", { tokens: "nope" })), null);
  assert.equal(
    narrowExercise(raw("MATCH_PAIRS", { left: [{ id: 1 }], right: [] })),
    null,
  );
  assert.equal(narrowExercise(raw("FILL_BLANK", { sentence: 5 })), null);
});

test("narrowing never exposes an answer field", () => {
  // The API cannot send one, but this asserts the client does not invent one.
  const narrowed = narrowExercise(
    raw("MULTIPLE_CHOICE", { options: [{ id: "o1", text: "Hola" }] }),
  );

  assert.ok(narrowed);
  assert.equal("correct_answer" in narrowed, false);
  assert.equal("answer" in narrowed, false);
});
