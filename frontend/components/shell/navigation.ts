/**
 * The product's primary destinations, declared once.
 *
 * Both the desktop sidebar and the mobile bottom bar render from this list, so
 * they cannot drift apart — adding a destination is one entry here.
 *
 * `available: false` marks a destination whose screen does not exist yet. Those
 * items render disabled rather than being hidden: showing the shape of the
 * product is honest and useful, whereas a link that silently 404s is not.
 */

export interface NavDestination {
  key: string;
  label: string;
  href: string;
  /** False while the screen is unbuilt — rendered disabled, never linked. */
  available: boolean;
  /** Material-style glyph, drawn inline so there is no icon dependency. */
  icon: "learn" | "leaderboard" | "profile" | "shop";
}

export const NAV_DESTINATIONS: NavDestination[] = [
  { key: "learn", label: "Learn", href: "/learn", available: true, icon: "learn" },
  {
    key: "leaderboard",
    label: "Leaderboard",
    href: "/leaderboard",
    available: true,
    icon: "leaderboard",
  },
  {
    key: "profile",
    label: "Profile",
    href: "/profile",
    available: true,
    icon: "profile",
  },
  { key: "shop", label: "Shop", href: "/shop", available: false, icon: "shop" },
];

/**
 * Which destination a pathname belongs to.
 *
 * Prefix matching, so `/learn/lesson/3` still counts as "Learn" — though the
 * lesson route renders no shell, a future nested screen would.
 */
export function activeKey(pathname: string): string | null {
  const match = NAV_DESTINATIONS.find(
    (item) => pathname === item.href || pathname.startsWith(`${item.href}/`),
  );
  return match?.key ?? null;
}
