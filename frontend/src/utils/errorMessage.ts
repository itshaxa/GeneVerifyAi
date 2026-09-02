/**
 * Step 10: one place that turns an unknown failure into a screen-safe message.
 *
 * `ApiError.message` is built from the backend's `detail` field, which is
 * already a human sentence (see `services/apiClient.ts`), so it is safe to
 * show. Anything else is replaced by the caller's own wording - a stack,
 * database error, filesystem path or raw provider payload can therefore never
 * reach the UI by accident.
 */

import { ApiError } from '../services/apiClient'

export function describeError(error: unknown, fallback: string): string {
  return error instanceof ApiError && error.message ? error.message : fallback
}

/** True for a 404, which several views treat as "nothing recorded yet". */
export function isNotFound(error: unknown): boolean {
  return error instanceof ApiError && error.status === 404
}
