/**
 * Leaderboard endpoint.
 *
 * No user id in the signature: the server resolves the caller and flags their
 * row, so a client cannot ask to be highlighted as somebody else.
 */

import { request } from "./client.ts";
import type { LeaderboardResponse } from "./types";

/** Learner standings, ranked by lifetime XP. */
export function getLeaderboard(init?: RequestInit): Promise<LeaderboardResponse> {
  return request<LeaderboardResponse>("/leaderboard", init);
}
