/**
 * Tests for the course and user API bindings.
 *
 * These assert the *contract between the binding and the client* — which path
 * each function requests — not the backend's behaviour, which the Python API
 * tests already cover. A wrong URL here is the kind of bug that only shows up
 * as a 404 at runtime.
 */

import assert from "node:assert/strict";
import test from "node:test";

import { getCourses, getCoursePath } from "./courses.ts";
import { getCurrentUser, getCurrentUserStats } from "./users.ts";

/** Capture the URL a binding requests, returning `body` as the response. */
async function capture(
  call: () => Promise<unknown>,
  body: unknown = {},
): Promise<string> {
  const original = globalThis.fetch;
  let url = "";
  globalThis.fetch = async (input) => {
    url = String(input);
    return new Response(JSON.stringify(body), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  };
  try {
    await call();
  } finally {
    globalThis.fetch = original;
  }
  return url;
}

test("getCourses requests /courses", async () => {
  const url = await capture(getCourses, { courses: [] });
  assert.ok(url.endsWith("/courses"), url);
});

test("getCoursePath interpolates the course id", async () => {
  const url = await capture(() => getCoursePath(7), { units: [] });
  assert.ok(url.endsWith("/courses/7/path"), url);
});

test("getCurrentUser requests /users/me", async () => {
  const url = await capture(getCurrentUser);
  assert.ok(url.endsWith("/users/me"), url);
});

test("getCurrentUserStats requests /users/me/stats", async () => {
  const url = await capture(getCurrentUserStats);
  assert.ok(url.endsWith("/users/me/stats"), url);
});

test("a typed path response is returned unchanged", async () => {
  const original = globalThis.fetch;
  globalThis.fetch = async () =>
    new Response(
      JSON.stringify({
        course_id: 1,
        course_title: "Spanish",
        source_language: "English",
        target_language: "Spanish",
        units: [{ id: 1, skills: [{ id: 1, state: "AVAILABLE" }] }],
      }),
      { status: 200, headers: { "Content-Type": "application/json" } },
    );
  try {
    const path = await getCoursePath(1);
    assert.equal(path.course_title, "Spanish");
    assert.equal(path.units[0].skills[0].state, "AVAILABLE");
  } finally {
    globalThis.fetch = original;
  }
});
