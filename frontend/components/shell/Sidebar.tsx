"use client";

/**
 * The desktop navigation rail.
 *
 * 256px fixed, per the Stitch design and `DESIGN.md`. Hidden below `lg`, where
 * `MobileBottomNav` takes over — the two render from the same
 * `NAV_DESTINATIONS` list, so they cannot drift.
 *
 * A Client Component only because it reads the current pathname to mark the
 * active item; everything it renders is static.
 */

import Link from "next/link";
import { usePathname } from "next/navigation";

import { DuoMascot } from "@/components/lesson/DuoMascot";

import { NavIcon } from "./NavIcon";
import { activeKey, NAV_DESTINATIONS } from "./navigation";

export function Sidebar() {
  const pathname = usePathname();
  const active = activeKey(pathname);

  return (
    <aside className="fixed inset-y-0 left-0 z-40 hidden w-64 flex-col gap-6 border-r-2 border-border bg-surface px-4 py-6 lg:flex">
      <Link
        href="/learn"
        className="flex items-center gap-2 px-2"
        aria-label="Duolingo Clone, go to Learn"
      >
        {/* Reuses the Phase 5 mascot rather than adding a second implementation. */}
        <DuoMascot className="h-9 w-9" />
        <span className="text-headline-lg lowercase text-green">duolingo</span>
      </Link>

      <nav aria-label="Main">
        <ul className="flex flex-col gap-1">
          {NAV_DESTINATIONS.map((item) => {
            const isActive = active === item.key;

            // Unbuilt destinations are shown but not linked. A disabled button
            // states the situation honestly; a link that 404s does not.
            if (!item.available) {
              return (
                <li key={item.key}>
                  <button
                    type="button"
                    disabled
                    aria-disabled="true"
                    title="Coming soon"
                    className="flex w-full cursor-not-allowed items-center gap-3 rounded-xl px-3 py-3 text-label-md uppercase text-text-disabled"
                  >
                    <NavIcon icon={item.icon} className="h-6 w-6" />
                    <span>{item.label}</span>
                    <span className="ml-auto text-caption normal-case">Soon</span>
                  </button>
                </li>
              );
            }

            return (
              <li key={item.key}>
                <Link
                  href={item.href}
                  aria-current={isActive ? "page" : undefined}
                  className={`flex items-center gap-3 rounded-xl border-2 px-3 py-3 text-label-md uppercase transition-colors ${
                    isActive
                      ? "border-blue bg-blue/10 text-blue-depth"
                      : "border-transparent text-text-secondary hover:bg-surface-subtle hover:text-text"
                  }`}
                >
                  <NavIcon icon={item.icon} className="h-6 w-6" />
                  <span>{item.label}</span>
                </Link>
              </li>
            );
          })}
        </ul>
      </nav>
    </aside>
  );
}
