"use client";

/**
 * The mobile bottom tab bar.
 *
 * `DESIGN.md` specifies a 56px tactile bottom bar below 768px; this shows below
 * `lg`, where the 256px sidebar stops fitting alongside the path. Items are
 * 64px tall so every tap target clears the ~44px guideline comfortably.
 *
 * Renders from the same `NAV_DESTINATIONS` list as the sidebar.
 */

import Link from "next/link";
import { usePathname } from "next/navigation";

import { NavIcon } from "./NavIcon";
import { activeKey, NAV_DESTINATIONS } from "./navigation";

export function MobileBottomNav() {
  const pathname = usePathname();
  const active = activeKey(pathname);

  return (
    <nav
      aria-label="Main"
      className="fixed inset-x-0 bottom-0 z-40 border-t-2 border-border bg-surface lg:hidden"
    >
      <ul className="mx-auto flex max-w-lg">
        {NAV_DESTINATIONS.map((item) => {
          const isActive = active === item.key;
          const shared =
            "flex h-16 w-full flex-col items-center justify-center gap-1 text-caption uppercase";

          if (!item.available) {
            return (
              <li key={item.key} className="flex-1">
                <button
                  type="button"
                  disabled
                  aria-disabled="true"
                  className={`${shared} cursor-not-allowed text-text-disabled`}
                >
                  <NavIcon icon={item.icon} className="h-6 w-6" />
                  <span>{item.label}</span>
                </button>
              </li>
            );
          }

          return (
            <li key={item.key} className="flex-1">
              <Link
                href={item.href}
                aria-current={isActive ? "page" : undefined}
                className={`${shared} ${
                  isActive
                    ? "text-blue-depth"
                    : "text-text-secondary hover:text-text"
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
  );
}
