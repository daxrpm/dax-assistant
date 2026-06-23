import { useState } from "react";
import { Button } from "@heroui/react";
import { api } from "../../api/client";
import type { FullConfig } from "../../types/config";
import {
  Panel,
  PanelHeader,
  Field,
  TextInput,
  TextArea,
  Toggle,
  useToast,
} from "../../components/ui";

export function ServerTab({
  config,
  onSaved,
}: {
  config: FullConfig;
  onSaved: () => void;
}) {
  const toast = useToast();
  const w = config.web;
  const [host, setHost] = useState(w.host);
  const [port, setPort] = useState(w.port);
  const [exposeLan, setExposeLan] = useState(w.expose_lan ?? false);
  const [corsOrigins, setCorsOrigins] = useState(w.cors_origins.join("\n"));
  const [saving, setSaving] = useState(false);

  const save = async () => {
    setSaving(true);
    try {
      await api.updateWeb({
        host,
        port: Number(port),
        cors_origins: corsOrigins.split("\n").map((s) => s.trim()).filter(Boolean),
        expose_lan: exposeLan,
      });
      toast.show("Server settings saved — restart to apply host/port changes", "success");
      onSaved();
    } catch (e) {
      toast.show(e instanceof Error ? e.message : "Save failed", "danger");
    } finally {
      setSaving(false);
    }
  };

  return (
    <Panel>
      <PanelHeader
        title="Web server"
        description="Network binding and CORS — requires restart to take effect"
      />
      <div className="flex flex-col gap-4">
        <Field
          label="Host"
          description="127.0.0.1 = localhost only · 0.0.0.0 = all interfaces (use with expose_lan)"
        >
          <TextInput
            value={host}
            onChange={(e) => setHost(e.target.value)}
            placeholder="127.0.0.1"
          />
        </Field>
        <Field label="Port">
          <TextInput
            type="number"
            value={port}
            onChange={(e) => setPort(Number(e.target.value))}
          />
        </Field>
        <div className="flex items-center justify-between rounded-xl border border-separator bg-background px-3 py-2.5">
          <div>
            <p className="text-sm font-medium">Expose on LAN</p>
            <p className="text-xs text-muted">
              Bind to 0.0.0.0 so other devices on the network can reach Dax
            </p>
          </div>
          <Toggle checked={exposeLan} onChange={setExposeLan} label="Expose LAN" />
        </div>
        <Field
          label="CORS origins"
          description="One origin per line. Allows the browser to call the API from these addresses."
        >
          <TextArea
            rows={3}
            value={corsOrigins}
            onChange={(e) => setCorsOrigins(e.target.value)}
            placeholder={"http://localhost:8420\nhttp://192.168.1.100:8420"}
          />
        </Field>
        <div className="flex justify-end">
          <Button variant="primary" onPress={save} isDisabled={saving}>
            {saving ? "Saving…" : "Save"}
          </Button>
        </div>
      </div>
    </Panel>
  );
}
