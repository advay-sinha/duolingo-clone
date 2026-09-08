import { redirect } from "next/navigation";

import { getOnboardingStatus } from "@/lib/api/onboarding";
import { redirectIfUnauthenticated, forwardedAuth } from "@/lib/api/server";
import type { OnboardingStatus, OnboardingStep } from "@/lib/api/types";

import { redirectFor } from "./steps";

/**
 * Server-side onboarding guard, used by every onboarding page and by `/learn`.
 *
 * **The server decides where a learner belongs, on every request.** This asks the
 * API where they are and redirects if the page they asked for is not it. The
 * consequences are worth spelling out, because each is an acceptance criterion:
 *
 * * typing `/onboarding/placement` before choosing a course bounces to the course
 *   screen — you cannot skip ahead by knowing a URL;
 * * a refresh mid-flow lands on the step the database says, so nothing is lost;
 * * logging out and back in resumes where they were;
 * * a learner who registered before onboarding existed is `DONE`, so `/learn`
 *   renders for them exactly as it always did.
 *
 * `redirect()` throws, so `requireStep` either returns the status or never
 * returns at all.
 */
export async function requireStep(page: OnboardingStep): Promise<OnboardingStatus> {
  const status = await loadStatus();
  const destination = redirectFor(status, page);
  if (destination) redirect(destination);
  return status;
}

/**
 * Fetch the onboarding status, turning "not signed in" into a login redirect.
 *
 * Any other failure is rethrown: a backend that is down is not a reason to send
 * someone to a login form they cannot use.
 */
export async function loadStatus(): Promise<OnboardingStatus> {
  try {
    return await getOnboardingStatus(await forwardedAuth());
  } catch (error: unknown) {
    redirectIfUnauthenticated(error);
    throw error;
  }
}
