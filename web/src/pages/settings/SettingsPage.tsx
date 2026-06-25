import { useState } from "react";
import {
  SlidersHorizontal,
  Cpu,
  Mic,
  MessageCircle,
  Send,
  ShieldCheck,
  Globe,
  Brain,
} from "lucide-react";
import { useConfig } from "../../hooks/useConfig";
import { Tabs } from "../../components/ui";
import { GeneralTab } from "./GeneralTab";
import { LLMTab } from "./LLMTab";
import { VoiceTab } from "./VoiceTab";
import { WhatsAppTab } from "./WhatsAppTab";
import { TelegramTab } from "./TelegramTab";
import { ToolsTab } from "./ToolsTab";
import { ServerTab } from "./ServerTab";
import { MemoryTab } from "./MemoryTab";

const TABS = [
  { id: "general", label: "General", icon: <SlidersHorizontal size={15} /> },
  { id: "llm", label: "LLM", icon: <Cpu size={15} /> },
  { id: "voice", label: "Voice", icon: <Mic size={15} /> },
  { id: "whatsapp", label: "WhatsApp", icon: <MessageCircle size={15} /> },
  { id: "telegram", label: "Telegram", icon: <Send size={15} /> },
  { id: "tools", label: "Security & Tools", icon: <ShieldCheck size={15} /> },
  { id: "server", label: "Web Server", icon: <Globe size={15} /> },
  { id: "memory", label: "Memory", icon: <Brain size={15} /> },
];

export function SettingsPage({ initialTab = "general" }: { initialTab?: string }) {
  const { config, loading, refresh } = useConfig();
  const [active, setActive] = useState(initialTab);

  return (
    <div className="h-full overflow-y-auto scroll-slim p-6">
      <div className="mx-auto flex max-w-5xl flex-col gap-5">
        <Tabs tabs={TABS} active={active} onChange={setActive} />

        {loading || !config ? (
          <p className="text-sm text-muted">Loading configuration…</p>
        ) : (
          <>
            {active === "general" && <GeneralTab config={config} onSaved={refresh} />}
            {active === "llm" && <LLMTab config={config} onSaved={refresh} />}
            {active === "voice" && <VoiceTab config={config} onSaved={refresh} />}
            {active === "whatsapp" && <WhatsAppTab config={config} onSaved={refresh} />}
            {active === "telegram" && <TelegramTab config={config} onSaved={refresh} />}
            {active === "tools" && <ToolsTab config={config} onSaved={refresh} />}
            {active === "server" && <ServerTab config={config} onSaved={refresh} />}
            {active === "memory" && <MemoryTab config={config} onSaved={refresh} />}
          </>
        )}
      </div>
    </div>
  );
}
