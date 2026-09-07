/**
 * `/login` — publicly accessible, by definition.
 *
 * A Server Component wrapping one Client Component, the same boundary the lesson
 * route uses: the card, the mascot and the copy render on the server, and only
 * the form ships JavaScript.
 *
 * An already-signed-in visitor is sent to `/learn` rather than shown a login
 * form they do not need.
 */

import { redirect } from "next/navigation";

import { AuthCard, AuthSwitch } from "@/components/auth/AuthCard";
import { LoginForm } from "@/components/auth/LoginForm";
import { getAuthenticatedUser } from "@/lib/api/auth";
import { forwardedAuth } from "@/lib/api/server";

export const metadata = { title: "Log in · Duolingo Clone" };

// The answer depends on the caller's cookie, so it can never be cached.
export const dynamic = "force-dynamic";

export default async function LoginPage() {
  let signedIn = false;
  try {
    await getAuthenticatedUser(await forwardedAuth());
    signedIn = true;
  } catch {
    // 401 is the expected case here, and a backend that is down should still
    // render the form — the submit will report the real problem.
  }
  if (signedIn) redirect("/learn");

  return (
    <AuthCard
      title="Welcome back!"
      subtitle="Log in to keep your streak going."
      footer={
        <AuthSwitch
          prompt="New here?"
          href="/register"
          label="Create an account"
        />
      }
    >
      <LoginForm />
    </AuthCard>
  );
}
