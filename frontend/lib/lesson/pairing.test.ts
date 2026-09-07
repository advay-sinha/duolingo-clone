/**
 * Tests for match-pairs interaction state.
 *
 * Rewritten in Phase 9 along with the module. The old suite tested a build-then-
 * check flow: forming, unlinking and re-forming pairs before a single submit.
 * That interaction no longer exists — pairs are graded the moment they are
 * formed — so testing it would have been testing a product decision that had
 * been reversed.
 *
 * The theme throughout: **the server owns what is matched.** Several tests feed
 * in a response that contradicts local state, to prove the module follows the
 * response rather than its own bookkeeping.
 */

import assert from "node:assert/strict";
import test from "node:test";

import {
  applyServerPairs,
  clearWrong,
  emptyPairState,
  isLocked,
  isSubmitting,
  isWrong,
  matchedLeft,
  matchedRight,
  ownerOf,
  pairIndex,
  releaseSubmission,
  tapLeft,
  tapRight,
  type PairState,
} from "./pairing.ts";

/** State with one confirmed pair, as the server would have reported it. */
function withOnePair(): PairState {
  return applyServerPairs(
    { ...emptyPairState, submitting: ["l1", "r2"] },
    { correct: true, matched_pairs: [["l1", "r2"]] },
  );
}

// --------------------------------------------------------------------------
// Selection
// --------------------------------------------------------------------------

test("tapping a left item makes it pending", () => {
  const state = tapLeft(emptyPairState, "l1");

  assert.equal(state.pending, "l1");
  assert.equal(state.submitting, null);
});

test("tapping the pending item again cancels the selection", () => {
  let state = tapLeft(emptyPairState, "l1");
  state = tapLeft(state, "l1");

  assert.equal(state.pending, null);
});

test("a right item cannot be chosen first", () => {
  // A pair needs the Spanish side to have a meaning attached to it, not the
  // other way round.
  const state = tapRight(emptyPairState, "r1");

  assert.equal(state.pending, null);
  assert.equal(state.submitting, null);
});

test("choosing a right item after a left one forms a pair to submit", () => {
  let state = tapLeft(emptyPairState, "l1");
  state = tapRight(state, "r3");

  assert.deepEqual(state.submitting, ["l1", "r3"]);
  assert.equal(state.pending, null);
  // Crucially, nothing is marked matched: only the server decides that.
  assert.deepEqual(state.matched, []);
});

test("taps are ignored while a pair is being graded", () => {
  let state = tapLeft(emptyPairState, "l1");
  state = tapRight(state, "r3");

  assert.equal(tapLeft(state, "l2"), state);
  assert.equal(tapRight(state, "r1"), state);
});

// --------------------------------------------------------------------------
// The server's verdict
// --------------------------------------------------------------------------

test("a correct verdict locks the pair the server reported", () => {
  const state = withOnePair();

  assert.deepEqual(state.matched, [["l1", "r2"]]);
  assert.equal(state.submitting, null);
  assert.equal(state.wrong, null);
  assert.ok(isLocked(state, "l1", "left"));
  assert.ok(isLocked(state, "r2", "right"));
});

test("an incorrect verdict locks nothing and flags the rejected pair", () => {
  const state = applyServerPairs(
    { ...emptyPairState, submitting: ["l1", "r1"] },
    { correct: false, matched_pairs: [] },
  );

  assert.deepEqual(state.matched, []);
  assert.deepEqual(state.wrong, ["l1", "r1"]);
  assert.equal(isLocked(state, "l1", "left"), false);
});

test("the matched set is replaced by the server's, not merged with it", () => {
  // A deliberately contradictory response: the client believes l1/r2 is
  // matched, the server says only l5/r5 is. The server wins.
  const state = applyServerPairs(withOnePair(), {
    correct: true,
    matched_pairs: [["l5", "r5"]],
  });

  assert.deepEqual(state.matched, [["l5", "r5"]]);
  assert.equal(isLocked(state, "l1", "left"), false);
});

test("a locked item ignores further taps", () => {
  const state = withOnePair();

  assert.equal(tapLeft(state, "l1"), state);
  assert.equal(tapRight(state, "r2"), state);
});

test("a failed request gives the selection back without a verdict", () => {
  let state = tapLeft(emptyPairState, "l1");
  state = tapRight(state, "r3");
  state = releaseSubmission(state);

  assert.equal(state.submitting, null);
  assert.equal(state.pending, null);
  // Nothing is marked wrong: no verdict arrived, so none is assumed.
  assert.equal(state.wrong, null);
  assert.deepEqual(state.matched, []);
});

test("the red flash clears on the next selection", () => {
  const rejected = applyServerPairs(
    { ...emptyPairState, submitting: ["l1", "r1"] },
    { correct: false, matched_pairs: [] },
  );

  assert.equal(tapLeft(rejected, "l2").wrong, null);
  assert.equal(clearWrong(rejected).wrong, null);
});

// --------------------------------------------------------------------------
// Derived views the component renders
// --------------------------------------------------------------------------

test("matched sets report both sides", () => {
  const state = applyServerPairs(emptyPairState, {
    correct: true,
    matched_pairs: [
      ["l1", "r2"],
      ["l3", "r1"],
    ],
  });

  assert.deepEqual([...matchedLeft(state)], ["l1", "l3"]);
  assert.deepEqual([...matchedRight(state)], ["r2", "r1"]);
});

test("pair numbers follow the order the server matched them in", () => {
  const state = applyServerPairs(emptyPairState, {
    correct: true,
    matched_pairs: [
      ["l3", "r1"],
      ["l1", "r2"],
    ],
  });

  assert.equal(pairIndex(state, "l3"), 1);
  assert.equal(pairIndex(state, "l1"), 2);
  assert.equal(pairIndex(state, "l2"), null);
});

test("ownerOf finds the left item a right item belongs to", () => {
  const state = withOnePair();

  assert.equal(ownerOf(state, "r2"), "l1");
  assert.equal(ownerOf(state, "r9"), undefined);
});

test("the in-flight pair is identifiable on both sides", () => {
  let state = tapLeft(emptyPairState, "l1");
  state = tapRight(state, "r3");

  assert.ok(isSubmitting(state, "l1", "left"));
  assert.ok(isSubmitting(state, "r3", "right"));
  assert.equal(isSubmitting(state, "l2", "left"), false);
});

test("the rejected pair is identifiable on both sides", () => {
  const state = applyServerPairs(
    { ...emptyPairState, submitting: ["l1", "r1"] },
    { correct: false, matched_pairs: [] },
  );

  assert.ok(isWrong(state, "l1", "left"));
  assert.ok(isWrong(state, "r1", "right"));
  assert.equal(isWrong(state, "r2", "right"), false);
});
