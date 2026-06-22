import { useEffect, useState, type ChangeEvent } from "react";
import {
  Badge,
  Card,
  Group,
  SimpleGrid,
  Stack,
  Switch,
  Table,
  Text,
  ThemeIcon,
  Title,
  Loader,
  Alert,
} from "@mantine/core";
import {
  IconActivity,
  IconBrain,
  IconServer,
  IconMicrophone,
  IconInfoCircle,
  IconShieldCheck,
} from "@tabler/icons-react";
import { useStatus, useConfig } from "../../hooks/useConfig";
import { api, type ToolAuditEntry } from "../../api/client";

const AUDIT_STATUS_COLOR: Record<string, string> = {
  executed: "green",
  approved: "green",
  declined: "orange",
  denied: "red",
  error: "red",
};

function ToolAuditCard() {
  const [entries, setEntries] = useState<ToolAuditEntry[]>([]);

  useEffect(() => {
    let active = true;
    const load = () =>
      api
        .getToolAudit(15)
        .then((data) => active && setEntries(data))
        .catch(() => undefined);
    void load();
    const timer = setInterval(load, 5000);
    return () => {
      active = false;
      clearInterval(timer);
    };
  }, []);

  return (
    <Card withBorder padding="lg" radius="md">
      <Card.Section withBorder inheritPadding py="xs">
        <Group justify="space-between">
          <Text fw={500} size="sm" c="dimmed">
            Recent Tool Activity
          </Text>
          <ThemeIcon variant="light" color="grape" size="md">
            <IconShieldCheck size={16} />
          </ThemeIcon>
        </Group>
      </Card.Section>
      {entries.length === 0 ? (
        <Text c="dimmed" size="sm" mt="md">
          No tool activity yet.
        </Text>
      ) : (
        <Table mt="md" verticalSpacing="xs" fz="sm">
          <Table.Thead>
            <Table.Tr>
              <Table.Th>Time</Table.Th>
              <Table.Th>Tool</Table.Th>
              <Table.Th>Status</Table.Th>
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {entries.map((e, i) => (
              <Table.Tr key={`${e.timestamp}-${i}`}>
                <Table.Td>
                  {new Date(e.timestamp).toLocaleTimeString([], {
                    hour: "2-digit",
                    minute: "2-digit",
                  })}
                </Table.Td>
                <Table.Td>
                  <Text size="sm" ff="monospace">
                    {e.tool_name}
                  </Text>
                </Table.Td>
                <Table.Td>
                  <Badge
                    size="sm"
                    variant="light"
                    color={AUDIT_STATUS_COLOR[e.status] ?? "gray"}
                  >
                    {e.status}
                  </Badge>
                </Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      )}
    </Card>
  );
}

const SYSTEM_STATUS = {
  RUNNING: "running",
  STOPPED: "stopped",
} as const;

type SystemStatus = (typeof SYSTEM_STATUS)[keyof typeof SYSTEM_STATUS];

function getStatusColor(status: string): string {
  if (status === SYSTEM_STATUS.RUNNING) return "green";
  if (status === SYSTEM_STATUS.STOPPED) return "red";
  return "gray";
}

export function DashboardPage() {
  const { status, loading, error, refresh } = useStatus();
  const { config } = useConfig();
  const [togglingVoice, setTogglingVoice] = useState(false);

  const handleVoiceToggle = async (checked: boolean) => {
    setTogglingVoice(true);
    try {
      await api.toggleVoice(checked);
      await refresh();
    } finally {
      setTogglingVoice(false);
    }
  };

  if (loading && !status) {
    return (
      <Stack align="center" justify="center" h="60vh">
        <Loader size="lg" />
        <Text c="dimmed">Loading status...</Text>
      </Stack>
    );
  }

  if (error && !status) {
    return (
      <Alert
        color="red"
        title="Connection Error"
        icon={<IconInfoCircle size={18} />}
      >
        {error}
      </Alert>
    );
  }

  if (!status) return null;

  const systemStatus = status.status as SystemStatus;

  return (
    <Stack gap="lg">
      <Title order={2}>Dashboard</Title>

      <SimpleGrid cols={{ base: 1, sm: 2, lg: 4 }} spacing="md">
        <Card withBorder padding="lg" radius="md">
          <Card.Section withBorder inheritPadding py="xs">
            <Group justify="space-between">
              <Text fw={500} size="sm" c="dimmed">
                System Status
              </Text>
              <ThemeIcon
                variant="light"
                color={getStatusColor(systemStatus)}
                size="md"
              >
                <IconActivity size={16} />
              </ThemeIcon>
            </Group>
          </Card.Section>
          <Stack gap="xs" mt="md">
            <Badge
              color={getStatusColor(systemStatus)}
              variant="light"
              size="lg"
            >
              {systemStatus}
            </Badge>
          </Stack>
        </Card>

        <Card withBorder padding="lg" radius="md">
          <Card.Section withBorder inheritPadding py="xs">
            <Group justify="space-between">
              <Text fw={500} size="sm" c="dimmed">
                LLM Provider
              </Text>
              <ThemeIcon variant="light" color="violet" size="md">
                <IconBrain size={16} />
              </ThemeIcon>
            </Group>
          </Card.Section>
          <Stack gap="xs" mt="md">
            <Text fw={600} size="lg">
              {status.llm_provider}
            </Text>
            <Badge
              color={
                systemStatus === SYSTEM_STATUS.RUNNING ? "green" : "gray"
              }
              variant="light"
              size="sm"
            >
              {systemStatus === SYSTEM_STATUS.RUNNING
                ? "Available"
                : "Unavailable"}
            </Badge>
          </Stack>
        </Card>

        <Card withBorder padding="lg" radius="md">
          <Card.Section withBorder inheritPadding py="xs">
            <Group justify="space-between">
              <Text fw={500} size="sm" c="dimmed">
                MCP Servers
              </Text>
              <ThemeIcon variant="light" color="blue" size="md">
                <IconServer size={16} />
              </ThemeIcon>
            </Group>
          </Card.Section>
          <Stack gap="xs" mt="md">
            <Group gap="lg">
              <Stack gap={2}>
                <Text fw={600} size="xl">
                  {status.mcp_servers}
                </Text>
                <Text size="xs" c="dimmed">
                  Servers
                </Text>
              </Stack>
              <Stack gap={2}>
                <Text fw={600} size="xl">
                  {status.mcp_tools}
                </Text>
                <Text size="xs" c="dimmed">
                  Tools
                </Text>
              </Stack>
            </Group>
          </Stack>
        </Card>

        <Card withBorder padding="lg" radius="md">
          <Card.Section withBorder inheritPadding py="xs">
            <Group justify="space-between">
              <Text fw={500} size="sm" c="dimmed">
                Voice Listening
              </Text>
              <ThemeIcon
                variant="light"
                color={status.voice_listening ? "teal" : "gray"}
                size="md"
              >
                <IconMicrophone size={16} />
              </ThemeIcon>
            </Group>
          </Card.Section>
          <Stack gap="xs" mt="md">
            <Group justify="space-between">
              <Badge
                color={status.voice_listening ? "teal" : "gray"}
                variant="light"
                size="sm"
              >
                {status.voice_listening ? "Active" : "Inactive"}
              </Badge>
              <Switch
                checked={status.voice_listening}
                onChange={(event: ChangeEvent<HTMLInputElement>) =>
                  handleVoiceToggle(event.currentTarget.checked)
                }
                disabled={togglingVoice}
                size="md"
                color="teal"
              />
            </Group>
          </Stack>
        </Card>
      </SimpleGrid>

      <Card withBorder padding="lg" radius="md">
        <Card.Section withBorder inheritPadding py="xs">
          <Group justify="space-between">
            <Text fw={500} size="sm" c="dimmed">
              System Info
            </Text>
            <ThemeIcon variant="light" color="gray" size="md">
              <IconInfoCircle size={16} />
            </ThemeIcon>
          </Group>
        </Card.Section>
        <SimpleGrid cols={{ base: 1, sm: 3 }} mt="md" spacing="md">
          <Stack gap={2}>
            <Text size="xs" c="dimmed" tt="uppercase" fw={500}>
              Name
            </Text>
            <Text fw={600}>{status.name}</Text>
          </Stack>
          <Stack gap={2}>
            <Text size="xs" c="dimmed" tt="uppercase" fw={500}>
              Version
            </Text>
            <Text fw={600}>{status.version}</Text>
          </Stack>
          <Stack gap={2}>
            <Text size="xs" c="dimmed" tt="uppercase" fw={500}>
              Language
            </Text>
            <Text fw={600}>
              {config?.general?.language_default ?? "---"}
            </Text>
          </Stack>
        </SimpleGrid>
      </Card>

      <ToolAuditCard />
    </Stack>
  );
}
