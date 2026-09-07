/**
 * The owl mascot, as inline SVG.
 *
 * **Why this is not a Stitch asset.** `stitch/` contains a 1024×1024 PNG of the
 * mascot, but the Stitch *lesson player* draws the owl as inline SVG — and that
 * is the better runtime choice here: a few hundred bytes instead of 760KB, it
 * scales without blurring, and it takes its colours from the design tokens so it
 * stays consistent if the palette changes. The PNG stays reference material.
 *
 * Redrawn as a component rather than pasted as markup, so the lesson prompt can
 * use it anywhere without duplicating forty lines of paths.
 */

export function DuoMascot({ className = "" }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 100 100"
      className={className}
      role="img"
      aria-label="Duo the owl"
    >
      <circle cx="50" cy="50" r="46" fill="var(--color-green)" />
      <ellipse cx="14" cy="50" rx="9" ry="18" fill="var(--color-green-depth)" />
      <ellipse cx="86" cy="50" rx="9" ry="18" fill="var(--color-green-depth)" />
      <ellipse cx="50" cy="55" rx="34" ry="28" fill="#6be026" />
      <ellipse cx="36" cy="46" rx="14" ry="17" fill="#ffffff" />
      <ellipse cx="64" cy="46" rx="14" ry="17" fill="#ffffff" />
      <ellipse cx="39" cy="47" rx="8" ry="11" fill="var(--color-text)" />
      <ellipse cx="61" cy="47" rx="8" ry="11" fill="var(--color-text)" />
      <circle cx="37" cy="43" r="3" fill="#ffffff" />
      <circle cx="59" cy="43" r="3" fill="#ffffff" />
      <path
        d="M 28 32 Q 35 24 45 33"
        fill="none"
        stroke="var(--color-green-depth)"
        strokeWidth="4"
        strokeLinecap="round"
      />
      <path
        d="M 72 32 Q 65 24 55 33"
        fill="none"
        stroke="var(--color-green-depth)"
        strokeWidth="4"
        strokeLinecap="round"
      />
      <path d="M 42 56 Q 50 67 58 56 Q 50 50 42 56 Z" fill="var(--color-orange)" />
      <path d="M 45 56 Q 50 63 55 56 Z" fill="var(--color-orange-depth)" />
    </svg>
  );
}
