import { useEffect } from "react";
import { Button, Group, Select, Stack, TextInput } from "@mantine/core";
import { useForm } from "@mantine/form";
import { notifications } from "@mantine/notifications";
import { api } from "../../api/client";
import type { GeneralConfig } from "../../types/config";

const LANGUAGE = {
  ES: "es",
  EN: "en",
  AUTO: "auto",
} as const;

type Language = (typeof LANGUAGE)[keyof typeof LANGUAGE];

const LOG_LEVEL = {
  DEBUG: "DEBUG",
  INFO: "INFO",
  WARNING: "WARNING",
  ERROR: "ERROR",
} as const;

type LogLevel = (typeof LOG_LEVEL)[keyof typeof LOG_LEVEL];

const LANGUAGE_OPTIONS = [
  { value: LANGUAGE.ES, label: "Spanish" },
  { value: LANGUAGE.EN, label: "English" },
  { value: LANGUAGE.AUTO, label: "Auto-detect" },
];

const LOG_LEVEL_OPTIONS = [
  { value: LOG_LEVEL.DEBUG, label: "DEBUG" },
  { value: LOG_LEVEL.INFO, label: "INFO" },
  { value: LOG_LEVEL.WARNING, label: "WARNING" },
  { value: LOG_LEVEL.ERROR, label: "ERROR" },
];

interface GeneralFormValues {
  name: string;
  language_default: Language;
  log_level: LogLevel;
}

interface GeneralTabProps {
  data: GeneralConfig | null;
  onSaved: () => void;
}

export function GeneralTab({ data, onSaved }: GeneralTabProps) {
  const form = useForm<GeneralFormValues>({
    initialValues: {
      name: "",
      language_default: LANGUAGE.AUTO,
      log_level: LOG_LEVEL.INFO,
    },
  });

  useEffect(() => {
    if (data) {
      form.setValues({
        name: data.name,
        language_default: data.language_default as Language,
        log_level: data.log_level as LogLevel,
      });
    }
  }, [data]);

  const handleSubmit = async (values: GeneralFormValues) => {
    try {
      await api.updateGeneral({ ...values });
      notifications.show({
        title: "Saved",
        message: "General settings updated",
        color: "green",
      });
      onSaved();
    } catch (e) {
      notifications.show({
        title: "Error",
        message: e instanceof Error ? e.message : "Failed to save settings",
        color: "red",
      });
    }
  };

  return (
    <form onSubmit={form.onSubmit(handleSubmit)}>
      <Stack gap="md">
        <TextInput
          label="Name"
          description="Assistant display name"
          {...form.getInputProps("name")}
        />
        <Select
          label="Default Language"
          description="Language for responses"
          data={LANGUAGE_OPTIONS}
          {...form.getInputProps("language_default")}
        />
        <Select
          label="Log Level"
          description="Minimum log severity"
          data={LOG_LEVEL_OPTIONS}
          {...form.getInputProps("log_level")}
        />
        <Group justify="flex-end">
          <Button type="submit">Save</Button>
        </Group>
      </Stack>
    </form>
  );
}
