/**
 * The shared frame for the login and register screens.
 *
 * A Server Component: it is layout and copy, with no state and no handlers, so
 * only the form inside it crosses into the browser. The mascot, the heading and
 * the card cost no JavaScript.
 *
 * Visually this is the same language as the rest of the app — a rounded card on
 * the subtle ground, tactile controls, the mascot — rather than the flat,
 * centred, generic sign-in box every SaaS product ships. Someone arriving at
 * `/login` should already be able to tell what kind of product this is.
 */

import Link from "next/link";
import type { ReactNode } from "react";

import { DuoMascot } from "@/components/lesson/DuoMascot";

export function AuthCard({
  title,
  subtitle,
  children,
  footer,
}: {
  title: string;
  subtitle: string;
  children: ReactNode;
  footer: ReactNode;
}) {
  return (
    <main className="mx-auto flex min-h-dvh w-full max-w-md flex-col justify-center gap-6 px-4 py-10">
      <div className="flex flex-col items-center gap-3 text-center">
        <DuoMascot className="h-24 w-24" />
        <h1 className="text-headline-xl text-text">{title}</h1>
        <p className="text-body-md text-text-secondary">{subtitle}</p>
      </div>

      <div className="card flex flex-col gap-5 p-6">{children}</div>

      <p className="text-center text-body-sm text-text-secondary">{footer}</p>
    </main>
  );
}

/** The cross-link between the two auth screens. */
export function AuthSwitch({
  prompt,
  href,
  label,
}: {
  prompt: string;
  href: string;
  label: string;
}) {
  return (
    <>
      {prompt}{" "}
      <Link href={href} className="font-bold text-blue-depth underline">
        {label}
      </Link>
    </>
  );
}
