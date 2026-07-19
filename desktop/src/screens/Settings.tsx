import { useState } from "react";
import { SettingsIcon } from "../components/icons";
import { McpServers } from "../components/McpServers";
import { Spinner, Tabs, type TabItem } from "../design/primitives";
import { useConfig } from "../hooks/useConfig";
import { useTheme } from "../lib/useTheme";
import { GeneralTab } from "./settings/GeneralTab";
import { LLMTab } from "./settings/LLMTab";
import { MemoryTab } from "./settings/MemoryTab";
import {
  ServerTab,
  TelegramTab,
  WhatsAppTab,
} from "./settings/ChannelsTab";
import { DesktopTab } from "./settings/DesktopTab";
import { ToolsTab } from "./settings/ToolsTab";
import { VoiceStatus } from "./settings/VoiceStatus";
import { VoiceTab } from "./settings/VoiceTab";
import p from "./page.module.css";

type TabId =
  | "general"
  | "llm"
  | "voice"
  | "tools"
  | "mcp"
  | "memory"
  | "telegram"
  | "whatsapp"
  | "server"
  | "desktop";

const TABS: TabItem<TabId>[] = [
  { id: "general", label: "General" },
  { id: "llm", label: "LLM" },
  { id: "voice", label: "Voice" },
  { id: "tools", label: "Tools" },
  { id: "mcp", label: "MCP" },
  { id: "memory", label: "Memory" },
  { id: "telegram", label: "Telegram" },
  { id: "whatsapp", label: "WhatsApp" },
  { id: "server", label: "Server" },
  { id: "desktop", label: "Desktop" },
];

export function Settings() {
  const { config, loading, refresh } = useConfig();
  const { mode, setMode } = useTheme();
  const [tab, setTab] = useState<TabId>("general");

  return (
    <div className={p.scrollPage}>
      <div className={p.page}>
        <div className={p.pageHead}>
          <div className={p.pageMark}>
            <SettingsIcon size={19} />
          </div>
          <div>
            <h1 className={p.pageTitle}>Settings</h1>
            <p className={p.pageSubtitle}>Everything the backend exposes, in one place</p>
          </div>
        </div>

        <Tabs items={TABS} value={tab} onChange={setTab} />

        {loading || !config ? (
          <Spinner size={18} />
        ) : tab === "general" ? (
          <GeneralTab config={config} onSaved={refresh} />
        ) : tab === "llm" ? (
          <LLMTab config={config} onSaved={refresh} />
        ) : tab === "voice" ? (
          <div className={p.rows}>
            <VoiceStatus config={config} />
            <VoiceTab config={config} onSaved={refresh} />
          </div>
        ) : tab === "tools" ? (
          <ToolsTab config={config} onSaved={refresh} />
        ) : tab === "mcp" ? (
          <McpServers config={config} onSaved={refresh} />
        ) : tab === "memory" ? (
          <MemoryTab />
        ) : tab === "telegram" ? (
          <TelegramTab config={config} onSaved={refresh} />
        ) : tab === "whatsapp" ? (
          <WhatsAppTab config={config} onSaved={refresh} />
        ) : tab === "server" ? (
          <ServerTab config={config} onSaved={refresh} />
        ) : (
          <DesktopTab themeMode={mode} onThemeChange={setMode} />
        )}
      </div>
    </div>
  );
}
