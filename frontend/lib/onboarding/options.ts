/**
 * The onboarding screens' content, as data.
 *
 * Three lists — proficiency levels, starting points, and the course catalogue —
 * kept out of the components that render them. That is not ceremony: each list
 * is asserted against in a test, and a `.map()` over data is what stops five
 * near-identical cards from drifting apart in markup and accessibility.
 */

import type { ProficiencyLevel, StartingMode } from "@/lib/api/types";

// --------------------------------------------------------------------------
// Proficiency
// --------------------------------------------------------------------------

export interface ProficiencyOption {
  /** The value sent to the server. Never the label — copy changes, this must not. */
  value: ProficiencyLevel;
  label: string;
  /** Filled bars out of `PROFICIENCY_BARS`, the Stitch design's strength meter. */
  strength: number;
}

/** How many bars the proficiency indicator draws. */
export const PROFICIENCY_BARS = 4;

/**
 * The five answers, weakest first.
 *
 * The order is the design's and it is meaningful: the bars fill as the list
 * descends, so the ladder reads at a glance without anyone parsing the sentences.
 */
export const PROFICIENCY_OPTIONS: ProficiencyOption[] = [
  { value: "BEGINNER", label: "I'm new to Spanish", strength: 0 },
  { value: "COMMON_WORDS", label: "I know some common words", strength: 1 },
  { value: "BASIC_CONVERSATION", label: "I can have basic conversations", strength: 2 },
  { value: "VARIOUS_TOPICS", label: "I can talk about various topics", strength: 3 },
  { value: "ADVANCED", label: "I can discuss most topics in detail", strength: 4 },
];

// --------------------------------------------------------------------------
// Starting point
// --------------------------------------------------------------------------

export interface StartingPointOption {
  value: StartingMode;
  title: string;
  description: string;
  /** Emoji standing in for the Stitch illustration. See `CourseTile` for why. */
  icon: string;
}

export const STARTING_POINT_OPTIONS: StartingPointOption[] = [
  {
    value: "SCRATCH",
    title: "Start from scratch",
    description: "Take the easiest lesson of the Spanish course",
    icon: "📗",
  },
  {
    value: "PLACEMENT",
    title: "Find my level",
    description: "Let Duo recommend where you should start learning",
    icon: "🧭",
  },
];

// --------------------------------------------------------------------------
// Courses
// --------------------------------------------------------------------------

/**
 * A language the picker shows but the backend does not have.
 *
 * **These are presentation, and they are honest about it.** The brief is
 * explicit that no fake courses should be created to populate the UI, so none
 * were: there is exactly one row in the `courses` table, and every tile below is
 * rendered as a disabled "Coming soon" card that makes no request. The real
 * course is fetched from `GET /courses` and is the only selectable one.
 *
 * The flag is an emoji rather than one of the Stitch PNGs on purpose — the same
 * argument `DuoMascot` makes. A tile is a few bytes of text that scales and
 * themes itself, against twelve images the build would have to carry.
 */
export interface ComingSoonCourse {
  key: string;
  title: string;
  flag: string;
}

export const COMING_SOON_COURSES: ComingSoonCourse[] = [
  { key: "french", title: "French", flag: "🇫🇷" },
  { key: "german", title: "German", flag: "🇩🇪" },
  { key: "japanese", title: "Japanese", flag: "🇯🇵" },
  { key: "italian", title: "Italian", flag: "🇮🇹" },
  { key: "korean", title: "Korean", flag: "🇰🇷" },
  { key: "portuguese", title: "Portuguese", flag: "🇵🇹" },
  { key: "chinese", title: "Chinese", flag: "🇨🇳" },
];

/** The flag shown for a real course, falling back when the seed has none. */
export function courseFlag(flagEmoji: string): string {
  return flagEmoji.trim() || "🌍";
}
