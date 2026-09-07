/**
 * One labelled input for the auth forms.
 *
 * Accessibility is the whole reason this is a component rather than repeated
 * markup. Four things have to stay in step and are easy to get wrong one at a
 * time: the `<label htmlFor>` / `id` pairing, `aria-invalid` when the field is
 * wrong, `aria-describedby` pointing at the message, and the message being
 * rendered where a screen reader will reach it. Doing it once means every field
 * gets all four.
 *
 * Not a Client Component: it renders inputs and takes props. The state lives in
 * the form above it.
 */

export function AuthField({
  id,
  label,
  type,
  value,
  onChange,
  autoComplete,
  error,
  disabled,
  hint,
}: {
  id: string;
  label: string;
  type: "text" | "email" | "password";
  value: string;
  onChange: (value: string) => void;
  autoComplete: string;
  error?: string | null;
  disabled?: boolean;
  hint?: string;
}) {
  const messageId = error ? `${id}-error` : hint ? `${id}-hint` : undefined;

  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor={id} className="text-label-md uppercase text-text-secondary">
        {label}
      </label>
      <input
        id={id}
        type={type}
        value={value}
        disabled={disabled}
        // Tells a password manager what this field is for. Getting it wrong is
        // why so many sign-up forms fight with autofill.
        autoComplete={autoComplete}
        aria-invalid={error ? true : undefined}
        aria-describedby={messageId}
        onChange={(event) => onChange(event.target.value)}
        className={[
          "min-h-12 rounded-2xl border-2 bg-surface px-4 text-body-lg text-text",
          "outline-none transition-colors placeholder:text-text-disabled",
          "focus:border-blue disabled:cursor-not-allowed disabled:opacity-60",
          error ? "border-red" : "border-border",
        ].join(" ")}
      />
      {error ? (
        // Not `role="alert"`: the form-level message announces the failure once.
        // A second live region per field would talk over it.
        <p id={messageId} className="text-body-sm text-on-incorrect">
          {error}
        </p>
      ) : hint ? (
        <p id={messageId} className="text-body-sm text-text-secondary">
          {hint}
        </p>
      ) : null}
    </div>
  );
}
