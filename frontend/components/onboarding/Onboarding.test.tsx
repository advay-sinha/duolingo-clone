/**
 * Component tests for the onboarding screens.
 *
 * What these assert is what a learner can actually do: which cards are
 * selectable, which are not and say why, what the keyboard does, and where each
 * choice leads. The API modules are mocked, so nothing here touches a network;
 * the router is mocked because navigation is how these screens report success.
 *
 * The load-bearing one is `a coming soon course cannot be selected`. It is the
 * second of two independent guarantees — the backend rejects any id that is not
 * in the courses table, and the UI never offers one — and only this half can be
 * checked from here.
 */

import { beforeEach, describe, expect, test, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import type {
  CourseSummary,
  OnboardingStatus,
  PlacementResult,
} from "@/lib/api/types";

const push = vi.fn();
const refresh = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push, refresh }),
}));

const selectCourse = vi.fn();
const selectProficiency = vi.fn();
const selectStartingMode = vi.fn();

vi.mock("@/lib/api/onboarding", () => ({
  selectCourse: (...args: unknown[]) => selectCourse(...args),
  selectProficiency: (...args: unknown[]) => selectProficiency(...args),
  selectStartingMode: (...args: unknown[]) => selectStartingMode(...args),
}));

const startPlacement = vi.fn();
const answerPlacement = vi.fn();
const completePlacement = vi.fn();

vi.mock("@/lib/api/placement", () => ({
  startPlacement: (...args: unknown[]) => startPlacement(...args),
  answerPlacement: (...args: unknown[]) => answerPlacement(...args),
  completePlacement: (...args: unknown[]) => completePlacement(...args),
}));

const { CoursePicker } = await import("./CoursePicker");
const { ProficiencyPicker } = await import("./ProficiencyPicker");
const { StartingPointPicker } = await import("./StartingPointPicker");
const { PlacementRunner } = await import("./PlacementRunner");
const { PlacementResultCard } = await import("./PlacementResultCard");
const { OnboardingLayout } = await import("./OnboardingLayout");

beforeEach(() => {
  push.mockClear();
  refresh.mockClear();
  selectCourse.mockReset();
  selectProficiency.mockReset();
  selectStartingMode.mockReset();
  startPlacement.mockReset();
  answerPlacement.mockReset();
  completePlacement.mockReset();
});

const SPANISH: CourseSummary = {
  id: 1,
  title: "Spanish",
  description: "",
  source_language: "English",
  target_language: "Spanish",
  flag_emoji: "🇪🇸",
};

function status(over: Partial<OnboardingStatus> = {}): OnboardingStatus {
  return {
    completed: false,
    step: "COURSE",
    course_id: null,
    proficiency: null,
    starting_mode: null,
    placement: null,
    grandfathered: false,
    completed_at: null,
    ...over,
  };
}

// --------------------------------------------------------------------------
// Course selection
// --------------------------------------------------------------------------

describe("CoursePicker", () => {
  test("the real course is selectable and continues to proficiency", async () => {
    selectCourse.mockResolvedValue(status({ step: "PROFICIENCY", course_id: 1 }));
    render(<CoursePicker courses={[SPANISH]} initial={null} />);

    await userEvent.click(screen.getByRole("button", { name: "Spanish, English to Spanish" }));
    await userEvent.click(screen.getByRole("button", { name: "Continue" }));

    expect(selectCourse).toHaveBeenCalledWith(1);
    expect(push).toHaveBeenCalledWith("/onboarding/proficiency");
    expect(refresh).toHaveBeenCalled();
  });

  test("a coming soon course cannot be selected", async () => {
    render(<CoursePicker courses={[SPANISH]} initial={null} />);

    const french = screen.getByRole("button", { name: "French, coming soon" });
    expect(french.hasAttribute("disabled")).toBe(true);

    await userEvent.click(french);
    expect(selectCourse).not.toHaveBeenCalled();
  });

  test("a coming soon course says so in its accessible name", () => {
    render(<CoursePicker courses={[SPANISH]} initial={null} />);

    // Not conveyed by colour alone: a screen reader hears the reason.
    expect(screen.getByRole("button", { name: "French, coming soon" })).toBeTruthy();
  });

  test("the selected course is obvious to assistive technology", async () => {
    render(<CoursePicker courses={[SPANISH]} initial={null} />);

    const spanish = screen.getByRole("button", { name: "Spanish, English to Spanish" });
    // A single real course is preselected — there is nothing to choose between.
    expect(spanish.getAttribute("aria-pressed")).toBe("true");
  });

  test("an existing choice is shown as selected after a refresh", () => {
    render(<CoursePicker courses={[SPANISH]} initial={1} />);

    expect(
      screen.getByRole("button", { name: "Spanish, English to Spanish" }).getAttribute("aria-pressed"),
    ).toBe("true");
  });

  test("a failed request keeps the learner on the screen with a message", async () => {
    selectCourse.mockRejectedValue(new Error("boom"));
    render(<CoursePicker courses={[SPANISH]} initial={1} />);

    await userEvent.click(screen.getByRole("button", { name: "Continue" }));

    expect(await screen.findByRole("alert")).toBeTruthy();
    expect(push).not.toHaveBeenCalled();
  });
});

// --------------------------------------------------------------------------
// Proficiency
// --------------------------------------------------------------------------

describe("ProficiencyPicker", () => {
  test("all five options are offered as one radio group", () => {
    render(<ProficiencyPicker initial={null} />);

    expect(
      screen.getByRole("radiogroup", { name: "How much Spanish do you know?" }),
    ).toBeTruthy();
    expect(screen.getAllByRole("radio")).toHaveLength(5);
  });

  test("the design's copy is used verbatim", () => {
    render(<ProficiencyPicker initial={null} />);

    for (const label of [
      "I'm new to Spanish",
      "I know some common words",
      "I can have basic conversations",
      "I can talk about various topics",
      "I can discuss most topics in detail",
    ]) {
      expect(screen.getByRole("radio", { name: label })).toBeTruthy();
    }
  });

  test("Continue is disabled until something is chosen", async () => {
    render(<ProficiencyPicker initial={null} />);

    const button = () =>
      screen.getByRole("button", { name: "Continue" }) as HTMLButtonElement;
    expect(button().disabled).toBe(true);

    await userEvent.click(
      screen.getByRole("radio", { name: "I know some common words" }),
    );
    expect(button().disabled).toBe(false);
  });

  test("the stored value is the enum, not the label", async () => {
    selectProficiency.mockResolvedValue(status({ step: "START" }));
    render(<ProficiencyPicker initial={null} />);

    await userEvent.click(
      screen.getByRole("radio", { name: "I can talk about various topics" }),
    );
    await userEvent.click(screen.getByRole("button", { name: "Continue" }));

    expect(selectProficiency).toHaveBeenCalledWith("VARIOUS_TOPICS");
    expect(push).toHaveBeenCalledWith("/onboarding/start");
  });

  test("the selected option is marked checked and the others are not", async () => {
    render(<ProficiencyPicker initial={null} />);

    const option = screen.getByRole("radio", { name: "I'm new to Spanish" });
    await userEvent.click(option);

    expect(option.getAttribute("aria-checked")).toBe("true");
    const checked = screen
      .getAllByRole("radio")
      .filter((node) => node.getAttribute("aria-checked") === "true");
    expect(checked).toHaveLength(1);
  });

  test("an existing choice survives a refresh", () => {
    render(<ProficiencyPicker initial="ADVANCED" />);

    expect(
      screen
        .getByRole("radio", { name: "I can discuss most topics in detail" })
        .getAttribute("aria-checked"),
    ).toBe("true");
  });

  test("arrow keys move and select, as a radio group must", async () => {
    render(<ProficiencyPicker initial="BEGINNER" />);

    const options = screen.getAllByRole("radio");
    options[0].focus();
    await userEvent.keyboard("{ArrowDown}");

    // Arrows move *and* select — that is the radio-group contract, not a
    // shortcut. Focus follows so the next arrow continues from here.
    expect(options[1].getAttribute("aria-checked")).toBe("true");
    expect(document.activeElement).toBe(options[1]);
  });

  test("from nothing selected, the first arrow picks the first option", async () => {
    render(<ProficiencyPicker initial={null} />);

    const options = screen.getAllByRole("radio");
    options[0].focus();
    await userEvent.keyboard("{ArrowDown}");

    expect(options[0].getAttribute("aria-checked")).toBe("true");
  });

  test("the group is one tab stop, not five", async () => {
    render(<ProficiencyPicker initial={null} />);

    const stops = screen
      .getAllByRole("radio")
      .filter((node) => node.getAttribute("tabindex") === "0");
    expect(stops).toHaveLength(1);
  });
});

// --------------------------------------------------------------------------
// Starting point
// --------------------------------------------------------------------------

describe("StartingPointPicker", () => {
  test("both starting points are offered with the design's copy", () => {
    render(<StartingPointPicker />);

    expect(
      screen.getByRole("button", {
        name: "Start from scratch. Take the easiest lesson of the Spanish course",
      }),
    ).toBeTruthy();
    expect(
      screen.getByRole("button", {
        name: "Find my level. Let Duo recommend where you should start learning",
      }),
    ).toBeTruthy();
  });

  test("start from scratch completes onboarding and goes to the path", async () => {
    selectStartingMode.mockResolvedValue(
      status({ completed: true, step: "DONE", starting_mode: "SCRATCH" }),
    );
    render(<StartingPointPicker />);

    await userEvent.click(screen.getByRole("button", { name: /Start from scratch/ }));

    expect(selectStartingMode).toHaveBeenCalledWith("SCRATCH");
    await waitFor(() => expect(push).toHaveBeenCalledWith("/learn"));
  });

  test("find my level leads to the placement test", async () => {
    selectStartingMode.mockResolvedValue(
      status({ step: "PLACEMENT", starting_mode: "PLACEMENT" }),
    );
    render(<StartingPointPicker />);

    await userEvent.click(screen.getByRole("button", { name: /Find my level/ }));

    expect(selectStartingMode).toHaveBeenCalledWith("PLACEMENT");
    await waitFor(() =>
      expect(push).toHaveBeenCalledWith("/onboarding/placement"),
    );
  });

  test("navigation follows what the server says, not the button pressed", async () => {
    // The server reports onboarding finished even though PLACEMENT was chosen.
    // The screen must believe the server.
    selectStartingMode.mockResolvedValue(status({ completed: true, step: "DONE" }));
    render(<StartingPointPicker />);

    await userEvent.click(screen.getByRole("button", { name: /Find my level/ }));

    await waitFor(() => expect(push).toHaveBeenCalledWith("/learn"));
  });
});

// --------------------------------------------------------------------------
// Placement
// --------------------------------------------------------------------------

const QUESTION = {
  exercise: {
    id: 7,
    type: "MULTIPLE_CHOICE" as const,
    order_index: 0,
    instruction: "Select the correct translation",
    prompt: "hola",
    data: {
      options: [
        { id: "o1", text: "hello" },
        { id: "o2", text: "goodbye" },
      ],
    },
  },
  difficulty: 3,
  number: 1,
};

describe("PlacementRunner", () => {
  test("it says it is a placement test and shows the progress", async () => {
    startPlacement.mockResolvedValue({
      test_id: 5,
      total_questions: 8,
      answered_count: 0,
      finished: false,
      question: QUESTION,
    });
    render(<PlacementRunner />);

    expect(await screen.findByText("Placement test")).toBeTruthy();
    expect(screen.getByText("Question 1 of 8")).toBeTruthy();
    expect(screen.getByText("Level 3/5")).toBeTruthy();
  });

  test("no XP or hearts appear anywhere on the screen", async () => {
    startPlacement.mockResolvedValue({
      test_id: 5,
      total_questions: 8,
      answered_count: 0,
      finished: false,
      question: QUESTION,
    });
    const { container } = render(<PlacementRunner />);
    await screen.findByText("Placement test");

    const text = container.textContent ?? "";
    expect(text).not.toMatch(/XP/i);
    expect(text).not.toMatch(/heart/i);
  });

  test("answering shows the verdict and then the next question", async () => {
    startPlacement.mockResolvedValue({
      test_id: 5,
      total_questions: 8,
      answered_count: 0,
      finished: false,
      question: QUESTION,
    });
    answerPlacement.mockResolvedValue({
      test_id: 5,
      correct: true,
      correct_answer: null,
      already_answered: false,
      total_questions: 8,
      answered_count: 1,
      finished: false,
      question: { ...QUESTION, difficulty: 4, number: 2 },
    });
    render(<PlacementRunner />);

    await userEvent.click(await screen.findByRole("radio", { name: "hello" }));
    await userEvent.click(screen.getByRole("button", { name: "Check" }));

    expect(await screen.findByText("Correct!")).toBeTruthy();
    expect(answerPlacement).toHaveBeenCalledWith({
      test_id: 5,
      exercise_id: 7,
      answer: { option_id: "o1" },
    });

    await userEvent.click(screen.getByRole("button", { name: "Continue" }));
    expect(await screen.findByText("Question 2 of 8")).toBeTruthy();
    // Difficulty came from the server; nothing was computed here.
    expect(screen.getByText("Level 4/5")).toBeTruthy();
  });

  test("a wrong answer shows the expected answer", async () => {
    startPlacement.mockResolvedValue({
      test_id: 5,
      total_questions: 8,
      answered_count: 0,
      finished: false,
      question: QUESTION,
    });
    answerPlacement.mockResolvedValue({
      test_id: 5,
      correct: false,
      correct_answer: "hello",
      already_answered: false,
      total_questions: 8,
      answered_count: 1,
      finished: false,
      question: { ...QUESTION, difficulty: 2, number: 2 },
    });
    render(<PlacementRunner />);

    await userEvent.click(await screen.findByRole("radio", { name: "goodbye" }));
    await userEvent.click(screen.getByRole("button", { name: "Check" }));

    expect(await screen.findByText("Not quite")).toBeTruthy();
    expect(screen.getByText("Answer: hello")).toBeTruthy();
  });

  test("Check is disabled until an answer is given", async () => {
    startPlacement.mockResolvedValue({
      test_id: 5,
      total_questions: 8,
      answered_count: 0,
      finished: false,
      question: QUESTION,
    });
    render(<PlacementRunner />);

    const check = () =>
      screen.getByRole("button", { name: "Check" }) as HTMLButtonElement;
    await screen.findByRole("button", { name: "Check" });
    expect(check().disabled).toBe(true);

    await userEvent.click(screen.getByRole("radio", { name: "hello" }));
    expect(check().disabled).toBe(false);
  });

  test("the last answer leads to scoring rather than another question", async () => {
    startPlacement.mockResolvedValue({
      test_id: 5,
      total_questions: 8,
      answered_count: 7,
      finished: false,
      question: { ...QUESTION, number: 8 },
    });
    answerPlacement.mockResolvedValue({
      test_id: 5,
      correct: true,
      correct_answer: null,
      already_answered: false,
      total_questions: 8,
      answered_count: 8,
      finished: true,
      question: null,
    });
    completePlacement.mockResolvedValue({
      test_id: 5,
      level: 3,
      score: 18,
      max_score: 24,
      total_questions: 8,
      correct_answers: 6,
      skill_id: 7,
      skill_title: "Numbers",
      unit_title: "Numbers and actions",
      skills_placed_out: 6,
      onboarding: status({ completed: true, step: "DONE" }),
    });
    render(<PlacementRunner />);

    await userEvent.click(await screen.findByRole("radio", { name: "hello" }));
    await userEvent.click(screen.getByRole("button", { name: "Check" }));
    await userEvent.click(
      await screen.findByRole("button", { name: "See my level" }),
    );

    expect(completePlacement).toHaveBeenCalledWith(5);
    expect(await screen.findByText("We found your starting point!")).toBeTruthy();
  });

  test("a test resumed after every question was answered can still be scored", async () => {
    startPlacement.mockResolvedValue({
      test_id: 5,
      total_questions: 8,
      answered_count: 8,
      finished: true,
      question: null,
    });
    render(<PlacementRunner />);

    expect(
      await screen.findByRole("button", { name: "See my level" }),
    ).toBeTruthy();
  });

  test("a failure to start explains itself instead of hanging", async () => {
    startPlacement.mockRejectedValue(new Error("nope"));
    render(<PlacementRunner />);

    expect(await screen.findByText("Something went wrong")).toBeTruthy();
  });
});

// --------------------------------------------------------------------------
// Result
// --------------------------------------------------------------------------

describe("PlacementResultCard", () => {
  const result: PlacementResult = {
    test_id: 5,
    level: 3,
    score: 18,
    max_score: 24,
    total_questions: 8,
    correct_answers: 6,
    skill_id: 7,
    skill_title: "Numbers",
    unit_title: "Numbers and actions",
    skills_placed_out: 6,
    onboarding: status({ completed: true, step: "DONE" }),
  };

  test("it names the skill the learner starts at", () => {
    render(<PlacementResultCard result={result} onContinue={() => {}} />);

    expect(screen.getByText("We found your starting point!")).toBeTruthy();
    expect(screen.getByText("Numbers")).toBeTruthy();
    expect(screen.getByText(/Numbers and actions/)).toBeTruthy();
  });

  test("it explains that skipped skills stay available", () => {
    render(<PlacementResultCard result={result} onContinue={() => {}} />);

    expect(screen.getByText(/6 earlier skills are marked as placed out/)).toBeTruthy();
  });

  test("a learner placed at the beginning is not told they skipped anything", () => {
    render(
      <PlacementResultCard
        result={{ ...result, level: 0, skills_placed_out: 0 }}
        onContinue={() => {}}
      />,
    );

    expect(screen.getByText(/start at the very beginning/)).toBeTruthy();
  });

  test("no reward is shown, because none was earned", () => {
    const { container } = render(
      <PlacementResultCard result={result} onContinue={() => {}} />,
    );

    const text = container.textContent ?? "";
    expect(text).not.toMatch(/XP/i);
    expect(text).not.toMatch(/crown/i);
    expect(text).not.toMatch(/streak/i);
  });

  test("the call to action leads into the app", async () => {
    const onContinue = vi.fn();
    render(<PlacementResultCard result={result} onContinue={onContinue} />);

    await userEvent.click(screen.getByRole("button", { name: "Start learning" }));
    expect(onContinue).toHaveBeenCalled();
  });
});

// --------------------------------------------------------------------------
// Layout
// --------------------------------------------------------------------------

describe("OnboardingLayout", () => {
  test("Duo's question is the page heading", () => {
    render(
      <OnboardingLayout progress={0.5} question="How much Spanish do you know?">
        <p>content</p>
      </OnboardingLayout>,
    );

    expect(
      screen.getByRole("heading", { name: "How much Spanish do you know?" }),
    ).toBeTruthy();
  });

  test("progress is announced as a percentage, not only drawn", () => {
    render(
      <OnboardingLayout progress={0.5} question="Anything">
        <p>content</p>
      </OnboardingLayout>,
    );

    expect(screen.getByText("Onboarding 50% complete")).toBeTruthy();
  });

  test("progress is clamped to a sane range", () => {
    render(
      <OnboardingLayout progress={2} question="Anything">
        <p>content</p>
      </OnboardingLayout>,
    );

    expect(screen.getByText("Onboarding 100% complete")).toBeTruthy();
  });
});
