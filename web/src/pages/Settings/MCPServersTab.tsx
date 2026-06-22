import { useEffect, useState } from "react";
import {
  Accordion,
  ActionIcon,
  Badge,
  Button,
  Card,
  Chip,
  Code,
  Divider,
  Group,
  Modal,
  PasswordInput,
  SegmentedControl,
  SimpleGrid,
  Stack,
  Text,
  TextInput,
  Title,
} from "@mantine/core";
import { useDisclosure } from "@mantine/hooks";
import { notifications } from "@mantine/notifications";
import {
  IconCheck,
  IconKey,
  IconLock,
  IconPlus,
  IconSearch,
  IconTerminal2,
  IconTrash,
  IconWorld,
} from "@tabler/icons-react";
import { api } from "../../api/client";
import type { MCPServerConfig } from "../../types/config";
import {
  MCP_CATALOG,
  CATEGORY_LABELS,
  type McpCatalogEntry,
  type McpServerInstall,
  type McpCategory,
  type McpEnvVar,
} from "../../data/mcp-catalog";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const AUTH_BADGE_COLOR: Record<string, string> = {
  none: "green",
  api_key: "yellow",
  oauth: "orange",
  token: "yellow",
  connection_string: "yellow",
};

const AUTH_LABEL: Record<string, string> = {
  none: "No auth",
  api_key: "API Key",
  oauth: "OAuth",
  token: "Token",
  connection_string: "Connection",
};

const RUNTIME_COMMAND: Record<string, string> = {
  npx: "npx",
  uvx: "uvx",
  docker: "docker",
  node: "node",
  python: "python",
  url: "",
};

const ALL_CATEGORIES = "all";

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface MCPServersTabProps {
  servers: Record<string, MCPServerConfig> | null;
  onChanged: () => void;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function buildInstallLabel(install: McpServerInstall): string {
  if (install.transport === "streamable-http" || install.transport === "sse") {
    return `Remote (${install.transport})`;
  }
  return `${install.runtimeHint} (${install.transport})`;
}

function buildServerPayload(
  entry: McpCatalogEntry,
  install: McpServerInstall,
  envValues: Record<string, string>,
  urlOverride?: string,
  argsOverride?: string,
): Record<string, unknown> {
  const isRemote =
    install.transport === "streamable-http" || install.transport === "sse";

  if (isRemote) {
    return {
      name: entry.id,
      command: "",
      args: [],
      env: {},
      transport: "streamable_http",
      url: urlOverride || install.identifier,
      enabled: true,
    };
  }

  const command = RUNTIME_COMMAND[install.runtimeHint] ?? install.runtimeHint;
  const args: string[] = [];

  if (install.runtimeHint === "npx") {
    args.push("-y", install.identifier);
  } else if (install.runtimeHint === "uvx") {
    args.push(install.identifier);
  } else if (install.runtimeHint === "docker") {
    args.push("run", "-i", "--rm", install.identifier);
  } else if (
    install.runtimeHint === "node" ||
    install.runtimeHint === "python"
  ) {
    args.push(...(install.args ?? [install.identifier]));
  }

  // Use override args if provided, otherwise use catalog defaults
  if (argsOverride && argsOverride.trim()) {
    const overrideArgs = argsOverride.trim().split(/\s+/);
    for (const arg of overrideArgs) {
      if (!args.includes(arg)) {
        args.push(arg);
      }
    }
  } else if (install.args) {
    for (const arg of install.args) {
      if (!args.includes(arg)) {
        args.push(arg);
      }
    }
  }

  const env: Record<string, string> = {};
  for (const v of install.envVars) {
    if (envValues[v.name] !== undefined && envValues[v.name] !== "") {
      env[v.name] = envValues[v.name];
    }
  }

  return {
    name: entry.id,
    command,
    args,
    env,
    transport: "stdio",
    url: "",
    enabled: true,
  };
}

function getCategories(): McpCategory[] {
  const seen = new Set<McpCategory>();
  for (const entry of MCP_CATALOG) {
    seen.add(entry.category);
  }
  return Array.from(seen);
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function InstalledServerCard({
  name,
  server,
  isDeleting,
  onDelete,
}: {
  name: string;
  server: MCPServerConfig;
  isDeleting: boolean;
  onDelete: () => void;
}) {
  const isHttp = server.transport === "streamable_http" || !!server.url;
  const envKeys = Object.keys(server.env);

  const [authStatus, setAuthStatus] = useState<{
    authenticated: boolean;
    expired?: boolean;
  } | null>(null);
  const [authLoading, setAuthLoading] = useState(false);

  // Check auth status for HTTP servers on mount
  useEffect(() => {
    if (isHttp) {
      api.getMCPAuthStatus(name).then(setAuthStatus).catch(() => {});
    }
  }, [isHttp, name]);

  const handleAuth = async () => {
    setAuthLoading(true);
    try {
      const { authorization_url } = await api.startMCPAuth(name);
      // Open auth page in new tab
      const authWindow = window.open(authorization_url, "_blank");
      // Poll for completion
      const pollInterval = setInterval(async () => {
        try {
          const status = await api.getMCPAuthStatus(name);
          if (status.authenticated) {
            clearInterval(pollInterval);
            setAuthStatus(status);
            setAuthLoading(false);
            if (authWindow && !authWindow.closed) {
              authWindow.close();
            }
            // Auto-reconnect the MCP server with new tokens
            try {
              const result = await api.reconnectMCPServer(name);
              notifications.show({
                title: "Connected",
                message: `${name} authenticated and connected (${result.tools} tools)`,
                color: "green",
              });
            } catch {
              notifications.show({
                title: "Authenticated",
                message: `${name} authenticated. Restart Dax to connect.`,
                color: "yellow",
              });
            }
          }
        } catch {
          // Keep polling
        }
      }, 2000);
      // Stop polling after 2 minutes
      setTimeout(() => {
        clearInterval(pollInterval);
        setAuthLoading(false);
      }, 120_000);
    } catch (e) {
      setAuthLoading(false);
      notifications.show({
        title: "Auth failed",
        message: e instanceof Error ? e.message : "Could not start OAuth flow",
        color: "red",
      });
    }
  };

  const handleLogout = async () => {
    await api.logoutMCP(name);
    setAuthStatus({ authenticated: false });
    notifications.show({
      title: "Logged out",
      message: `${name} credentials removed`,
      color: "yellow",
    });
  };

  return (
    <Card withBorder padding="md">
      <Group justify="space-between" mb="xs">
        <Group gap="xs">
          <Text fw={600}>{name}</Text>
          <Badge
            color={isHttp ? "blue" : "violet"}
            variant="light"
            size="xs"
            leftSection={
              isHttp ? (
                <IconWorld size={10} />
              ) : (
                <IconTerminal2 size={10} />
              )
            }
          >
            {isHttp ? "http" : "stdio"}
          </Badge>
          <Badge
            color={server.enabled ? "green" : "gray"}
            variant="light"
            size="xs"
          >
            {server.enabled ? "Enabled" : "Disabled"}
          </Badge>
          {isHttp && authStatus?.authenticated && (
            <Badge color="green" variant="light" size="xs" leftSection={<IconCheck size={10} />}>
              Authenticated
            </Badge>
          )}
          {isHttp && authStatus && !authStatus.authenticated && (
            <Badge color="orange" variant="light" size="xs" leftSection={<IconLock size={10} />}>
              Not authenticated
            </Badge>
          )}
        </Group>
        <ActionIcon
          color="red"
          variant="subtle"
          loading={isDeleting}
          onClick={onDelete}
          aria-label={`Delete ${name}`}
        >
          <IconTrash size={16} />
        </ActionIcon>
      </Group>

      <Stack gap={4}>
        {server.command && (
          <Text size="sm">
            <Text span fw={500}>Command:</Text>{" "}
            <Code>{server.command}</Code>
          </Text>
        )}

        {server.args.length > 0 && (
          <Text size="sm">
            <Text span fw={500}>Args:</Text>{" "}
            <Code>{server.args.join(" ")}</Code>
          </Text>
        )}

        {server.url && (
          <Text size="sm">
            <Text span fw={500}>URL:</Text>{" "}
            <Code>{server.url}</Code>
          </Text>
        )}

        {envKeys.length > 0 && (
          <div>
            <Text size="sm" fw={500}>Environment:</Text>
            {envKeys.map((k) => (
              <Text key={k} size="xs" c="dimmed" ml="sm">
                {k}={"*".repeat(8)}
              </Text>
            ))}
          </div>
        )}
      </Stack>

      {isHttp && (
        <Group mt="sm" gap="xs">
          {authStatus?.authenticated ? (
            <Button
              size="xs"
              variant="subtle"
              color="yellow"
              leftSection={<IconLock size={14} />}
              onClick={handleLogout}
            >
              Logout
            </Button>
          ) : (
            <Button
              size="xs"
              variant="light"
              color="blue"
              leftSection={<IconKey size={14} />}
              loading={authLoading}
              onClick={handleAuth}
            >
              Authenticate
            </Button>
          )}
        </Group>
      )}
    </Card>
  );
}

function CatalogCard({
  entry,
  onAdd,
}: {
  entry: McpCatalogEntry;
  onAdd: () => void;
}) {
  return (
    <Card withBorder padding="md" h="100%">
      <Stack justify="space-between" h="100%" gap="sm">
        <Stack gap="xs">
          <Group justify="space-between" align="flex-start">
            <Text fw={700} size="md" lineClamp={1}>
              {entry.name}
            </Text>
            <Group gap={4} wrap="nowrap">
              {entry.isOfficial && (
                <Badge
                  color="blue"
                  variant="filled"
                  size="xs"
                  leftSection={<IconCheck size={10} />}
                >
                  Official
                </Badge>
              )}
            </Group>
          </Group>

          <Text size="sm" c="dimmed" lineClamp={2}>
            {entry.description}
          </Text>

          <Group gap={4}>
            <Badge variant="light" size="xs">
              {CATEGORY_LABELS[entry.category]}
            </Badge>
            <Badge
              color={AUTH_BADGE_COLOR[entry.authType] ?? "gray"}
              variant="light"
              size="xs"
              leftSection={
                entry.authType === "none" ? (
                  <IconCheck size={10} />
                ) : (
                  <IconKey size={10} />
                )
              }
            >
              {AUTH_LABEL[entry.authType] ?? entry.authType}
            </Badge>
          </Group>

          {entry.capabilities && entry.capabilities.length > 0 && (
            <Group gap={4} mt={4}>
              {entry.capabilities.slice(0, 3).map((cap) => (
                <Badge key={cap} variant="outline" size="xs" color="gray">
                  {cap}
                </Badge>
              ))}
              {entry.capabilities.length > 3 && (
                <Text size="xs" c="dimmed">
                  +{entry.capabilities.length - 3} more
                </Text>
              )}
            </Group>
          )}
        </Stack>

        <Button
          variant="light"
          size="xs"
          leftSection={<IconPlus size={14} />}
          onClick={onAdd}
          fullWidth
        >
          Add
        </Button>
      </Stack>
    </Card>
  );
}

function EnvVarField({
  envVar,
  value,
  onChange,
}: {
  envVar: McpEnvVar;
  value: string;
  onChange: (val: string) => void;
}) {
  const label = `${envVar.name}${envVar.isRequired ? " *" : ""}`;
  const description = envVar.description;

  if (envVar.isSecret) {
    return (
      <PasswordInput
        label={label}
        description={description}
        placeholder={envVar.placeholder ?? ""}
        value={value}
        onChange={(e) => onChange(e.currentTarget.value)}
        leftSection={<IconLock size={16} />}
      />
    );
  }

  return (
    <TextInput
      label={label}
      description={description}
      placeholder={envVar.placeholder ?? ""}
      value={value}
      onChange={(e) => onChange(e.currentTarget.value)}
    />
  );
}

function AddServerModal({
  entry,
  opened,
  onClose,
  onAdded,
}: {
  entry: McpCatalogEntry | null;
  opened: boolean;
  onClose: () => void;
  onAdded: () => void;
}) {
  const [selectedInstallIndex, setSelectedInstallIndex] = useState(0);
  const [envValues, setEnvValues] = useState<Record<string, string>>({});
  const [argsOverride, setArgsOverride] = useState("");
  const [urlOverride, setUrlOverride] = useState("");
  const [submitting, setSubmitting] = useState(false);

  if (!entry) return null;

  const hasMultipleInstalls = entry.installs.length > 1;
  const install = entry.installs[selectedInstallIndex] ?? entry.installs[0];

  // Initialize overrides from catalog defaults when install changes
  if (
    urlOverride === "" &&
    install.transport !== "stdio" &&
    install.identifier
  ) {
    setUrlOverride(install.identifier);
  }
  if (argsOverride === "" && install.args && install.args.length > 0) {
    setArgsOverride(install.args.join(" "));
  }
  const isRemote =
    install.transport === "streamable-http" || install.transport === "sse";

  const requiredEnvVars = install.envVars.filter((v) => v.isRequired);
  const optionalEnvVars = install.envVars.filter((v) => !v.isRequired);

  const updateEnvValue = (name: string, value: string) => {
    setEnvValues((prev) => ({ ...prev, [name]: value }));
  };

  const handleInstallChange = (value: string) => {
    setSelectedInstallIndex(Number(value));
    setEnvValues({});
  };

  const canSubmit = requiredEnvVars.every(
    (v) => envValues[v.name] !== undefined && envValues[v.name] !== "",
  );

  const handleSubmit = async () => {
    if (!canSubmit) return;

    setSubmitting(true);
    try {
      const payload = buildServerPayload(
        entry, install, envValues, urlOverride, argsOverride,
      );
      await api.addMCPServer(payload);

      notifications.show({
        title: "Server added",
        message: `${entry.name} has been configured successfully`,
        color: "green",
      });

      handleClose();
      onAdded();
    } catch (e) {
      notifications.show({
        title: "Error",
        message: e instanceof Error ? e.message : "Failed to add server",
        color: "red",
      });
    } finally {
      setSubmitting(false);
    }
  };

  const handleClose = () => {
    setSelectedInstallIndex(0);
    setEnvValues({});
    onClose();
  };

  return (
    <Modal
      opened={opened}
      onClose={handleClose}
      title={`Add ${entry.name}`}
      size="lg"
    >
      <Stack gap="md">
        {hasMultipleInstalls && (
          <div>
            <Text size="sm" fw={500} mb={4}>
              Installation method
            </Text>
            <SegmentedControl
              fullWidth
              value={String(selectedInstallIndex)}
              onChange={handleInstallChange}
              data={entry.installs.map((inst, i) => ({
                value: String(i),
                label: buildInstallLabel(inst),
              }))}
            />
          </div>
        )}

        {isRemote ? (
          <TextInput
            label="URL"
            value={urlOverride}
            onChange={(e) => setUrlOverride(e.currentTarget.value)}
            leftSection={<IconWorld size={16} />}
            description="Remote MCP endpoint"
          />
        ) : (
          <>
            <TextInput
              label="Command"
              value={
                RUNTIME_COMMAND[install.runtimeHint] ?? install.runtimeHint
              }
              readOnly
              leftSection={<IconTerminal2 size={16} />}
              description="Runtime command (auto-detected)"
            />
            <TextInput
              label="Package / identifier"
              value={install.identifier}
              readOnly
              description="Package name from catalog"
            />
            <TextInput
              label="Arguments"
              value={argsOverride}
              onChange={(e) => setArgsOverride(e.currentTarget.value)}
              placeholder="Additional arguments (e.g., /home/user/Documents)"
              description="Edit to customize paths or options"
            />
          </>
        )}

        {requiredEnvVars.length > 0 && (
          <>
            <Divider
              label="Required credentials"
              labelPosition="center"
              mt="xs"
            />
            {requiredEnvVars.map((v) => (
              <EnvVarField
                key={v.name}
                envVar={v}
                value={envValues[v.name] ?? ""}
                onChange={(val) => updateEnvValue(v.name, val)}
              />
            ))}
            <Text size="xs" c="dimmed">
              Tip: Use{" "}
              <Code>{"{env:VAR_NAME}"}</Code> syntax to reference
              existing environment variables instead of pasting raw secrets.
            </Text>
          </>
        )}

        {optionalEnvVars.length > 0 && (
          <Accordion variant="contained">
            <Accordion.Item value="optional">
              <Accordion.Control>
                <Text size="sm">
                  Optional settings ({optionalEnvVars.length})
                </Text>
              </Accordion.Control>
              <Accordion.Panel>
                <Stack gap="sm">
                  {optionalEnvVars.map((v) => (
                    <EnvVarField
                      key={v.name}
                      envVar={v}
                      value={envValues[v.name] ?? ""}
                      onChange={(val) => updateEnvValue(v.name, val)}
                    />
                  ))}
                </Stack>
              </Accordion.Panel>
            </Accordion.Item>
          </Accordion>
        )}

        {entry.authSetupUrl && (
          <Text size="xs" c="dimmed">
            Need credentials?{" "}
            <Text
              component="a"
              href={entry.authSetupUrl}
              target="_blank"
              rel="noopener noreferrer"
              size="xs"
              c="blue"
              td="underline"
            >
              Setup guide
            </Text>
          </Text>
        )}

        <Group justify="flex-end" mt="sm">
          <Button variant="subtle" onClick={handleClose}>
            Cancel
          </Button>
          <Button
            onClick={handleSubmit}
            loading={submitting}
            disabled={!canSubmit && requiredEnvVars.length > 0}
            leftSection={<IconPlus size={16} />}
          >
            Add Server
          </Button>
        </Group>
      </Stack>
    </Modal>
  );
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export function MCPServersTab({ servers, onChanged }: MCPServersTabProps) {
  const [deleting, setDeleting] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [categoryFilter, setCategoryFilter] = useState(ALL_CATEGORIES);
  const [selectedEntry, setSelectedEntry] = useState<McpCatalogEntry | null>(
    null,
  );
  const [modalOpened, { open: openModal, close: closeModal }] =
    useDisclosure(false);

  // -- Installed servers --
  const serverEntries = servers ? Object.entries(servers) : [];

  const handleDelete = async (name: string) => {
    setDeleting(name);
    try {
      await api.deleteMCPServer(name);
      notifications.show({
        title: "Deleted",
        message: `MCP server "${name}" removed`,
        color: "green",
      });
      onChanged();
    } catch (e) {
      notifications.show({
        title: "Error",
        message: e instanceof Error ? e.message : "Failed to delete server",
        color: "red",
      });
    } finally {
      setDeleting(null);
    }
  };

  // -- Catalog filtering --
  const query = search.toLowerCase().trim();

  const filteredCatalog = MCP_CATALOG.filter((entry) => {
    const matchesCategory =
      categoryFilter === ALL_CATEGORIES || entry.category === categoryFilter;

    const matchesSearch =
      query === "" ||
      entry.name.toLowerCase().includes(query) ||
      entry.description.toLowerCase().includes(query) ||
      entry.tags.some((tag) => tag.includes(query));

    return matchesCategory && matchesSearch;
  });

  const categories = getCategories();

  const handleAddClick = (entry: McpCatalogEntry) => {
    setSelectedEntry(entry);
    openModal();
  };

  const handleModalClose = () => {
    closeModal();
    setSelectedEntry(null);
  };

  return (
    <Stack gap="lg">
      {/* ── Section A: Installed Servers ────────────────────────────── */}
      <div>
        <Group justify="space-between" mb="sm">
          <Title order={4}>Installed Servers</Title>
          <Text size="sm" c="dimmed">
            {serverEntries.length} configured
          </Text>
        </Group>

        {serverEntries.length === 0 ? (
          <Text c="dimmed" ta="center" py="md" size="sm">
            No MCP servers installed yet. Browse the catalog below to get
            started.
          </Text>
        ) : (
          <SimpleGrid cols={{ base: 1, sm: 2 }} spacing="md">
            {serverEntries.map(([name, server]) => (
              <InstalledServerCard
                key={name}
                name={name}
                server={server}
                isDeleting={deleting === name}
                onDelete={() => handleDelete(name)}
              />
            ))}
          </SimpleGrid>
        )}
      </div>

      <Divider />

      {/* ── Section B: Server Catalog ───────────────────────────────── */}
      <div>
        <Title order={4} mb="sm">
          Server Catalog
        </Title>

        <Stack gap="sm" mb="md">
          <TextInput
            placeholder="Search servers..."
            leftSection={<IconSearch size={16} />}
            value={search}
            onChange={(e) => setSearch(e.currentTarget.value)}
          />

          <Chip.Group
            multiple={false}
            value={categoryFilter}
            onChange={(val) => setCategoryFilter(val as string)}
          >
            <Group gap={6}>
              <Chip value={ALL_CATEGORIES} size="xs" variant="outline">
                All
              </Chip>
              {categories.map((cat) => (
                <Chip key={cat} value={cat} size="xs" variant="outline">
                  {CATEGORY_LABELS[cat]}
                </Chip>
              ))}
            </Group>
          </Chip.Group>
        </Stack>

        {filteredCatalog.length === 0 ? (
          <Text c="dimmed" ta="center" py="xl" size="sm">
            No servers match your search.
          </Text>
        ) : (
          <SimpleGrid cols={{ base: 1, sm: 2, md: 3 }} spacing="md">
            {filteredCatalog.map((entry) => (
              <CatalogCard
                key={entry.id}
                entry={entry}
                onAdd={() => handleAddClick(entry)}
              />
            ))}
          </SimpleGrid>
        )}
      </div>

      {/* ── Add Server Modal ────────────────────────────────────────── */}
      <AddServerModal
        entry={selectedEntry}
        opened={modalOpened}
        onClose={handleModalClose}
        onAdded={onChanged}
      />
    </Stack>
  );
}
