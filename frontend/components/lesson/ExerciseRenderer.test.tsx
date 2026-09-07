/**
 * Component tests for the exercise renderers.
 *
 * These assert **what a learner sees and can do** — which control appears, what
 * a click reports upward, what a verdict renders — not how any of it is
 * implemented. The pure-logic tests already cover the reducer and the payload
 * builders; this file covers the layer they could not reach.
 */

import { describe, expect, test, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import type { SubmitAnswerResponse, SubmitPairResponse } from "@/lib/api/types";
import type { NarrowedExercise } from "@/lib/lesson/exercise";

import { ExerciseRenderer } from "./ExerciseRenderer";

function base(over: Partial<{ id: number }> = {}) {
  return {
    id: over.id ?? 1,
    type: "MULTIPLE_CHOICE" as const,
    order_index: 0,
    instruction: "",
    prompt: "Hello",
    data: {},
  };
}

const MULTIPLE_CHOICE: NarrowedExercise = {
  type: "MULTIPLE_CHOICE",
  base: base(),
  options: [
    { id: "o1", text: "Hola" },
    { id: "o2", text: "Adiós" },
  ],
};

function verdict(over: Partial<SubmitAnswerResponse> = {}): SubmitAnswerResponse {
  return {
    correct: true,
    correct_answer: null,
    xp_earned: 10,
    hearts_remaining: 5,
    already_answered: false,
    answered_count: 1,
    total_exercises: 5,
    ...over,
  };
}

function renderExercise(exercise: NarrowedExercise, props = {}) {
  const onDraftChange = vi.fn();
  const onSubmit = vi.fn();
  // Match pairs is the only exercise that grades through the server mid-play;
  // the default is a stub the other four never call.
  const onSubmitPair = vi.fn();
  render(
    <ExerciseRenderer
      exercise={exercise}
      disabled={false}
      verdict={null}
      onDraftChange={onDraftChange}
      onSubmit={onSubmit}
      onSubmitPair={onSubmitPair}
      {...props}
    />,
  );
  return { onDraftChange, onSubmit, onSubmitPair };
}

// --------------------------------------------------------------------------
// Dispatch
// --------------------------------------------------------------------------

describe("dispatch", () => {
  test("multiple choice renders its options as radios", () => {
    renderExercise(MULTIPLE_CHOICE);

    const options = screen.getAllByRole("radio");
    expect(options).toHaveLength(2);
    expect(screen.getByText("Hola")).toBeDefined();
    expect(screen.getByText("Adiós")).toBeDefined();
  });

  test("translate renders the word bank", () => {
    renderExercise({
      type: "TRANSLATE",
      base: base(),
      tokens: ["buenos", "días", "hola"],
    });

    expect(screen.getByRole("button", { name: "buenos" })).toBeDefined();
    expect(screen.getByLabelText("Word bank")).toBeDefined();
  });

  test("match pairs renders both columns", () => {
    renderExercise({
      type: "MATCH_PAIRS",
      base: base(),
      left: [{ id: "l1", text: "hola" }],
      right: [{ id: "r1", text: "hello" }],
    });

    expect(screen.getByLabelText("Spanish words")).toBeDefined();
    expect(screen.getByLabelText("English meanings")).toBeDefined();
  });

  test("type answer renders a labelled text input", () => {
    renderExercise({ type: "TYPE_ANSWER", base: base(), language: "es" });

    expect(screen.getByLabelText("Your answer")).toBeDefined();
  });
});

// --------------------------------------------------------------------------
// Selection reports a draft, and never a verdict
// --------------------------------------------------------------------------

describe("answering", () => {
  test("choosing an option reports the option id upward", async () => {
    const { onDraftChange } = renderExercise(MULTIPLE_CHOICE);

    await userEvent.click(screen.getByRole("radio", { name: /Hola/ }));

    expect(onDraftChange).toHaveBeenCalledWith({ option_id: "o1" });
  });

  test("the selected option is marked for assistive technology", async () => {
    renderExercise(MULTIPLE_CHOICE);
    const option = screen.getByRole("radio", { name: /Hola/ });

    expect(option.getAttribute("aria-checked")).toBe("false");
    await userEvent.click(option);
    expect(option.getAttribute("aria-checked")).toBe("true");
  });

  test("typing reports the text, and clearing it reports nothing to submit", async () => {
    const { onDraftChange } = renderExercise({
      type: "TYPE_ANSWER",
      base: base(),
      language: "es",
    });

    const input = screen.getByLabelText("Your answer");
    await userEvent.type(input, "hola");
    expect(onDraftChange).toHaveBeenLastCalledWith({ text: "hola" });

    await userEvent.clear(input);
    // null is the UI-level "not ready" signal -- the only judgement the client
    // makes about an answer.
    expect(onDraftChange).toHaveBeenLastCalledWith(null);
  });

  test("whitespace alone is not a submittable answer", async () => {
    const { onDraftChange } = renderExercise({
      type: "TYPE_ANSWER",
      base: base(),
      language: "es",
    });

    await userEvent.type(screen.getByLabelText("Your answer"), "   ");

    expect(onDraftChange).toHaveBeenLastCalledWith(null);
  });

  test("Enter requests submission while the exercise is unanswered", async () => {
    const { onSubmit } = renderExercise({
      type: "TYPE_ANSWER",
      base: base(),
      language: "es",
    });

    await userEvent.type(screen.getByLabelText("Your answer"), "hola{Enter}");

    expect(onSubmit).toHaveBeenCalledTimes(1);
  });

  test("match pairs sends each selected pair to the server immediately", async () => {
    // Replaces the Phase 5–8 test that asserted a draft payload was reported
    // once every pair was formed. There is no draft any more: each pair is
    // graded as it is made, so what matters is *what gets sent*.
    const onSubmitPair = vi
      .fn()
      .mockResolvedValue(pairResult({ matched_pairs: [["l1", "r2"]] }));
    renderExercise(MATCH_PAIRS, { onSubmitPair });

    await userEvent.click(screen.getByRole("button", { name: "hola" }));
    await userEvent.click(screen.getByRole("button", { name: "hello" }));

    expect(onSubmitPair).toHaveBeenCalledWith("l1", "r2");
  });
});

// --------------------------------------------------------------------------
// Match pairs — incremental grading
// --------------------------------------------------------------------------

const MATCH_PAIRS: NarrowedExercise = {
  type: "MATCH_PAIRS",
  base: base(),
  left: [
    { id: "l1", text: "hola" },
    { id: "l2", text: "adiós" },
  ],
  right: [
    { id: "r1", text: "goodbye" },
    { id: "r2", text: "hello" },
  ],
};

function pairResult(over: Partial<SubmitPairResponse> = {}): SubmitPairResponse {
  return {
    correct: true,
    pair_completed: true,
    matched_pairs: [],
    exercise_complete: false,
    exercise_correct: false,
    hearts_remaining: 5,
    xp_earned: 0,
    already_answered: false,
    answered_count: 0,
    total_exercises: 5,
    ...over,
  };
}

describe("MatchPairsExercise", () => {
  test("a right item cannot be chosen before a left one", () => {
    renderExercise(MATCH_PAIRS);

    // Disabled rather than inert: a tap that silently does nothing is worse
    // than a control that says it is not available yet.
    expect((screen.getByRole("button", { name: "hello" }) as HTMLButtonElement).disabled).toBe(
      true,
    );
  });

  test("choosing a left item enables the right column", async () => {
    renderExercise(MATCH_PAIRS);

    await userEvent.click(screen.getByRole("button", { name: "hola" }));

    expect((screen.getByRole("button", { name: "hello" }) as HTMLButtonElement).disabled).toBe(
      false,
    );
  });

  test("nothing is submitted until both halves are chosen", async () => {
    const onSubmitPair = vi.fn().mockResolvedValue(pairResult());
    renderExercise(MATCH_PAIRS, { onSubmitPair });

    await userEvent.click(screen.getByRole("button", { name: "hola" }));

    expect(onSubmitPair).not.toHaveBeenCalled();
  });

  test("a correct pair locks both tiles", async () => {
    const onSubmitPair = vi
      .fn()
      .mockResolvedValue(pairResult({ matched_pairs: [["l1", "r2"]] }));
    renderExercise(MATCH_PAIRS, { onSubmitPair });

    await userEvent.click(screen.getByRole("button", { name: "hola" }));
    await userEvent.click(screen.getByRole("button", { name: "hello" }));

    // The accessible name changes too, so the lock is not conveyed by colour
    // alone.
    const left = screen.getByRole("button", { name: "hola, matched" }) as HTMLButtonElement;
    const right = screen.getByRole("button", { name: "hello, matched" }) as HTMLButtonElement;
    expect(left.disabled).toBe(true);
    expect(right.disabled).toBe(true);
  });

  test("a locked pair cannot be submitted again", async () => {
    const onSubmitPair = vi
      .fn()
      .mockResolvedValue(pairResult({ matched_pairs: [["l1", "r2"]] }));
    renderExercise(MATCH_PAIRS, { onSubmitPair });

    await userEvent.click(screen.getByRole("button", { name: "hola" }));
    await userEvent.click(screen.getByRole("button", { name: "hello" }));
    await userEvent.click(screen.getByRole("button", { name: "hola, matched" }));

    expect(onSubmitPair).toHaveBeenCalledTimes(1);
  });

  test("an incorrect pair releases the selection so the learner can retry", async () => {
    const onSubmitPair = vi
      .fn()
      .mockResolvedValue(
        pairResult({ correct: false, pair_completed: false, matched_pairs: [] }),
      );
    renderExercise(MATCH_PAIRS, { onSubmitPair });

    await userEvent.click(screen.getByRole("button", { name: "hola" }));
    await userEvent.click(screen.getByRole("button", { name: "goodbye" }));

    // Flagged as wrong, not locked — and still selectable.
    const left = screen.getByRole("button", {
      name: "hola, not a match",
    }) as HTMLButtonElement;
    expect(left.disabled).toBe(false);
  });

  test("after a wrong pair the next selection can still be made", async () => {
    const onSubmitPair = vi
      .fn()
      .mockResolvedValueOnce(pairResult({ correct: false, matched_pairs: [] }))
      .mockResolvedValueOnce(pairResult({ matched_pairs: [["l1", "r2"]] }));
    renderExercise(MATCH_PAIRS, { onSubmitPair });

    await userEvent.click(screen.getByRole("button", { name: "hola" }));
    await userEvent.click(screen.getByRole("button", { name: "goodbye" }));
    await userEvent.click(screen.getByRole("button", { name: "hola, not a match" }));
    await userEvent.click(screen.getByRole("button", { name: "hello" }));

    expect(onSubmitPair).toHaveBeenNthCalledWith(2, "l1", "r2");
  });

  test("the client follows the server's matched list, not its own", async () => {
    // A response a correct backend would not send: it confirms a pair the
    // learner did not just make. The UI must render what it was told.
    const onSubmitPair = vi
      .fn()
      .mockResolvedValue(pairResult({ matched_pairs: [["l2", "r1"]] }));
    renderExercise(MATCH_PAIRS, { onSubmitPair });

    await userEvent.click(screen.getByRole("button", { name: "hola" }));
    await userEvent.click(screen.getByRole("button", { name: "hello" }));

    expect(screen.getByRole("button", { name: "adiós, matched" })).toBeDefined();
    expect(screen.queryByRole("button", { name: "hola, matched" })).toBeNull();
  });

  test("progress is reported in words as well as colour", async () => {
    const onSubmitPair = vi
      .fn()
      .mockResolvedValue(pairResult({ matched_pairs: [["l1", "r2"]] }));
    renderExercise(MATCH_PAIRS, { onSubmitPair });

    expect(screen.getByText("0 of 2 matched")).toBeDefined();

    await userEvent.click(screen.getByRole("button", { name: "hola" }));
    await userEvent.click(screen.getByRole("button", { name: "hello" }));

    expect(screen.getByText("1 of 2 matched")).toBeDefined();
  });

  test("verdicts are announced to assistive technology", async () => {
    const onSubmitPair = vi
      .fn()
      .mockResolvedValue(pairResult({ matched_pairs: [["l1", "r2"]] }));
    renderExercise(MATCH_PAIRS, { onSubmitPair });

    await userEvent.click(screen.getByRole("button", { name: "hola" }));
    await userEvent.click(screen.getByRole("button", { name: "hello" }));

    const status = screen.getByRole("status");
    expect(status.getAttribute("aria-live")).toBe("polite");
    expect(status.textContent).toContain("matches");
  });

  test("a failed request gives the selection back and marks nothing wrong", async () => {
    const onSubmitPair = vi.fn().mockRejectedValue(new Error("network"));
    renderExercise(MATCH_PAIRS, { onSubmitPair });

    await userEvent.click(screen.getByRole("button", { name: "hola" }));
    await userEvent.click(screen.getByRole("button", { name: "hello" }));

    // No verdict arrived, so the tile is neither locked nor flagged as wrong.
    const left = screen.getByRole("button", { name: "hola" }) as HTMLButtonElement;
    expect(left.disabled).toBe(false);
    expect(screen.getByText("0 of 2 matched")).toBeDefined();
  });
});

// --------------------------------------------------------------------------
// Radio-group keyboard contract
// --------------------------------------------------------------------------

describe("multiple choice keyboard navigation", () => {
  test("the group is a single tab stop", async () => {
    renderExercise(MULTIPLE_CHOICE);

    const radios = screen.getAllByRole("radio");
    // Exactly one option is reachable by Tab; arrows move between them. Four
    // separate tab stops would make a long list tedious to pass through.
    const reachable = radios.filter((radio) => radio.tabIndex === 0);
    expect(reachable).toHaveLength(1);
    expect(reachable[0]).toBe(radios[0]);
  });

  test("an arrow key selects the next option", async () => {
    const { onDraftChange } = renderExercise(MULTIPLE_CHOICE);
    const radios = screen.getAllByRole("radio");

    radios[0].focus();
    await userEvent.keyboard("{ArrowDown}");

    // Selecting on arrow is what a radio group does — moving without selecting
    // would leave the checked state and the focus out of step.
    expect(onDraftChange).toHaveBeenLastCalledWith({ option_id: "o1" });
    expect(radios[0].getAttribute("aria-checked")).toBe("true");
  });

  test("arrow selection wraps around the group", async () => {
    const { onDraftChange } = renderExercise(MULTIPLE_CHOICE);
    const radios = screen.getAllByRole("radio");

    radios[0].focus();
    await userEvent.keyboard("{ArrowDown}{ArrowDown}{ArrowDown}");

    // o1 -> o2 -> back to o1.
    expect(onDraftChange).toHaveBeenLastCalledWith({ option_id: "o1" });
  });

  test("the tab stop follows the checked option", async () => {
    renderExercise(MULTIPLE_CHOICE);
    const radios = screen.getAllByRole("radio");

    await userEvent.click(radios[1]);

    expect(radios[1].tabIndex).toBe(0);
    expect(radios[0].tabIndex).toBe(-1);
  });

  test("a graded exercise ignores arrow keys", async () => {
    const { onDraftChange } = renderExercise(MULTIPLE_CHOICE, {
      disabled: true,
      verdict: verdict(),
    });
    const radios = screen.getAllByRole("radio");

    radios[0].focus();
    await userEvent.keyboard("{ArrowDown}");

    // The answer is already with the server; the learner must not be able to
    // change it.
    expect(onDraftChange).not.toHaveBeenCalled();
  });
});
