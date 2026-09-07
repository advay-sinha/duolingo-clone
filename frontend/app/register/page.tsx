/**
 * `/register` — publicly accessible, like `/login`.
 *
 * Registering signs the learner in, so this page hands off to `/learn` directly
 * rather than bouncing through the login form.
 */

import { redirect } from "next/navigation";

import { AuthCard, AuthSwitch } from "@/components/auth/AuthCard";
import { RegisterForm } from "@/components/auth/RegisterForm";
import { getAuthenticatedUser } from "@/lib/api/auth";
import { forwardedAuth } from "@/lib/api/server";

export const metadata = { title: "Create an account · Duolingo Clone" };

export const dynamic = "force-dynamic";

export default async function RegisterPage() {
  let signedIn = false;
  try {
    await getAuthenticatedUser(await forwardedAuth());
    signedIn = true;
  } catch {
    // Expected when signed out.
  }
  if (signedIn) redirect("/learn");

  return (
    <AuthCard
      title="Start learning Spanish"
      subtitle="Free, and your progress is saved as you go."
      footer={
        <AuthSwitch
          prompt="Already have an account?"
          href="/login"
          label="Log in"
        />
      }
    >
      <RegisterForm />
    </AuthCard>
  );
}
