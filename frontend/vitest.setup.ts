/**
 * Test environment setup.
 *
 * jsdom implements the DOM but not every browser API a component may touch, so
 * the few we rely on are stubbed here rather than in each test.
 */

import { afterEach, vi } from "vitest";
import { cleanup } from "@testing-library/react";

// Unmount between tests so queries cannot see the previous test's markup.
afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

// jsdom has no speech synthesis. Stubbing it means SpeakButton renders (rather
// than returning null) so its behaviour can be asserted, and gives tests a spy
// to check that speaking is actually requested.
Object.defineProperty(window, "speechSynthesis", {
  writable: true,
  configurable: true,
  value: {
    speak: vi.fn(),
    cancel: vi.fn(),
    getVoices: () => [],
  },
});

class MockUtterance {
  text: string;
  lang = "";
  rate = 1;
  constructor(text: string) {
    this.text = text;
  }
}
Object.defineProperty(window, "SpeechSynthesisUtterance", {
  writable: true,
  configurable: true,
  value: MockUtterance,
});
