/**
 * Tests for navigation configuration.
 *
 * Small, but it protects two real properties: that the desktop and mobile bars
 * cannot drift apart (they render from the same list), and that active-state
 * matching handles nested routes.
 */

import assert from "node:assert/strict";
import test from "node:test";

import { activeKey, NAV_DESTINATIONS } from "./navigation.ts";

test("the built destinations are Learn, Leaderboard and Profile", () => {
  // Pins which screens actually exist. Enabling a destination before its page
  // is built would fail here — as this did when Phase 7 shipped two of them.
  const available = NAV_DESTINATIONS.filter((item) => item.available);
  assert.deepEqual(
    available.map((item) => item.key),
    ["learn", "leaderboard", "profile"],
  );
});

test("Shop remains an unbuilt placeholder", () => {
  const shop = NAV_DESTINATIONS.find((item) => item.key === "shop");
  assert.equal(shop?.available, false);
});

test("unbuilt destinations are still listed, so the product shape is visible", () => {
  assert.ok(NAV_DESTINATIONS.length > 1);
  assert.ok(NAV_DESTINATIONS.every((item) => item.href.startsWith("/")));
});

test("every built destination marks its own route active", () => {
  for (const item of NAV_DESTINATIONS.filter((d) => d.available)) {
    assert.equal(activeKey(item.href), item.key, item.href);
  }
});

test("every destination has a unique key and href", () => {
  assert.equal(new Set(NAV_DESTINATIONS.map((i) => i.key)).size, NAV_DESTINATIONS.length);
  assert.equal(new Set(NAV_DESTINATIONS.map((i) => i.href)).size, NAV_DESTINATIONS.length);
});

test("/learn marks Learn active", () => {
  assert.equal(activeKey("/learn"), "learn");
});

test("a nested lesson route still marks Learn active", () => {
  assert.equal(activeKey("/learn/lesson/3"), "learn");
});

test("an unrelated route marks nothing active", () => {
  assert.equal(activeKey("/"), null);
  assert.equal(activeKey("/something-else"), null);
});

test("a prefix that is not a path segment does not match", () => {
  // "/learning" must not light up "Learn".
  assert.equal(activeKey("/learning"), null);
});
