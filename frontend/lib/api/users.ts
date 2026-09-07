/**
 * Current-learner endpoints.
 *
 * There is no user id in any signature: the backend decides who the caller is,
 * from their session cookie. The client never names a user, so it can never ask
 * for someone else's data — there is no field in which to ask.
 *
 * The optional `init` is how a Server Component forwards the incoming request's
 * cookie; see `lib/api/server.ts`.
 */

import { request } from "./client.ts";
import type {
  AchievementListResponse,
  LearnerProfile,
  UserStats,
  UserSummary,
} from "./types";

/** Identity of the current learner. */
export function getCurrentUser(init?: RequestInit): Promise<UserSummary> {
  return request<UserSummary>("/users/me", init);
}

/** XP, hearts, streak, daily goal and gems for the current learner. */
export function getCurrentUserStats(init?: RequestInit): Promise<UserStats> {
  return request<UserStats>("/users/me/stats", init);
}

/**
 * The learner's profile: identity, stats and lifetime aggregates in one call.
 *
 * One request rather than three, and the aggregates are counted server-side —
 * the payload stays the same size however much the learner has practised.
 */
export function getLearnerProfile(init?: RequestInit): Promise<LearnerProfile> {
  return request<LearnerProfile>("/users/me/profile", init);
}

/** The achievement catalogue with this learner's unlock state. */
export function getAchievements(
  init?: RequestInit,
): Promise<AchievementListResponse> {
  return request<AchievementListResponse>("/users/me/achievements", init);
}
