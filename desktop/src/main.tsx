import React from "react";
import ReactDOM from "react-dom/client";
import { App } from "./App";
import { APP_ICON_URL } from "./components/AppIcon";
import { I18nProvider } from "./i18n/I18n";
import "./design/global.css";

const favicon = document.createElement("link");
favicon.rel = "icon";
favicon.type = "image/png";
favicon.href = APP_ICON_URL;
document.head.append(favicon);
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
