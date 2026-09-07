/**
 * Navigation glyphs, drawn inline.
 *
 * The Stitch screens use Material Symbols via a Google Fonts stylesheet. Four
 * inline paths cost nothing, avoid a render-blocking font request for four
 * icons, and inherit `currentColor` so they follow the active/disabled states
 * without extra styling.
 */

import type { NavDestination } from "./navigation";

const PATHS: Record<NavDestination["icon"], string> = {
  // graduation cap
  learn: "M12 3 1 9l11 6 9-4.91V17h2V9L12 3zM5 13.18v4L12 21l7-3.82v-4L12 17l-7-3.82z",
  // medal
  leaderboard:
    "M12 2 8 6l4 4 4-4-4-4zm0 8a6 6 0 1 0 0 12 6 6 0 0 0 0-12zm0 3.2 1.2 2.5 2.7.4-2 1.9.5 2.7-2.4-1.3-2.4 1.3.5-2.7-2-1.9 2.7-.4L12 13.2z",
  // person
  profile:
    "M12 12a5 5 0 1 0 0-10 5 5 0 0 0 0 10zm0 2c-4.4 0-8 2.2-8 5v3h16v-3c0-2.8-3.6-5-8-5z",
  // storefront
  shop: "M4 4h16l1 5a3 3 0 0 1-5.5 1.7A3 3 0 0 1 12 12a3 3 0 0 1-3.5-1.3A3 3 0 0 1 3 9l1-5zm1 9.9V20h14v-6.1a5 5 0 0 1-3.5-.6A5 5 0 0 1 12 14a5 5 0 0 1-3.5-.7 5 5 0 0 1-3.5.6z",
};

export function NavIcon({
  icon,
  className = "",
}: {
  icon: NavDestination["icon"];
  className?: string;
}) {
  return (
    <svg viewBox="0 0 24 24" className={className} aria-hidden="true" fill="currentColor">
      <path d={PATHS[icon]} />
    </svg>
  );
}
