import { useState, useEffect } from "react";
import {
  Button,
  Group,
  PasswordInput,
  Stack,
  Switch,
  TextInput,
} from "@mantine/core";
import { useForm } from "@mantine/form";
import { notifications } from "@mantine/notifications";
import { api } from "../../api/client";
import type { WhatsAppConfig } from "../../types/config";

interface WhatsAppFormValues {
  enabled: boolean;
  evolution_api_url: string;
  evolution_api_instance: string;
  api_key: string;
  respond_with_audio: boolean;
}

interface WhatsAppTabProps {
  data: WhatsAppConfig | null;
  onSaved: () => void;
}

export function WhatsAppTab({ data, onSaved }: WhatsAppTabProps) {
  const [saving, setSaving] = useState(false);

  const form = useForm<WhatsAppFormValues>({
    initialValues: {
      enabled: false,
      evolution_api_url: "",
      evolution_api_instance: "",
      api_key: "",
      respond_with_audio: false,
    },
  });

  useEffect(() => {
    if (data) {
      form.setValues({
        enabled: data.enabled,
        evolution_api_url: data.evolution_api_url,
        evolution_api_instance: data.evolution_api_instance,
        api_key: "",
        respond_with_audio: data.respond_with_audio,
      });
    }
  }, [data]);

  const handleSubmit = async (values: WhatsAppFormValues) => {
    setSaving(true);
    try {
      const payload: Record<string, unknown> = { ...values };
      if (!values.api_key) {
        delete payload.api_key;
      }
      await api.updateWhatsApp(payload);
      notifications.show({
        title: "Saved",
        message: "WhatsApp settings updated",
        color: "green",
      });
      onSaved();
    } catch (e) {
      notifications.show({
        title: "Error",
        message: e instanceof Error ? e.message : "Failed to save settings",
        color: "red",
      });
    } finally {
      setSaving(false);
    }
  };

  return (
    <form onSubmit={form.onSubmit(handleSubmit)}>
      <Stack gap="md">
        <Switch
          label="Enabled"
          description="Enable WhatsApp integration"
          {...form.getInputProps("enabled", { type: "checkbox" })}
        />
        <TextInput
          label="Evolution API URL"
          placeholder="https://evolution-api.example.com"
          {...form.getInputProps("evolution_api_url")}
        />
        <TextInput
          label="Instance Name"
          placeholder="dax-assistant"
          {...form.getInputProps("evolution_api_instance")}
        />
        <PasswordInput
          label="API Key"
          description={
            data?.has_api_key
              ? "Key is configured. Leave blank to keep current key."
              : "No key configured."
          }
          placeholder="Enter API key"
          {...form.getInputProps("api_key")}
        />
        <Switch
          label="Respond with Audio"
          description="Send voice messages instead of text"
          {...form.getInputProps("respond_with_audio", { type: "checkbox" })}
        />
        <Group justify="flex-end">
          <Button type="submit" loading={saving}>
            Save
          </Button>
        </Group>
      </Stack>
    </form>
  );
}
