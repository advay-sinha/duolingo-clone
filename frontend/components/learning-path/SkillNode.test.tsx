/**
 * Component tests for the path, leaderboard and achievement UI.
 *
 * The theme throughout: **the client renders what the server decided.** Several
 * tests feed in data a correct backend would never send, to prove the UI follows
 * the response rather than re-deriving state from progress numbers.
 */

import { describe, expect, test, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import type {
  AchievementItem,
  LeaderboardEntry,
  SkillNode as SkillNodeData,
} from "@/lib/api/types";

import { AchievementCard } from "../profile/AchievementCard";
import { LeaderboardRow } from "../leaderboard/LeaderboardRow";
import { SkillNode } from "./SkillNode";

function skill(over: Partial<SkillNodeData> = {}): SkillNodeData {
  return {
    id: 1,
    title: "Greetings",
    description: "Hello and goodbye",
    order_index: 0,
    icon: "waving_hand",
    state: "AVAILABLE",
    crowns: 0,
    placed_out: false,
    lessons_completed: 0,
    total_lessons: 2,
    xp_earned: 0,
    lessons: [
      { id: 1, title: "One", order_index: 0, xp_reward: 10, completed: false },
      { id: 2, title: "Two", order_index: 1, xp_reward: 10, completed: false },
    ],
    ...over,
  };
}

// --------------------------------------------------------------------------
// Skill nodes
// --------------------------------------------------------------------------

describe("SkillNode", () => {
  test("an available skill can be activated", async () => {
    const onSelect = vi.fn();
    render(<SkillNode skill={skill()} offset={0} onSelect={onSelect} />);

    await userEvent.click(screen.getByRole("button"));

    expect(onSelect).toHaveBeenCalledTimes(1);
  });

  test("a locked skill is a disabled control and cannot be activated", async () => {
    const onSelect = vi.fn();
    render(
      <SkillNode skill={skill({ state: "LOCKED" })} offset={0} onSelect={onSelect} />,
    );

    const button = screen.getByRole("button") as HTMLButtonElement;
    expect(button.disabled).toBe(true);
    expect(button.getAttribute("aria-disabled")).toBe("true");

    await userEvent.click(button);
    expect(onSelect).not.toHaveBeenCalled();
  });

  test("state is announced in words, not only in colour", () => {
    const { unmount } = render(
      <SkillNode skill={skill({ state: "LOCKED" })} offset={0} onSelect={vi.fn()} />,
    );
    expect(screen.getByRole("button").textContent).toContain("Locked");
    unmount();

    render(
      <SkillNode
        skill={skill({ state: "COMPLETED", crowns: 1, lessons_completed: 2 })}
        offset={0}
        onSelect={vi.fn()}
      />,
    );
    expect(screen.getByRole("button").textContent).toContain("Completed");
  });

  test("an in-progress skill announces how far along it is", () => {
    render(
      <SkillNode skill={skill({ lessons_completed: 1 })} offset={0} onSelect={vi.fn()} />,
    );

    expect(screen.getByRole("button").textContent).toContain(
      "1 of 2 lessons complete",
    );
  });

  test("the server's state wins over contradictory progress numbers", async () => {
    // A backend would not send this; the point is that the UI does not
    // second-guess `state` by looking at crowns or counts.
    const onSelect = vi.fn();
    render(
      <SkillNode
        skill={skill({ state: "LOCKED", crowns: 1, lessons_completed: 2 })}
        offset={0}
        onSelect={onSelect}
      />,
    );

    const button = screen.getByRole("button") as HTMLButtonElement;
    expect(button.disabled).toBe(true);
    await userEvent.click(button);
    expect(onSelect).not.toHaveBeenCalled();
  });
});

// --------------------------------------------------------------------------
// Leaderboard
// --------------------------------------------------------------------------

function entry(over: Partial<LeaderboardEntry> = {}): LeaderboardEntry {
  return {
    rank: 1,
    user_id: 1,
    display_name: "Alex Mercer",
    avatar_url: "",
    xp: 120,
    current_streak: 3,
    is_current_user: false,
    ...over,
  };
}

describe("LeaderboardRow", () => {
  test("shows rank, name and XP", () => {
    render(<LeaderboardRow entry={entry()} />);

    expect(screen.getByText("Alex Mercer")).toBeDefined();
    expect(screen.getByText("120 XP")).toBeDefined();
  });

  test("the current learner is labelled, not just tinted", () => {
    render(<LeaderboardRow entry={entry({ is_current_user: true })} />);

    // A word, so the highlight survives for colour-blind and screen-reader users.
    expect(screen.getByText("You")).toBeDefined();
  });

  test("another learner's row carries no 'You' label", () => {
    render(<LeaderboardRow entry={entry({ display_name: "Ana", user_id: 2 })} />);

    expect(screen.queryByText("You")).toBeNull();
  });

  test("the highlight follows the server's flag, not the rank", () => {
    render(<LeaderboardRow entry={entry({ rank: 7, is_current_user: true })} />);

    expect(screen.getByText("You")).toBeDefined();
  });
});

// --------------------------------------------------------------------------
// Achievements
// --------------------------------------------------------------------------

function achievement(over: Partial<AchievementItem> = {}): AchievementItem {
  return {
    id: 1,
    key: "FIRST_LESSON",
    title: "First steps",
    description: "Complete your first lesson",
    icon: "star",
    color_key: "green",
    unlocked: false,
    unlocked_at: null,
    ...over,
  };
}

describe("AchievementCard", () => {
  test("a locked achievement says so and still describes the goal", () => {
    render(<AchievementCard item={achievement()} />);

    expect(screen.getByText("Locked")).toBeDefined();
    // Knowing what there is to earn is the point of showing locked ones.
    expect(screen.getByText("Complete your first lesson")).toBeDefined();
  });

  test("an unlocked achievement says so and shows when it was earned", () => {
    render(
      <AchievementCard
        item={achievement({ unlocked: true, unlocked_at: "2026-03-15T10:00:00Z" })}
      />,
    );

    expect(screen.getByText("Unlocked")).toBeDefined();
    expect(screen.getByText(/Earned/)).toBeDefined();
  });

  test("locked state is communicated in text, not colour alone", () => {
    const { container } = render(<AchievementCard item={achievement()} />);

    // The word is present regardless of any styling.
    expect(container.textContent).toContain("Locked");
  });
});
