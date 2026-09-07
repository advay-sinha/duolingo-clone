/**
 * Match-pairs interaction state, as pure functions.
 *
 * **Phase 9 rewrote this module.** Until Phase 8 the learner built a whole
 * mapping and pressed Check: pairs could be formed, unlinked and re-formed, and
 * this file owned all of that. Grading is now immediate — a left tap, a right
 * tap, and the server answers — so the rules changed shape entirely:
 *
 * * a matched pair is **locked**, because the server has accepted it and there
 *   is nothing left to reconsider;
 * * a wrong pair is **released**, so the learner tries again rather than being
 *   stuck with a mistake on screen;
 * * the truth about what is matched lives on the **server**, and
 *   `applyServerPairs` replaces the local set with what the response said rather
 *   than merging into it.
 *
 * What has not changed is the boundary: **nothing here decides correctness.**
 * This module decides what a tap means and which tiles are locked. Whether a
 * pair is right is the server's call, every time.
 */

/** A pair the server has confirmed, as it comes back in the response. */
export type MatchedPair = [string, string];

export interface PairState {
  /** Pairs the server has accepted. Locked, in the order they were matched. */
  matched: MatchedPair[];
  /** A left item awaiting its right-hand partner, if any. */
  pending: string | null;
  /**
   * The pair being graded right now, if a request is in flight. Used to show a
   * brief "checking" state and to block a second submission.
   */
  submitting: MatchedPair | null;
  /**
   * The pair the server just rejected, held only long enough to flash red. It
   * is not progress and is never locked.
   */
  wrong: MatchedPair | null;
}

export const emptyPairState: PairState = {
  matched: [],
  pending: null,
  submitting: null,
  wrong: null,
};

/** Every left id the server has accepted. */
export function matchedLeft(state: PairState): Set<string> {
  return new Set(state.matched.map(([left]) => left));
}

/** Every right id the server has accepted. */
export function matchedRight(state: PairState): Set<string> {
  return new Set(state.matched.map(([, right]) => right));
}

/** Whether a tile is locked — matched, and therefore out of play. */
export function isLocked(state: PairState, id: string, side: "left" | "right") {
  return side === "left"
    ? matchedLeft(state).has(id)
    : matchedRight(state).has(id);
}

/**
 * Apply a tap on a left item.
 *
 * A locked item ignores taps: it is already answered, and un-matching it would
 * mean asking the server to forget something it has recorded. Tapping the
 * pending item again cancels the selection.
 */
export function tapLeft(state: PairState, id: string): PairState {
  if (state.submitting) return state;
  if (isLocked(state, id, "left")) return state;
  return {
    ...state,
    pending: state.pending === id ? null : id,
    wrong: null,
  };
}

/**
 * Apply a tap on a right item.
 *
 * Returns the state unchanged when there is nothing to pair it with — a right
 * item cannot be chosen first, because a pair needs the Spanish side to have a
 * meaning attached to it.
 *
 * When it *does* form a pair, the pair goes into `submitting`: the component
 * reads that and sends it to the server. Nothing is marked correct here.
 */
export function tapRight(state: PairState, id: string): PairState {
  if (state.submitting) return state;
  if (isLocked(state, id, "right")) return state;
  if (!state.pending) return state;

  return {
    ...state,
    submitting: [state.pending, id],
    pending: null,
    wrong: null,
  };
}

/**
 * Record the server's verdict on the pair that was in flight.
 *
 * `matched` is taken wholesale from the response rather than appended to
 * locally. The server's list is the truth, and copying it means a dropped
 * response cannot leave the two disagreeing about what has been matched.
 */
export function applyServerPairs(
  state: PairState,
  result: { correct: boolean; matched_pairs: MatchedPair[] },
): PairState {
  return {
    matched: result.matched_pairs,
    pending: null,
    submitting: null,
    // The rejected pair is remembered only for the flash of red, and only when
    // it was actually wrong.
    wrong: result.correct ? null : state.submitting,
  };
}

/**
 * Release the in-flight pair after a request that failed to complete.
 *
 * A network error is not a verdict: nothing is marked wrong, no heart is
 * assumed lost, and the learner simply gets their selection back.
 */
export function releaseSubmission(state: PairState): PairState {
  return { ...state, submitting: null, pending: null, wrong: null };
}

/** Clear the red flash once the learner moves on. */
export function clearWrong(state: PairState): PairState {
  return state.wrong === null ? state : { ...state, wrong: null };
}

/** Ordinal of a matched pair (1-based), for the badge that visualises the link. */
export function pairIndex(state: PairState, leftId: string): number | null {
  const position = state.matched.findIndex(([left]) => left === leftId);
  return position === -1 ? null : position + 1;
}

/** The left item matched to a right item, if any. */
export function ownerOf(state: PairState, rightId: string): string | undefined {
  return state.matched.find(([, right]) => right === rightId)?.[0];
}

/** Whether a tile is part of the pair currently being graded. */
export function isSubmitting(
  state: PairState,
  id: string,
  side: "left" | "right",
): boolean {
  if (!state.submitting) return false;
  return side === "left" ? state.submitting[0] === id : state.submitting[1] === id;
}

/** Whether a tile is part of the pair the server just rejected. */
export function isWrong(
  state: PairState,
  id: string,
  side: "left" | "right",
): boolean {
  if (!state.wrong) return false;
  return side === "left" ? state.wrong[0] === id : state.wrong[1] === id;
}
