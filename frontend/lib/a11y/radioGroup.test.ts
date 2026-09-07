/**
 * Tests for the radio-group keyboard contract.
 *
 * Written against the WAI-ARIA pattern rather than against the components, so
 * they document what the role *promises* — which is the thing Phase 8's audit
 * found unimplemented.
 */

import assert from "node:assert/strict";
import test from "node:test";

import { radioGroupAction, radioTabIndex } from "./radioGroup.ts";

test("arrow keys move forward and backward", () => {
  assert.deepEqual(radioGroupAction("ArrowDown", 0, 4), { type: "move", index: 1 });
  assert.deepEqual(radioGroupAction("ArrowRight", 0, 4), { type: "move", index: 1 });
  assert.deepEqual(radioGroupAction("ArrowUp", 2, 4), { type: "move", index: 1 });
  assert.deepEqual(radioGroupAction("ArrowLeft", 2, 4), { type: "move", index: 1 });
});

test("movement wraps at both ends", () => {
  assert.deepEqual(radioGroupAction("ArrowDown", 3, 4), { type: "move", index: 0 });
  assert.deepEqual(radioGroupAction("ArrowUp", 0, 4), { type: "move", index: 3 });
});

test("with nothing selected, forward lands on the first option", () => {
  assert.deepEqual(radioGroupAction("ArrowDown", -1, 4), { type: "move", index: 0 });
});

test("with nothing selected, backward lands on the last option", () => {
  assert.deepEqual(radioGroupAction("ArrowUp", -1, 4), { type: "move", index: 3 });
});

test("Home and End jump to the ends", () => {
  assert.deepEqual(radioGroupAction("Home", 2, 4), { type: "move", index: 0 });
  assert.deepEqual(radioGroupAction("End", 0, 4), { type: "move", index: 3 });
});

test("Space selects the focused option", () => {
  assert.deepEqual(radioGroupAction(" ", 1, 4), { type: "select" });
});

test("keys the group does not own are left alone", () => {
  // Returning null is what stops the component calling preventDefault and
  // breaking Tab, Enter and browser shortcuts.
  for (const key of ["Tab", "Enter", "a", "Escape", "PageDown"]) {
    assert.equal(radioGroupAction(key, 0, 4), null, key);
  }
});

test("an empty group handles nothing", () => {
  assert.equal(radioGroupAction("ArrowDown", -1, 0), null);
});

test("a single option wraps to itself", () => {
  assert.deepEqual(radioGroupAction("ArrowDown", 0, 1), { type: "move", index: 0 });
  assert.deepEqual(radioGroupAction("ArrowUp", 0, 1), { type: "move", index: 0 });
});

test("the group is one tab stop, held by the checked option", () => {
  assert.equal(radioTabIndex(0, 2), -1);
  assert.equal(radioTabIndex(2, 2), 0);
  assert.equal(radioTabIndex(3, 2), -1);
});

test("with nothing checked the first option holds the tab stop", () => {
  assert.equal(radioTabIndex(0, -1), 0);
  assert.equal(radioTabIndex(1, -1), -1);
});
