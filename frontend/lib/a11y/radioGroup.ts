/**
 * Keyboard behaviour for a radio group, as a pure function.
 *
 * **Why this exists.** The multiple-choice and fill-blank exercises declare
 * `role="radiogroup"` with `role="radio"` children. That is the right semantics
 * — the learner picks exactly one — but a role is a promise about behaviour, and
 * Phase 8's accessibility audit found the promise unkept: arrow keys did
 * nothing, and every option was a separate tab stop. A screen-reader user hears
 * "radio button, 1 of 4" and presses Down; nothing happening is worse than
 * never having claimed the role at all.
 *
 * The alternative was to drop to `aria-pressed` toggle buttons, which are
 * honest but say nothing about "choose one". Implementing the contract is a few
 * lines, so the contract is implemented.
 *
 * The rules follow the WAI-ARIA radio group pattern: arrows move *and* select,
 * wrapping at both ends; Home and End jump to the ends; Space selects the
 * focused option.
 *
 * Keeping it a pure function (key + position in, intent out) means the whole
 * keyboard contract is testable with `node --test` and no DOM — the components
 * are left with only focus management, which is the part that genuinely needs a
 * browser.
 */

/** What a key press should do to a radio group. */
export type RadioGroupAction =
  | { type: "move"; index: number }
  | { type: "select" }
  | null;

/**
 * Decide what a key press means inside a radio group.
 *
 * @param key - `KeyboardEvent.key`.
 * @param current - Index of the checked option, or `-1` when none is checked.
 * @param count - Number of options.
 * @returns The action to perform, or `null` if the key is not ours to handle —
 *   in which case the caller must not call `preventDefault`, or it would break
 *   Tab, Enter and every browser shortcut.
 */
export function radioGroupAction(
  key: string,
  current: number,
  count: number,
): RadioGroupAction {
  if (count <= 0) return null;

  switch (key) {
    // Down/Right and Up/Left are both listed because a radio group is a single
    // logical sequence regardless of whether it is laid out as a column or a
    // row — and this one is a responsive grid that is both.
    case "ArrowDown":
    case "ArrowRight":
      // From "nothing checked", forward means the first option, not the second.
      return { type: "move", index: current < 0 ? 0 : (current + 1) % count };
    case "ArrowUp":
    case "ArrowLeft":
      return {
        type: "move",
        index: current < 0 ? count - 1 : (current - 1 + count) % count,
      };
    case "Home":
      return { type: "move", index: 0 };
    case "End":
      return { type: "move", index: count - 1 };
    case " ":
    case "Spacebar":
      return { type: "select" };
    default:
      return null;
  }
}

/**
 * The `tabIndex` for one option, implementing a roving tab stop.
 *
 * A radio group is **one** stop in the tab order, not one per option: Tab moves
 * past the whole group and arrows move within it. Before anything is checked,
 * the first option holds the stop so the group is reachable at all.
 */
export function radioTabIndex(index: number, current: number): 0 | -1 {
  if (current < 0) return index === 0 ? 0 : -1;
  return index === current ? 0 : -1;
}
