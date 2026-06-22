import { useState, type FormEvent } from "react";
import {
  Alert,
  Button,
  Card,
  Center,
  PasswordInput,
  Stack,
  Text,
  Title,
} from "@mantine/core";
import { IconLock } from "@tabler/icons-react";

import { api } from "../../api/client";

interface LoginPageProps {
  configured: boolean;
  onSuccess: () => void;
}

export function LoginPage({ configured, onSuccess }: LoginPageProps) {
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      const res = await api.login(password);
      if (res.ok) {
        onSuccess();
      } else {
        setError("Incorrect password.");
      }
    } catch {
      setError("Incorrect password.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Center h="100vh" p="md">
      <Card withBorder radius="md" p="xl" w={360} shadow="sm">
        <Stack gap="md">
          <Stack gap={4} align="center">
            <Title order={3}>Dax</Title>
            <Text size="sm" c="dimmed">
              Sign in to your assistant
            </Text>
          </Stack>

          {!configured && (
            <Alert color="yellow" title="No password set">
              Set <code>DAX_SECURITY__PASSWORD_HASH</code> in your .env
              (generate one with <code>python -m dax.web.auth &lt;password&gt;</code>).
            </Alert>
          )}

          {error && (
            <Alert color="red" variant="light">
              {error}
            </Alert>
          )}

          <form onSubmit={handleSubmit}>
            <Stack gap="sm">
              <PasswordInput
                leftSection={<IconLock size={16} />}
                placeholder="Password"
                value={password}
                onChange={(e) => setPassword(e.currentTarget.value)}
                autoFocus
                disabled={!configured}
              />
              <Button
                type="submit"
                fullWidth
                loading={submitting}
                disabled={!configured || !password}
              >
                Sign in
              </Button>
            </Stack>
          </form>
        </Stack>
      </Card>
    </Center>
  );
}
