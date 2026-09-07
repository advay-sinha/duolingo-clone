/**
 * Health endpoint binding.
 *
 * One small module per backend resource — the pattern `courses.ts` and
 * `users.ts` also follow. Response types live in `types.ts` so each shape is
 * declared exactly once.
 */

import { request } from "./client.ts";
import type { Health } from "./types";

export type { Health };

/** Ask the backend whether it is up. */
export function getHealth(): Promise<Health> {
  return request<Health>("/health");
}
