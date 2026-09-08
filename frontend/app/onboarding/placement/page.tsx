/**
 * `/onboarding/placement` — the placement test.
 *
 * The only onboarding screen without `OnboardingLayout`: the test needs the full
 * viewport and its own header, in the same way the lesson player drops the app
 * chrome. It still lives under `/onboarding`, because that is what it is — the
 * last step, and onboarding stays incomplete until it finishes.
 *
 * The guard is what makes the test resumable: a learner who closes the tab and
 * comes back lands here again, and `POST /placement/start` returns their open
 * test with the question they had reached.
 */

import { PlacementRunner } from "@/components/onboarding/PlacementRunner";
import { requireStep } from "@/lib/onboarding/guard";

export const metadata = { title: "Placement test · Duolingo Clone" };

export const dynamic = "force-dynamic";

export default async function PlacementPage() {
  await requireStep("PLACEMENT");

  return <PlacementRunner />;
}
