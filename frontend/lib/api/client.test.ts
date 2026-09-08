/**
 * Tests for the API client.
 *
 * Runs on Node's built-in test runner (`node --test`), which strips TypeScript
 * types natively on Node 22.6+. That keeps Phase 1 free of Jest/Vitest and
 * their configuration — a real test framework can be added later if the
 * frontend grows logic that needs one.
 */

import assert from "node:assert/strict";
import test from "node:test";

import { ApiError, apiBaseUrl, request } from "./client.ts";

/** Replace global fetch for one test and restore it afterwards. */
async function withFetch(
  stub: typeof globalThis.fetch,
  body: () => Promise<void>,
): Promise<void> {
  const original = globalThis.fetch;
  globalThis.fetch = stub;
  try {
    await body();
  } finally {
    globalThis.fetch = original;
  }
}

test("returns the parsed JSON body on success", async () => {
  await withFetch(
    async () =>
      new Response(JSON.stringify({ status: "ok" }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    async () => {
      const result = await request<{ status: string }>("/health");
      assert.deepEqual(result, { status: "ok" });
    },
  );
});

test("calls the configured base URL and path", async () => {
  let calledWith = "";

  await withFetch(
    async (input) => {
      calledWith = String(input);
      return new Response("{}", { status: 200 });
    },
    async () => {
      await request("/health");
      assert.ok(
        calledWith.endsWith("/health"),
        `expected the request URL to end with /health, got ${calledWith}`,
      );
    },
  );
});

test("throws ApiError carrying the status when the response is not ok", async () => {
  await withFetch(
    async () => new Response("nope", { status: 500 }),
    async () => {
      await assert.rejects(
        () => request("/health"),
        (error: unknown) => {
          assert.ok(error instanceof ApiError);
          assert.equal(error.status, 500);
          return true;
        },
      );
    },
  );
});

test("throws ApiError with status 0 when the backend is unreachable", async () => {
  await withFetch(
    async () => {
      throw new TypeError("fetch failed");
    },
    async () => {
      await assert.rejects(
        () => request("/health"),
        (error: unknown) => {
          assert.ok(error instanceof ApiError);
          assert.equal(error.status, 0);
          assert.match(error.message, /Is the backend running\?/);
          return true;
        },
      );
    },
  );
});

test("uses the backend's own message when the error envelope is present", async () => {
  await withFetch(
    async () =>
      new Response(
        JSON.stringify({
          error: { code: "conflict", message: "No hearts remaining." },
        }),
        { status: 409, headers: { "Content-Type": "application/json" } },
      ),
    async () => {
      await assert.rejects(
        () => request("/lessons/1/start"),
        (error: unknown) => {
          assert.ok(error instanceof ApiError);
          // The learner sees the domain sentence, not a URL and a number.
          assert.equal(error.message, "No hearts remaining.");
          assert.equal(error.code, "conflict");
          assert.equal(error.status, 409);
          return true;
        },
      );
    },
  );
});

test("falls back to readable copy when the body is not an envelope", async () => {
  await withFetch(
    async () => new Response("<html>gateway error</html>", { status: 502 }),
    async () => {
      await assert.rejects(
        () => request("/health"),
        (error: unknown) => {
          assert.ok(error instanceof ApiError);
          assert.equal(error.status, 502);
          assert.equal(error.code, null);
          // No HTML, no stack, no path-and-status developer sentence.
          assert.match(error.message, /server had a problem/i);
          return true;
        },
      );
    },
  );
});

// --- where the API is, per environment (Phase 10) -------------------------
//
// The browser and the server resolve the API differently on purpose, and the
// difference is the whole reason authentication works in a split deployment.
// These pin both halves.

test("in the browser the API base is relative, so calls are same-origin", () => {
  const original = globalThis.window;
  // A bare object is enough: `apiBaseUrl` only asks whether `window` is defined.
  (globalThis as { window?: unknown }).window = {};
  try {
    assert.equal(apiBaseUrl(), "/api/v1");
  } finally {
    if (original === undefined) delete (globalThis as { window?: unknown }).window;
    else (globalThis as { window?: unknown }).window = original;
  }
});

test("on the server the API base is absolute", () => {
  // No `window` here: this file runs under `node --test`.
  assert.ok(apiBaseUrl().startsWith("http"));
  assert.ok(apiBaseUrl().endsWith("/api/v1"));
});

test("the server base follows API_ORIGIN", () => {
  const original = process.env.API_ORIGIN;
  process.env.API_ORIGIN = "https://api.example.test";
  try {
    assert.equal(apiBaseUrl(), "https://api.example.test/api/v1");
  } finally {
    if (original === undefined) delete process.env.API_ORIGIN;
    else process.env.API_ORIGIN = original;
  }
});

test("the server base falls back to the local backend", () => {
  const original = process.env.API_ORIGIN;
  delete process.env.API_ORIGIN;
  try {
    assert.equal(apiBaseUrl(), "http://localhost:8000/api/v1");
  } finally {
    if (original !== undefined) process.env.API_ORIGIN = original;
  }
});
