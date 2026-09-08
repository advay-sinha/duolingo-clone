/**
 * Response types for every backend endpoint.
 *
 * These mirror the Pydantic schemas in `backend/app/schemas/`. They live in one
 * module rather than beside each API function so a shape is declared once and
 * imported wherever it is needed — the alternative is the same interface drifting
 * in three files.
 *
 * **They are hand-written, and that is a known trade-off.** Nothing forces them
 * to match the backend; a renamed field would compile here and fail at runtime.
 * The alternative is generating a client from the FastAPI OpenAPI document,
 * which removes the risk at the cost of a build step. With five endpoints,
 * hand-writing is the smaller cost — that judgement flips as the API grows.
 */

// --- health ---------------------------------------------------------------

/** `GET /health` */
export interface Health {
  status: string;
}

// --- courses --------------------------------------------------------------

/** One course, as returned by `GET /courses`. */
export interface CourseSummary {
  id: number;
  title: string;
  description: string;
  source_language: string;
  target_language: string;
  flag_emoji: string;
}

/** `GET /courses` */
export interface CourseListResponse {
  courses: CourseSummary[];
}

// --- learning path --------------------------------------------------------

/**
 * A skill's state for the current learner.
 *
 * Computed by the backend's `PathService`, never stored. The Stitch design also
 * shows an "in progress" node; that is a rendering distinction the UI derives
 * from `lessons_completed > 0` on an `AVAILABLE` skill, and deliberately not a
 * domain state. `PLACED_OUT` *is* one, because it says something about the
 * learner's history that no other field does.
 */
export type SkillState =
  | "LOCKED"
  | "AVAILABLE"
  | "COMPLETED"
  | /**
     * A placement test placed the learner beyond this skill (Phase 9.5).
     *
     * Kept distinct from `COMPLETED` all the way to the UI, because it is a
     * different fact: the learner never did these lessons. It unlocks what
     * follows exactly as a crown does, and the skill stays playable.
     */
    "PLACED_OUT";

export interface LessonNode {
  id: number;
  title: string;
  order_index: number;
  xp_reward: number;
  completed: boolean;
}

export interface SkillNode {
  id: number;
  title: string;
  description: string;
  order_index: number;
  /** Material Symbols icon name for the node glyph. */
  icon: string;
  state: SkillState;
  crowns: number;
  /** True when a placement test placed the learner beyond this skill. */
  placed_out: boolean;
  lessons_completed: number;
  total_lessons: number;
  xp_earned: number;
  lessons: LessonNode[];
}

export interface UnitNode {
  id: number;
  title: string;
  description: string;
  order_index: number;
  /** Design-token key for the unit banner colour. */
  color_key: string;
  skills: SkillNode[];
}

/** `GET /courses/{id}/path` */
export interface CoursePathResponse {
  course_id: number;
  course_title: string;
  source_language: string;
  target_language: string;
  units: UnitNode[];
}

// --- user -----------------------------------------------------------------

/** `GET /users/me` */
export interface UserSummary {
  id: number;
  username: string;
  display_name: string;
  avatar_url: string;
}

/**
 * `GET /users/me/stats`
 *
 * Note there is no progress percentage anywhere in the API: the server sends
 * counts, the client renders ratios.
 */
export interface UserStats {
  total_xp: number;
  gems: number;
  hearts: number;
  max_hearts: number;
  current_streak: number;
  longest_streak: number;
  daily_goal: number;
  daily_xp: number;
}

// --- lesson engine --------------------------------------------------------

export type ExerciseType =
  | "MULTIPLE_CHOICE"
  | "TRANSLATE"
  | "MATCH_PAIRS"
  | "FILL_BLANK"
  | "TYPE_ANSWER";

/**
 * One exercise as the renderer receives it.
 *
 * There is no answer field, and there never will be: the backend's
 * `ExercisePublic` schema does not declare one, so the answer cannot reach the
 * browser even by mistake. Correctness is decided server-side.
 *
 * `data` is the type-specific payload:
 * - `MULTIPLE_CHOICE` — `{ options: { id, text }[] }`
 * - `TRANSLATE`       — `{ tokens: string[] }`
 * - `MATCH_PAIRS`     — `{ left: { id, text }[], right: { id, text }[] }`
 * - `FILL_BLANK`      — `{ sentence: string, options: string[] }`
 * - `TYPE_ANSWER`     — `{ language: string }`
 */
export interface ExercisePublic {
  id: number;
  type: ExerciseType;
  order_index: number;
  instruction: string;
  prompt: string;
  data: Record<string, unknown>;
}

/** `GET /lessons/{id}` */
export interface LessonResponse {
  id: number;
  title: string;
  order_index: number;
  xp_reward: number;
  skill: { id: number; title: string };
  exercises: ExercisePublic[];
}

/** `POST /lessons/{id}/start` */
export interface StartLessonResponse {
  attempt_id: number;
  lesson_id: number;
  started_at: string;
  hearts: number;
  max_hearts: number;
  lesson: LessonResponse;
}

/**
 * The shape of a submitted answer, by exercise type. Mirrors what the backend
 * graders accept; anything else comes back as a 422.
 */
export type AnswerPayload =
  | { option_id: string }
  | { tokens: string[] }
  | { pairs: [string, string][] }
  | { text: string };

/** `POST /lessons/{id}/answer` request body. */
export interface SubmitAnswerRequest {
  attempt_id: number;
  exercise_id: number;
  answer: AnswerPayload;
}

/** `POST /lessons/{id}/answer` response. */
export interface SubmitAnswerResponse {
  correct: boolean;
  /** Populated only after an incorrect submission, for feedback. */
  correct_answer: string | null;
  xp_earned: number;
  hearts_remaining: number;
  /** True when this exercise was already answered and the verdict was replayed. */
  already_answered: boolean;
  answered_count: number;
  total_exercises: number;
}

/** `POST /lessons/{id}/complete` request body — deliberately carries no score. */
export interface CompleteLessonRequest {
  attempt_id: number;
}

/** `POST /lessons/{id}/complete` response. */
export interface CompleteLessonResponse {
  attempt_id: number;
  lesson_id: number;
  correct_answers: number;
  incorrect_answers: number;
  total_exercises: number;
  accuracy: number;
  xp_earned: number;
  /** False for a repeat completion, which awards no XP. */
  first_completion: boolean;
  total_xp: number;
  daily_xp: number;
  daily_goal: number;
  hearts_remaining: number;
  current_streak: number;
  longest_streak: number;
  streak_extended: boolean;
  skill_id: number;
  lessons_completed: number;
  total_lessons: number;
  crowns: number;
  crown_earned: boolean;
  /** Titles of achievements this completion unlocked; usually empty. */
  achievements_unlocked: string[];
}

// --- leaderboard ----------------------------------------------------------

/** One row of the standings. Deliberately narrow: this is the only place one
 *  learner's data is shown to another. */
export interface LeaderboardEntry {
  rank: number;
  user_id: number;
  display_name: string;
  avatar_url: string;
  /** Lifetime XP — the ranking metric. */
  xp: number;
  current_streak: number;
  /** The server flags the caller's own row, so the client never compares ids. */
  is_current_user: boolean;
}

/** `GET /leaderboard` */
export interface LeaderboardResponse {
  /** e.g. "all-time" — stated by the server so the UI cannot mislabel it. */
  period: string;
  metric: string;
  entries: LeaderboardEntry[];
  /** Null when the caller falls outside the returned page. */
  current_user_rank: number | null;
}

// --- achievements ---------------------------------------------------------

/** One achievement with this learner's unlock state. Locked and unlocked share
 *  a shape; `unlocked` is the discriminator. */
export interface AchievementItem {
  id: number;
  key: string;
  title: string;
  description: string;
  icon: string;
  color_key: string;
  unlocked: boolean;
  unlocked_at: string | null;
}

/** `GET /users/me/achievements` */
export interface AchievementListResponse {
  achievements: AchievementItem[];
  unlocked_count: number;
  total_count: number;
}

// --- profile --------------------------------------------------------------

/**
 * `GET /users/me/profile`
 *
 * The aggregates are counted in SQL. The client never totals lesson attempts
 * itself — persistent statistics belong to the backend.
 */
export interface LearnerProfile {
  user: UserSummary;
  stats: UserStats;
  lessons_completed: number;
  skills_completed: number;
  total_crowns: number;
  perfect_lessons: number;
}

// --- authentication -------------------------------------------------------

/**
 * The caller, as described to themselves.
 *
 * This is the only type in the file that carries an email, because it is the
 * only one that describes *you*. `LeaderboardEntry` describes someone else and
 * deliberately does not — see the backend's `schemas/auth.py`.
 *
 * There is no `password` and no `password_hash` field, and there never will be:
 * the backend's response models do not declare them, so they cannot arrive.
 */
export interface AuthenticatedUser {
  id: number;
  username: string;
  email: string;
  display_name: string;
  avatar_url: string;
  created_at: string;
}

/** `POST /auth/register`, `POST /auth/login`, `GET /auth/me`. */
export interface AuthResponse {
  user: AuthenticatedUser;
}

/** `POST /auth/logout`. */
export interface LogoutResponse {
  /** False when there was no session to end — not an error. */
  ended: boolean;
}

// --- match pairs ----------------------------------------------------------

/**
 * `POST /lessons/{id}/pair` — the verdict on one match-pairs selection.
 *
 * `matched_pairs` is the server's complete record of accepted pairs, not a
 * delta, so a client that dropped a response cannot drift out of step with what
 * the server believes.
 */
export interface SubmitPairResponse {
  correct: boolean;
  pair_completed: boolean;
  matched_pairs: [string, string][];
  exercise_complete: boolean;
  /**
   * Whether the finished exercise counts as correct — no wrong pair was
   * submitted. Sent by the server rather than inferred from `xp_earned`, so the
   * feedback bar shows a verdict it was given, not one it worked out.
   */
  exercise_correct: boolean;
  hearts_remaining: number;
  xp_earned: number;
  already_answered: boolean;
  answered_count: number;
  total_exercises: number;
}

// --- onboarding -----------------------------------------------------------

/**
 * The five proficiency answers, as a controlled union.
 *
 * The same five values the backend's `ProficiencyLevel` enum declares. A union
 * rather than `string`, so a typo is a compile error here and a 422 there — the
 * label a learner reads is copy and will change; this value must not.
 */
export type ProficiencyLevel =
  | "BEGINNER"
  | "COMMON_WORDS"
  | "BASIC_CONVERSATION"
  | "VARIOUS_TOPICS"
  | "ADVANCED";

/** Which of the two starting-point cards the learner chose. */
export type StartingMode = "SCRATCH" | "PLACEMENT";

/**
 * The onboarding step the learner is on.
 *
 * **Computed by the server**, from which of its columns are still null. The
 * frontend routes on this value and never works the sequence out for itself,
 * which is what makes onboarding resume correctly after a refresh, a logout, or
 * a login on a different device.
 */
export type OnboardingStep =
  | "COURSE"
  | "PROFICIENCY"
  | "START"
  | "PLACEMENT"
  | "DONE";

/** The stored outcome of a placement test. */
export interface PlacementSummary {
  level: number;
  score: number;
  max_score: number;
  skill_id: number | null;
  skill_title: string | null;
  unit_title: string | null;
  skills_placed_out: number;
}

/** `GET /onboarding`, and the response of every onboarding write. */
export interface OnboardingStatus {
  completed: boolean;
  step: OnboardingStep;
  course_id: number | null;
  proficiency: ProficiencyLevel | null;
  starting_mode: StartingMode | null;
  placement: PlacementSummary | null;
  /** True for a learner who registered before onboarding existed. */
  grandfathered: boolean;
  completed_at: string | null;
}

// --- placement ------------------------------------------------------------

/** One placement question, with where it sits in the test. */
export interface PlacementQuestion {
  exercise: ExercisePublic;
  /** The difficulty band it was drawn from, 1-5. */
  difficulty: number;
  /** 1-based, for "Question 3 of 8". */
  number: number;
}

/** `POST /placement/start` — the open test and the question to show now. */
export interface PlacementState {
  test_id: number;
  total_questions: number;
  answered_count: number;
  finished: boolean;
  question: PlacementQuestion | null;
}

/**
 * `POST /placement/answer`.
 *
 * A superset of `PlacementState`, deliberately: the verdict fields are added to
 * the same shape, so one render function handles both and the client never
 * merges a response into state it was already holding.
 */
export interface PlacementAnswerResult extends PlacementState {
  correct: boolean;
  /** Populated only after an incorrect answer, for feedback. */
  correct_answer: string | null;
  already_answered: boolean;
}

/**
 * `POST /placement/complete`.
 *
 * Note what is absent and always will be: xp, hearts, streak, crowns. A
 * placement response has no field a reward could travel in.
 */
export interface PlacementResult {
  test_id: number;
  level: number;
  score: number;
  max_score: number;
  total_questions: number;
  correct_answers: number;
  skill_id: number;
  skill_title: string;
  unit_title: string;
  skills_placed_out: number;
  onboarding: OnboardingStatus;
}
