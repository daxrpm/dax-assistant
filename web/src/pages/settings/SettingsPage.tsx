import { useState } from "react";
import {
  SlidersHorizontal,
  Cpu,
  Mic,
  MessageCircle,
  ShieldCheck,
  Server,
} from "lucide-react";
import { useConfig } from "../../hooks/useConfig";
import { Tabs } from "../../components/ui";
import { GeneralTab } from "./GeneralTab";
import { LLMTab } from "./LLMTab";
import { VoiceTab } from "./VoiceTab";
import { WhatsAppTab } from "./WhatsAppTab";
import { ToolsTab } from "./ToolsTab";
import { McpTab } from "./McpTab";

const TABS = [
  { id: "general", label: "General", icon: <SlidersHorizontal size={15} /> },
  { id: "llm", label: "LLM", icon: <Cpu size={15} /> },
  { id: "voice", label: "Voice", icon: <Mic size={15} /> },
  { id: "whatsapp", label: "WhatsApp", icon: <MessageCircle size={15} /> },
  { id: "tools", label: "Security & Tools", icon: <ShieldCheck size={15} /> },
  { id: "mcp", label: "MCP Servers", icon: <Server size={15} /> },
];

export function SettingsPage() {
  const { config, loading, refresh } = useConfig();
  const [active, setActive] = useState("general");

  return (
    <div className="h-full overflow-y-auto scroll-slim p-6">
      <div className="mx-auto flex max-w-3xl flex-col gap-5">
        <Tabs tabs={TABS} active={active} onChange={setActive} />

        {loading || !config ? (
          <p className="text-sm text-muted">Loading configuration…</p>
        ) : (
          <>
            {active === "general" && <GeneralTab config={config} onSaved={refresh} />}
            {active === "llm" && <LLMTab config={config} onSaved={refresh} />}
            {active === "voice" && <VoiceTab config={config} onSaved={refresh} />}
            {active === "whatsapp" && <WhatsAppTab config={config} onSaved={refresh} />}
            {active === "tools" && <ToolsTab config={config} onSaved={refresh} />}
            {active === "mcp" && <McpTab config={config} onSaved={refresh} />}
          </>
        )}
      </div>
    </div>
  );
}
