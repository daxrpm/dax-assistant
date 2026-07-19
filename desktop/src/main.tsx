import React from "react";
import ReactDOM from "react-dom/client";
import { App } from "./App";
import { I18nProvider } from "./i18n/I18n";
import "./design/global.css";
import { shutdownRealtimeStores } from "./stores/realtime";
import { desktopRuntime } from "./native/runtime";

const root = document.getElementById("root");
if (!root) throw new Error("#root missing from index.html");

ReactDOM.createRoot(root).render(
  <React.StrictMode>
    <I18nProvider>
      <App />
    </I18nProvider>
  </React.StrictMode>,
);

window.addEventListener(
  "pagehide",
  () => {
    desktopRuntime.stop();
    shutdownRealtimeStores();
  },
  { once: true },
);
