import { BrowserRouter, Routes, Route } from "react-router";
import { ToastProvider } from "./components/ToastProvider";
import { AuthGate } from "./components/AuthGate";
import { AppShell } from "./components/AppShell";
import { ChatPage } from "./pages/Chat";
import { DashboardPage } from "./pages/Dashboard";
import { LogsPage } from "./pages/Logs";
import { McpPage } from "./pages/Mcp";
import { SettingsPage } from "./pages/settings/SettingsPage";

export default function App() {
  return (
    <ToastProvider>
      <AuthGate>
        {(authEnabled) => (
          <BrowserRouter>
            <Routes>
              <Route element={<AppShell authEnabled={authEnabled} />}>
                <Route index element={<ChatPage />} />
                <Route path="dashboard" element={<DashboardPage />} />
                <Route path="mcp" element={<McpPage />} />
                <Route path="logs" element={<LogsPage />} />
                <Route path="settings" element={<SettingsPage />} />
              </Route>
            </Routes>
          </BrowserRouter>
        )}
      </AuthGate>
    </ToastProvider>
  );
}
