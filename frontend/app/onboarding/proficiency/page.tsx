/**
 * `/onboarding/proficiency` — step 2 of 4.
 *
 * "How much Spanish do you know?", the first Stitch screen. The answer is
 * self-report and is stored as such: it is deliberately not read by the
 * placement engine, because replacing a claim with evidence is the only reason
 * the placement test exists.
 */

import { OnboardingLayout } from "@/components/onboarding/OnboardingLayout";
import { ProficiencyPicker } from "@/components/onboarding/ProficiencyPicker";
import { requireStep } from "@/lib/onboarding/guard";
import { stepProgress } from "@/lib/onboarding/steps";

export const metadata = { title: "How much Spanish do you know? · Duolingo Clone" };

export const dynamic = "force-dynamic";

export default async function ProficiencyPage() {
  const status = await requireStep("PROFICIENCY");

  return (
    <OnboardingLayout
      progress={stepProgress("PROFICIENCY")}
      question="How much Spanish do you know?"
    >
      <ProficiencyPicker initial={status.proficiency} />
    </OnboardingLayout>
  );
}
