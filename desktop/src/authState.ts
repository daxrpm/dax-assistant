import type { AuthStatus } from "./api/types";

export function permitsAuthenticatedShell(status: AuthStatus | null): boolean {
  return status !== null && (!status.auth_enabled || status.authenticated);
}
