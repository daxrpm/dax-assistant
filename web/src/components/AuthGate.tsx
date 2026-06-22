import { useCallback, useEffect, useState, type ReactNode } from "react";
import { Center, Loader } from "@mantine/core";

import { api, type AuthStatus } from "../api/client";
import { LoginPage } from "../pages/Login/LoginPage";

/**
 * Gates the app behind authentication. If auth is disabled server-side, or the
 * user already has a valid session, children render. Otherwise the login page
 * is shown.
 */
export function AuthGate({ children }: { children: ReactNode }) {
  const [authStatus, setAuthStatus] = useState<AuthStatus | null>(null);
  const [loading, setLoading] = useState(true);

  const check = useCallback(async () => {
    try {
      setAuthStatus(await api.authStatus());
    } catch {
      // If the status call itself fails, assume auth is required.
      setAuthStatus({ auth_enabled: true, configured: false, authenticated: false });
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void check();
  }, [check]);

  if (loading) {
    return (
      <Center h="100vh">
        <Loader size="lg" />
      </Center>
    );
  }

  if (authStatus && (!authStatus.auth_enabled || authStatus.authenticated)) {
    return <>{children}</>;
  }

  return (
    <LoginPage configured={authStatus?.configured ?? true} onSuccess={check} />
  );
}
