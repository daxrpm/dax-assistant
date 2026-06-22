import { useState } from "react";
import {
  AppShell,
  Burger,
  Group,
  NavLink,
  Text,
  ThemeIcon,
  Title,
  useMantineColorScheme,
  ActionIcon,
} from "@mantine/core";
import {
  IconDashboard,
  IconMessageCircle,
  IconSettings,
  IconSun,
  IconMoon,
  IconLogout,
} from "@tabler/icons-react";
import { useLocation, useNavigate, Outlet } from "react-router";

import { api } from "../api/client";

const NAV_ITEMS = [
  { label: "Dashboard", icon: IconDashboard, path: "/" },
  { label: "Chat", icon: IconMessageCircle, path: "/chat" },
  { label: "Settings", icon: IconSettings, path: "/settings" },
] as const;

export function AppLayout() {
  const [opened, setOpened] = useState(false);
  const location = useLocation();
  const navigate = useNavigate();
  const { colorScheme, toggleColorScheme } = useMantineColorScheme();

  return (
    <AppShell
      padding="md"
      header={{ height: 56 }}
      navbar={{
        width: 240,
        breakpoint: "sm",
        collapsed: { mobile: !opened },
      }}
    >
      <AppShell.Header>
        <Group h="100%" px="md" justify="space-between">
          <Group>
            <Burger
              opened={opened}
              onClick={() => setOpened((o) => !o)}
              hiddenFrom="sm"
              size="sm"
            />
            <Title order={4} fw={600}>
              Dax
            </Title>
            <Text size="xs" c="dimmed">
              Assistant
            </Text>
          </Group>
          <Group gap="xs">
            <ActionIcon
              variant="subtle"
              size="lg"
              onClick={toggleColorScheme}
              aria-label="Toggle color scheme"
            >
              {colorScheme === "dark" ? (
                <IconSun size={18} />
              ) : (
                <IconMoon size={18} />
              )}
            </ActionIcon>
            <ActionIcon
              variant="subtle"
              size="lg"
              color="red"
              onClick={async () => {
                await api.logout();
                window.location.reload();
              }}
              aria-label="Sign out"
            >
              <IconLogout size={18} />
            </ActionIcon>
          </Group>
        </Group>
      </AppShell.Header>

      <AppShell.Navbar p="xs">
        {NAV_ITEMS.map((item) => (
          <NavLink
            key={item.path}
            label={item.label}
            leftSection={
              <ThemeIcon variant="light" size="sm">
                <item.icon size={14} />
              </ThemeIcon>
            }
            active={
              item.path === "/"
                ? location.pathname === "/"
                : location.pathname.startsWith(item.path)
            }
            onClick={() => {
              navigate(item.path);
              setOpened(false);
            }}
          />
        ))}
      </AppShell.Navbar>

      <AppShell.Main>
        <Outlet />
      </AppShell.Main>
    </AppShell>
  );
}
