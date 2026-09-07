/**
 * Theme preference: light, dark, or follow the system.
 *
 * The pure half lives here so the rules are testable without a browser; the
 * React half is `components/shell/ThemeToggle.tsx`.
 *
 * **Why no global state library.** The theme is one string that changes rarely
 * and is consumed by CSS, not by React. Putting it in a store would mean every
 * component re-rendering on a change that CSS already handles for free. The
 * source of truth is a `data-theme` attribute on `<html>`; `localStorage` is
 * only how it survives a reload.
 */

export type ThemeChoice = "light" | "dark" | "system";

export const THEME_STORAGE_KEY = "duolingo-clone-theme";

export function isThemeChoice(value: unknown): value is ThemeChoice {
  return value === "light" || value === "dark" || value === "system";
}

/**
 * What `data-theme` should be for a given choice.
 *
 * `system` returns `null` — the attribute is *removed* rather than set, which
 * hands control back to the `prefers-color-scheme` media query in the
 * stylesheet. That is why the CSS guards its dark block with
 * `:root:not([data-theme="light"])`: an explicit choice must win in both
 * directions, and absence must mean "ask the OS".
 */
export function attributeFor(choice: ThemeChoice): "light" | "dark" | null {
  return choice === "system" ? null : choice;
}

/**
 * The script that runs before React hydrates.
 *
 * **This is what prevents both a flash of the wrong theme and a hydration
 * mismatch.** Next.js renders on the server, where `localStorage` does not
 * exist, so the server cannot know the learner's choice. If the theme were
 * applied by an effect after hydration, a dark-mode learner would see a white
 * flash on every navigation; if it were applied during render, the server and
 * client markup would disagree and React would warn.
 *
 * Running it as a blocking inline script in `<head>` sidesteps both: the
 * attribute is on `<html>` before the first paint, and React never renders the
 * value at all — it only ever lives in the DOM attribute, so there is nothing
 * for hydration to mismatch on.
 *
 * Wrapped in try/catch because `localStorage` throws outright in some privacy
 * modes; a theme preference is never worth breaking the page for.
 */
export const THEME_INIT_SCRIPT = `
(function () {
  try {
    var stored = localStorage.getItem(${JSON.stringify(THEME_STORAGE_KEY)});
    if (stored === "light" || stored === "dark") {
      document.documentElement.setAttribute("data-theme", stored);
    }
  } catch (e) {}
})();
`.trim();
