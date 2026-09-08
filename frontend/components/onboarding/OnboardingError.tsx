/**
 * The error banner shared by the onboarding pickers.
 *
 * `role="alert"` so the message is announced when it appears — a learner using a
 * screen reader would otherwise get no signal that the button they pressed did
 * nothing. Renders nothing at all when there is no error, rather than an empty
 * live region, so the announcement fires on insertion.
 */

export function OnboardingError({ message }: { message: string | null }) {
  if (!message) return null;

  return (
    <p
      role="alert"
      className="rounded-2xl border-2 border-red/40 bg-feedback-incorrect px-4 py-3 text-body-sm text-on-incorrect"
    >
      {message}
    </p>
  );
}
