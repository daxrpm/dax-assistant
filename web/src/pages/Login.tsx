import { useState } from "react";
import { Button, Input } from "@heroui/react";
import { Sparkles, Eye, EyeOff, ShieldCheck } from "lucide-react";
import { api } from "../api/client";

/**
 * Single screen for both first-run onboarding and normal login.
 *
 * When `configured` is false there is no account yet, so we render the
 * "create your account" flow (password + confirmation) which calls /auth/setup
 * and signs the user straight in — no .env editing, everything from the UI.
 */
export function LoginPage({
  onLoggedIn,
  configured,
}: {
  onLoggedIn: () => void;
  configured: boolean;
}) {
  const setup = !configured;
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [show, setShow] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");

    if (setup) {
      if (password.length < 8) {
        setError("Password must be at least 8 characters");
        return;
      }
      if (password !== confirm) {
        setError("Passwords do not match");
        return;
      }
    }

    setLoading(true);
    try {
      const res = setup ? await api.setup(password) : await api.login(password);
      if (res.ok) {
        onLoggedIn();
      } else {
        setError(setup ? "Could not create the account" : "Incorrect password");
      }
    } catch {
      setError(setup ? "Setup failed" : "Login failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex h-full items-center justify-center bg-background px-4 text-foreground">
      <div className="w-full max-w-sm">
        <div className="mb-8 flex flex-col items-center text-center">
          <div className="mb-3 flex h-12 w-12 items-center justify-center rounded-2xl bg-accent text-accent-foreground">
            {setup ? <ShieldCheck size={22} /> : <Sparkles size={22} />}
          </div>
          <h1 className="text-xl font-semibold">
            {setup ? "Welcome to Dax" : "Welcome back"}
          </h1>
          <p className="mt-1 text-sm text-muted">
            {setup
              ? "Create your password to set up your assistant"
              : "Enter your password to continue"}
          </p>
        </div>

        <form
          onSubmit={submit}
          className="flex flex-col gap-3 rounded-2xl border border-separator bg-surface p-6 shadow-sm"
        >
          <div className="relative">
            <Input
              type={show ? "text" : "password"}
              placeholder={setup ? "Create a password" : "Password"}
              aria-label="Password"
              autoFocus
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              fullWidth
              className="pr-10"
            />
            <button
              type="button"
              onClick={() => setShow((s) => !s)}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-muted hover:text-foreground"
              tabIndex={-1}
              aria-label={show ? "Hide password" : "Show password"}
            >
              {show ? <EyeOff size={16} /> : <Eye size={16} />}
            </button>
          </div>

          {setup && (
            <Input
              type={show ? "text" : "password"}
              placeholder="Confirm password"
              aria-label="Confirm password"
              value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
              fullWidth
            />
          )}

          {error && <p className="text-sm text-danger">{error}</p>}

          <Button
            type="submit"
            variant="primary"
            fullWidth
            isDisabled={loading || !password || (setup && !confirm)}
            className="mt-1"
          >
            {loading
              ? setup
                ? "Creating…"
                : "Signing in…"
              : setup
                ? "Create account"
                : "Sign in"}
          </Button>
        </form>
      </div>
    </div>
  );
}
