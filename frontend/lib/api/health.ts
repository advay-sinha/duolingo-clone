/**
 * Health endpoint binding.
 *
 * One small module per backend resource. This is the pattern later phases
 * follow: `lib/api/path.ts`, `lib/api/lessons.ts`, and so on — each exporting
 * typed functions, none of them calling `fetch` themselves.
 */

import { request } from "./client";

/** Body of `GET /api/v1/health`, mirroring the backend's HealthResponse. */
export interface Health {
  status: string;
}

/** Ask the backend whether it is up. */
export function getHealth(): Promise<Health> {
  return request<Health>("/health");
}
