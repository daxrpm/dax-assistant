import "@mantine/core/styles.css";
import "@mantine/notifications/styles.css";

import { createTheme, MantineProvider } from "@mantine/core";
import { Notifications } from "@mantine/notifications";
import { BrowserRouter, Routes, Route } from "react-router";

import { AppLayout } from "./components/AppLayout";
import { AuthGate } from "./components/AuthGate";
import { DashboardPage } from "./pages/Dashboard";
import { ChatPage } from "./pages/Chat";
import { SettingsPage } from "./pages/Settings";

const theme = createTheme({
  primaryColor: "indigo",
  defaultRadius: "md",
  fontFamily:
    '-apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, sans-serif',
  cursorType: "pointer",
  autoContrast: true,
  headings: {
    fontWeight: "600",
  },
});

export default function App() {
  return (
    <MantineProvider theme={theme} defaultColorScheme="auto">
      <Notifications position="top-right" />
      <AuthGate>
        <BrowserRouter>
          <Routes>
            <Route element={<AppLayout />}>
              <Route index element={<DashboardPage />} />
              <Route path="chat" element={<ChatPage />} />
              <Route path="settings" element={<SettingsPage />} />
            </Route>
          </Routes>
        </BrowserRouter>
      </AuthGate>
    </MantineProvider>
  );
}
