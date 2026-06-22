import { useState } from "react";
import { Button } from "@heroui/react";
import { Sparkles, Eye, EyeOff } from "lucide-react";
import { api } from "../api/client";
import { TextInput } from "../components/ui";

export function LoginPage({
  onLoggedIn,
  configured,
}: {
  onLoggedIn: () => void;
  configured: boolean;
}) {
  const [password, setPassword] = useState("");
  const [show, setShow] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const res = await api.login(password);
      if (res.ok) {
        onLoggedIn();
      } else {
        setError("Incorrect password");
      }
    } catch {
      setError("Login failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex h-full items-center justify-center bg-background px-4 text-foreground">
      <div className="w-full max-w-sm">
        <div className="mb-8 flex flex-col items-center text-center">
          <div className="mb-3 flex h-12 w-12 items-center justify-center rounded-2xl bg-accent text-accent-foreground">
            <Sparkles size={22} />
          </div>
          <h1 className="text-xl font-semibold">Welcome to Dax</h1>
          <p className="mt-1 text-sm text-muted">
            {configured
              ? "Enter your password to continue"
              : "No password configured — set DAX_SECURITY__PASSWORD_HASH"}
          </p>
        </div>

        <form
          onSubmit={submit}
          className="rounded-2xl border border-separator bg-surface p-6 shadow-sm"
        >
          <div className="relative">
            <TextInput
              type={show ? "text" : "password"}
              placeholder="Password"
              autoFocus
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              disabled={!configured}
              className="pr-10"
            />
            <button
              type="button"
              onClick={() => setShow((s) => !s)}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-muted hover:text-foreground"
              tabIndex={-1}
            >
              {show ? <EyeOff size={16} /> : <Eye size={16} />}
            </button>
          </div>

          {error && <p className="mt-3 text-sm text-danger">{error}</p>}

          <Button
            type="submit"
            variant="primary"
            fullWidth
            isDisabled={loading || !configured || !password}
            className="mt-4"
          >
            {loading ? "Signing in…" : "Sign in"}
          </Button>
        </form>
      </div>
    </div>
  );
}
