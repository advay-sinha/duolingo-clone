/**
 * The frame every onboarding screen sits in.
 *
 * A Server Component: a progress bar, a mascot, a speech bubble and a footer
 * slot, none of which hold state. Only the pickers inside cross into the
 * browser, so three of the four screens ship almost no JavaScript.
 *
 * The layout follows the Stitch "Get started" screens: a thin progress rail
 * across the top, Duo speaking on the left, and a single column of large
 * selectable cards below. It is built from the same tokens and the same
 * `.tactile` / `.card` foundation as the rest of the app rather than a one-off
 * palette — the screens a learner sees first should not be the ones that look
 * like a different product.
 */

import type { ReactNode } from "react";

import { DuoMascot } from "@/components/lesson/DuoMascot";

export function OnboardingLayout({
  progress,
  question,
  children,
  footer,
}: {
  /** How far through onboarding, 0–1. Drives the rail at the top. */
  progress: number;
  /** What Duo asks on this screen. */
  question: string;
  children: ReactNode;
  footer?: ReactNode;
}) {
  const percent = Math.round(Math.min(1, Math.max(0, progress)) * 100);

  return (
    <main className="flex min-h-dvh flex-col">
      <header className="px-4 pt-6">
        <div className="mx-auto w-full max-w-2xl">
          {/* A native progress element rather than a styled div: assistive
              technology reads "45%" without any ARIA being hand-written, and it
              degrades to something meaningful with no CSS at all. */}
          <progress
            className="onboarding-rail h-4 w-full"
            value={percent}
            max={100}
          >
            {percent}%
          </progress>
          <span className="sr-only">Onboarding {percent}% complete</span>
        </div>
      </header>

      <div className="mx-auto flex w-full max-w-2xl flex-1 flex-col gap-7 px-4 pb-40 pt-8">
        <DuoSpeechBubble>{question}</DuoSpeechBubble>
        {children}
      </div>

      {footer && (
        <div className="fixed inset-x-0 bottom-0 z-30 border-t-2 border-border bg-surface">
          <div className="mx-auto w-full max-w-2xl px-4 py-4">{footer}</div>
        </div>
      )}
    </main>
  );
}

/**
 * Duo, and what Duo is saying.
 *
 * The bubble's tail is a rotated square with two borders, the same trick the
 * lesson player's translate prompt uses — no image, no pseudo-element hacks, and
 * it takes its colours from the theme so it is correct in dark mode for free.
 *
 * The question is an `<h1>`: it is genuinely the heading of the page, and
 * marking it up as one is what lets a screen-reader user jump straight to it.
 */
export function DuoSpeechBubble({ children }: { children: ReactNode }) {
  return (
    <div className="flex items-start gap-3">
      <DuoMascot className="h-20 w-20 shrink-0 sm:h-24 sm:w-24" />
      <div className="relative mt-3 flex-1 rounded-2xl border-2 border-border bg-surface px-5 py-4">
        <span
          aria-hidden="true"
          className="absolute -left-2 top-6 h-3.5 w-3.5 rotate-45 border-b-2 border-l-2 border-border bg-surface"
        />
        <h1 className="text-headline-lg text-text">{children}</h1>
      </div>
    </div>
  );
}
