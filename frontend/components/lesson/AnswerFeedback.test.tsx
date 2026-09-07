/**
 * Component tests for the two screens that report the server's verdict.
 *
 * Everything asserted here is a value the backend sent. These tests exist partly
 * to prove the UI does not embellish: a practice replay that earned nothing must
 * say so, not show an invented number.
 */

import { describe, expect, test, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import type { CompleteLessonResponse, SubmitAnswerResponse } from "@/lib/api/types";

import { AnswerFeedback } from "./AnswerFeedback";
import { LessonComplete } from "./LessonComplete";

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

function completion(
  over: Partial<CompleteLessonResponse> = {},
): CompleteLessonResponse {
  return {
    attempt_id: 1,
    lesson_id: 1,
    correct_answers: 4,
    incorrect_answers: 1,
    total_exercises: 5,
    accuracy: 0.8,
    xp_earned: 50,
    first_completion: true,
    total_xp: 50,
    daily_xp: 50,
    daily_goal: 30,
    hearts_remaining: 4,
    current_streak: 1,
    longest_streak: 1,
    streak_extended: true,
    skill_id: 1,
    lessons_completed: 1,
    total_lessons: 2,
    crowns: 0,
    crown_earned: false,
    achievements_unlocked: [],
    ...over,
  };
}

describe("AnswerFeedback", () => {
  test("a correct answer is announced positively with its XP", () => {
    render(
      <AnswerFeedback verdict={verdict()} isLast={false} busy={false} onContinue={vi.fn()} />,
    );

    expect(screen.getByText("Nicely done!")).toBeDefined();
    expect(screen.getByText("+10 XP")).toBeDefined();
  });

  test("a wrong answer shows the expected answer the server returned", () => {
    render(
      <AnswerFeedback
        verdict={verdict({ correct: false, correct_answer: "buenos días", xp_earned: 0 })}
        isLast={false}
        busy={false}
        onContinue={vi.fn()}
      />,
    );

    expect(screen.getByText("Not quite")).toBeDefined();
    expect(screen.getByText("buenos días")).toBeDefined();
  });

  test("no XP chip appears when nothing was earned", () => {
    render(
      <AnswerFeedback
        verdict={verdict({ correct: false, xp_earned: 0 })}
        isLast={false}
        busy={false}
        onContinue={vi.fn()}
      />,
    );

    expect(screen.queryByText(/\+0 XP/)).toBeNull();
  });

  test("the verdict is announced to assistive technology when it appears", () => {
    render(
      <AnswerFeedback verdict={verdict()} isLast={false} busy={false} onContinue={vi.fn()} />,
    );

    const status = screen.getByRole("status");
    expect(status.getAttribute("aria-live")).toBe("polite");
  });

  test("the last exercise offers Finish rather than Continue", () => {
    render(
      <AnswerFeedback verdict={verdict()} isLast={true} busy={false} onContinue={vi.fn()} />,
    );

    expect(screen.getByRole("button", { name: "Finish" })).toBeDefined();
  });

  test("continuing is disabled while completion is in flight", async () => {
    const onContinue = vi.fn();
    render(
      <AnswerFeedback verdict={verdict()} isLast={true} busy={true} onContinue={onContinue} />,
    );

    const button = screen.getByRole("button", { name: "Saving…" }) as HTMLButtonElement;
    expect(button.disabled).toBe(true);

    await userEvent.click(button);
    expect(onContinue).not.toHaveBeenCalled();
  });

  test("a replayed answer is labelled as already answered", () => {
    render(
      <AnswerFeedback
        verdict={verdict({ already_answered: true })}
        isLast={false}
        busy={false}
        onContinue={vi.fn()}
      />,
    );

    expect(screen.getByText("Already answered")).toBeDefined();
  });
});

describe("LessonComplete", () => {
  test("shows the rewards the server reported", () => {
    render(<LessonComplete result={completion()} onDone={vi.fn()} />);

    expect(screen.getByText("Lesson complete!")).toBeDefined();
    expect(screen.getByText("+50")).toBeDefined();
    expect(screen.getByText("80%")).toBeDefined();
  });

  test("a practice replay is reported honestly as earning nothing", () => {
    render(
      <LessonComplete
        result={completion({ first_completion: false, xp_earned: 0 })}
        onDone={vi.fn()}
      />,
    );

    expect(screen.getByText("+0")).toBeDefined();
    expect(screen.getByText(/no extra XP this time/)).toBeDefined();
  });

  test("a crown is mentioned only when the server awarded one", () => {
    const { unmount } = render(
      <LessonComplete result={completion()} onDone={vi.fn()} />,
    );
    expect(screen.queryByText(/Crown earned/)).toBeNull();
    unmount();

    render(
      <LessonComplete
        result={completion({ crown_earned: true, crowns: 1, lessons_completed: 2 })}
        onDone={vi.fn()}
      />,
    );
    expect(screen.getByText(/Crown earned/)).toBeDefined();
  });

  test("continuing returns the learner to the path", async () => {
    const onDone = vi.fn();
    render(<LessonComplete result={completion()} onDone={onDone} />);

    await userEvent.click(screen.getByRole("button", { name: "Continue" }));

    expect(onDone).toHaveBeenCalledTimes(1);
  });
});
