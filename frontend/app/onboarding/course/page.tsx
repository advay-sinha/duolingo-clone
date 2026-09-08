/**
 * `/onboarding/course` — step 1 of 4.
 *
 * A Server Component that fetches the real course list and the learner's
 * onboarding status, then hands both to one Client Component. The grid, the
 * mascot and the copy cost no JavaScript; only the selection does.
 */

import { CoursePicker } from "@/components/onboarding/CoursePicker";
import { OnboardingLayout } from "@/components/onboarding/OnboardingLayout";
import { getCourses } from "@/lib/api/courses";
import { forwardedAuth } from "@/lib/api/server";
import { requireStep } from "@/lib/onboarding/guard";
import { stepProgress } from "@/lib/onboarding/steps";

export const metadata = { title: "Choose a course · Duolingo Clone" };

// The answer depends on the caller's onboarding row, so it can never be cached.
export const dynamic = "force-dynamic";

export default async function CoursePage() {
  const status = await requireStep("COURSE");
  const { courses } = await getCourses(await forwardedAuth());

  return (
    <OnboardingLayout
      progress={stepProgress("COURSE")}
      question="What do you want to learn?"
    >
      <CoursePicker courses={courses} initial={status.course_id} />
    </OnboardingLayout>
  );
}
