/**
 * `/onboarding/start` — step 3 of 4, and the branch point.
 *
 * Two cards, two futures: finish onboarding now, or take a placement test first.
 * Both are real — neither is a stub, and the second leads to a test built from
 * the seeded course rather than to a question about which level you would like.
 */

import { OnboardingLayout } from "@/components/onboarding/OnboardingLayout";
import { StartingPointPicker } from "@/components/onboarding/StartingPointPicker";
import { requireStep } from "@/lib/onboarding/guard";
import { stepProgress } from "@/lib/onboarding/steps";

export const metadata = { title: "Where should you start? · Duolingo Clone" };

export const dynamic = "force-dynamic";

export default async function StartPage() {
  await requireStep("START");

  return (
    <OnboardingLayout
      progress={stepProgress("START")}
      question="Now let's find the best place to start!"
    >
      <StartingPointPicker />
    </OnboardingLayout>
  );
}
