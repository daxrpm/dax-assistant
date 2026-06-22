import { useEffect, useState } from "react";
import {
  Cpu,
  Server,
  Wrench,
  Mic,
  Activity,
  CheckCircle2,
  XCircle,
} from "lucide-react";
import { useStatus } from "../hooks/useConfig";
import { api, type MCPServerStatus, type ToolAuditEntry } from "../api/client";
import { Panel, PanelHeader, Badge } from "../components/ui";
import { cn } from "../lib/cn";

export function DashboardPage() {
  const { status } = useStatus();
  const [mcp, setMcp] = useState<MCPServerStatus[]>([]);
  const [audit, setAudit] = useState<ToolAuditEntry[]>([]);

  useEffect(() => {
    api.getMCPStatus().then(setMcp).catch(() => setMcp([]));
    api.getToolAudit(20).then(setAudit).catch(() => setAudit([]));
  }, []);

  const totalTools = mcp.reduce((n, s) => n + s.tool_count, 0);

  return (
    <div className="h-full overflow-y-auto scroll-slim p-6">
      <div className="mx-auto flex max-w-5xl flex-col gap-6">
        {/* Stat cards */}
        <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
          <Stat
            icon={<Activity size={18} />}
            label="Status"
            value={status?.status ?? "—"}
            tone="success"
          />
          <Stat
            icon={<Cpu size={18} />}
            label="LLM provider"
            value={status?.llm_provider ?? "—"}
          />
          <Stat
            icon={<Server size={18} />}
            label="MCP servers"
            value={String(status?.mcp_servers ?? mcp.length)}
          />
          <Stat icon={<Wrench size={18} />} label="Tools" value={String(totalTools)} />
        </div>

        <div className="grid gap-6 lg:grid-cols-2">
          {/* MCP servers */}
          <Panel>
            <PanelHeader title="MCP servers" description="Connected tool providers" />
            <div className="flex flex-col gap-2">
              {mcp.length === 0 && (
                <p className="text-sm text-muted">No MCP servers configured.</p>
              )}
              {mcp.map((s) => (
                <div
                  key={s.name}
                  className="flex items-center justify-between rounded-xl border border-separator bg-background px-3 py-2.5"
                >
                  <div className="flex items-center gap-2">
                    {s.connected ? (
                      <CheckCircle2 size={16} className="text-success" />
                    ) : (
                      <XCircle size={16} className="text-danger" />
                    )}
                    <span className="text-sm font-medium">{s.name}</span>
                    <Badge>{s.transport}</Badge>
                  </div>
                  <Badge color={s.connected ? "success" : "danger"}>
                    {s.tool_count} tools
                  </Badge>
                </div>
              ))}
            </div>
          </Panel>

          {/* Voice */}
          <Panel>
            <PanelHeader title="Voice" description="Wake-word pipeline" />
            <div className="flex items-center gap-3">
              <div
                className={cn(
                  "flex h-10 w-10 items-center justify-center rounded-xl",
                  status?.voice_listening
                    ? "bg-success-soft text-success"
                    : "bg-surface-secondary text-muted",
                )}
              >
                <Mic size={18} />
              </div>
              <div>
                <p className="text-sm font-medium">
                  {status?.voice_listening ? "Listening" : "Idle"}
                </p>
                <p className="text-xs text-muted">
                  {status?.voice_listening
                    ? "Wake word detection active"
                    : "Voice not listening"}
                </p>
              </div>
            </div>
          </Panel>
        </div>

        {/* Tool audit */}
        <Panel>
          <PanelHeader
            title="Recent tool activity"
            description="Audit log of gated and executed tools"
          />
          {audit.length === 0 ? (
            <p className="text-sm text-muted">No tool activity yet.</p>
          ) : (
            <div className="flex flex-col divide-y divide-separator">
              {audit.map((a, i) => (
                <div key={i} className="flex items-center justify-between gap-3 py-2.5">
                  <div className="flex min-w-0 items-center gap-2">
                    <Badge color="accent">{a.server_name}</Badge>
                    <span className="truncate text-sm font-medium">{a.tool_name}</span>
                  </div>
                  <div className="flex shrink-0 items-center gap-3">
                    <AuditBadge status={a.status} />
                    <span className="text-xs text-muted">
                      {new Date(a.timestamp).toLocaleTimeString()}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </Panel>
      </div>
    </div>
  );
}

function Stat({
  icon,
  label,
  value,
  tone,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  tone?: "success";
}) {
  return (
    <Panel className="p-4">
      <div className="flex items-center gap-2 text-muted">
        {icon}
        <span className="text-xs font-medium uppercase tracking-wide">{label}</span>
      </div>
      <p
        className={cn(
          "mt-2 truncate text-xl font-semibold capitalize",
          tone === "success" && "text-success",
        )}
      >
        {value}
      </p>
    </Panel>
  );
}

function AuditBadge({ status }: { status: string }) {
  const color =
    status === "approved" || status === "executed"
      ? "success"
      : status === "denied"
        ? "danger"
        : "default";
  return <Badge color={color}>{status}</Badge>;
}
