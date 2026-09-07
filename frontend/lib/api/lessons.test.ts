/**
 * Tests for the lesson API bindings.
 *
 * These assert the contract between binding and client — path, HTTP method, and
 * body — not backend behaviour, which the Python suite covers. A POST sent as a
 * GET, or a body serialised wrongly, is the kind of bug that only shows up at
 * runtime.
 */

import assert from "node:assert/strict";
import test from "node:test";

import {
  completeLesson,
  getLesson,
  startLesson,
  submitAnswer,
} from "./lessons.ts";

interface Captured {
  url: string;
  method: string;
  body: unknown;
}

/** Capture the request a binding makes, returning `response` as its result. */
async function capture(
  call: () => Promise<unknown>,
  response: unknown = {},
): Promise<Captured> {
  const original = globalThis.fetch;
  let captured: Captured = { url: "", method: "GET", body: undefined };

  globalThis.fetch = async (input, init) => {
    captured = {
      url: String(input),
      method: init?.method ?? "GET",
      body: init?.body ? JSON.parse(String(init.body)) : undefined,
    };
    return new Response(JSON.stringify(response), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  };

  try {
    await call();
  } finally {
    globalThis.fetch = original;
  }
  return captured;
}

test("getLesson requests the lesson by id", async () => {
  const { url, method } = await capture(() => getLesson(12));
  assert.ok(url.endsWith("/lessons/12"), url);
  assert.equal(method, "GET");
});

test("startLesson POSTs to /start with no body", async () => {
  const { url, method, body } = await capture(() => startLesson(12));
  assert.ok(url.endsWith("/lessons/12/start"), url);
  assert.equal(method, "POST");
  assert.equal(body, undefined);
});

test("submitAnswer POSTs the attempt, exercise and answer", async () => {
  const { url, method, body } = await capture(() =>
    submitAnswer(12, {
      attempt_id: 44,
      exercise_id: 7,
      answer: { option_id: "o2" },
    }),
  );

  assert.ok(url.endsWith("/lessons/12/answer"), url);
  assert.equal(method, "POST");
  assert.deepEqual(body, {
    attempt_id: 44,
    exercise_id: 7,
    answer: { option_id: "o2" },
  });
});

test("submitAnswer carries word-bank tokens unchanged", async () => {
  const { body } = await capture(() =>
    submitAnswer(12, {
      attempt_id: 44,
      exercise_id: 8,
      answer: { tokens: ["buenos", "días"] },
    }),
  );
  assert.deepEqual((body as { answer: { tokens: string[] } }).answer.tokens, [
    "buenos",
    "días",
  ]);
});

test("completeLesson POSTs only the attempt id", async () => {
  const { url, method, body } = await capture(() =>
    completeLesson(12, { attempt_id: 44 }),
  );

  assert.ok(url.endsWith("/lessons/12/complete"), url);
  assert.equal(method, "POST");
  // No score, no correct count -- the server is authoritative.
  assert.deepEqual(body, { attempt_id: 44 });
});

test("an answer verdict is returned to the caller unchanged", async () => {
  const original = globalThis.fetch;
  globalThis.fetch = async () =>
    new Response(
      JSON.stringify({
        correct: false,
        correct_answer: "buenos días",
        xp_earned: 0,
        hearts_remaining: 4,
        already_answered: false,
        answered_count: 1,
        total_exercises: 5,
      }),
      { status: 200, headers: { "Content-Type": "application/json" } },
    );
  try {
    const verdict = await submitAnswer(1, {
      attempt_id: 1,
      exercise_id: 1,
      answer: { text: "wrong" },
    });
    assert.equal(verdict.correct, false);
    assert.equal(verdict.correct_answer, "buenos días");
    assert.equal(verdict.hearts_remaining, 4);
  } finally {
    globalThis.fetch = original;
  }
});
