import { Container, Loader, Stack, Tabs, Text, Title } from "@mantine/core";
import {
  IconAdjustments,
  IconBrain,
  IconBrandWhatsapp,
  IconMicrophone,
  IconServer,
} from "@tabler/icons-react";
import { useConfig } from "../../hooks/useConfig";
import { GeneralTab } from "./GeneralTab";
import { LLMTab } from "./LLMTab";
import { VoiceTab } from "./VoiceTab";
import { WhatsAppTab } from "./WhatsAppTab";
import { MCPServersTab } from "./MCPServersTab";

const TAB = {
  GENERAL: "general",
  LLM: "llm",
  VOICE: "voice",
  WHATSAPP: "whatsapp",
  MCP: "mcp",
} as const;

export function SettingsPage() {
  const { config, loading, error, refresh } = useConfig();

  if (loading && !config) {
    return (
      <Container size="md" py="xl">
        <Stack align="center" gap="md">
          <Loader />
          <Text c="dimmed">Loading settings...</Text>
        </Stack>
      </Container>
    );
  }

  if (error) {
    return (
      <Container size="md" py="xl">
        <Text c="red">{error}</Text>
      </Container>
    );
  }

  return (
    <Container size="md" py="xl">
      <Title order={2} mb="lg">
        Settings
      </Title>

      <Tabs defaultValue={TAB.GENERAL} keepMounted={false}>
        <Tabs.List mb="lg">
          <Tabs.Tab
            value={TAB.GENERAL}
            leftSection={<IconAdjustments size={16} />}
          >
            General
          </Tabs.Tab>
          <Tabs.Tab value={TAB.LLM} leftSection={<IconBrain size={16} />}>
            LLM
          </Tabs.Tab>
          <Tabs.Tab
            value={TAB.VOICE}
            leftSection={<IconMicrophone size={16} />}
          >
            Voice
          </Tabs.Tab>
          <Tabs.Tab
            value={TAB.WHATSAPP}
            leftSection={<IconBrandWhatsapp size={16} />}
          >
            WhatsApp
          </Tabs.Tab>
          <Tabs.Tab value={TAB.MCP} leftSection={<IconServer size={16} />}>
            MCP Servers
          </Tabs.Tab>
        </Tabs.List>

        <Tabs.Panel value={TAB.GENERAL}>
          <GeneralTab data={config?.general ?? null} onSaved={refresh} />
        </Tabs.Panel>

        <Tabs.Panel value={TAB.LLM}>
          <LLMTab data={config?.llm ?? null} onSaved={refresh} />
        </Tabs.Panel>

        <Tabs.Panel value={TAB.VOICE}>
          <VoiceTab data={config?.voice ?? null} onSaved={refresh} />
        </Tabs.Panel>

        <Tabs.Panel value={TAB.WHATSAPP}>
          <WhatsAppTab data={config?.whatsapp ?? null} onSaved={refresh} />
        </Tabs.Panel>

        <Tabs.Panel value={TAB.MCP}>
          <MCPServersTab
            servers={config?.mcp.servers ?? null}
            onChanged={refresh}
          />
        </Tabs.Panel>
      </Tabs>
    </Container>
  );
}
