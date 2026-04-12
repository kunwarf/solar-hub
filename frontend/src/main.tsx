import * as React from "react";
import { createRoot } from "react-dom/client";
import { registerSW } from "virtual:pwa-register";
import App from "./App.tsx";

// Activate new service worker immediately on install so mobile PWA users
// receive frontend updates without having to fully close and reopen the app.
registerSW({ immediate: true, onNeedRefresh() { location.reload(); } });

// Ensure React and hooks are available globally for Radix UI
if (typeof window !== 'undefined') {
  (window as any).React = React;
  (window as any).useMemo = React.useMemo;
  (window as any).useCallback = React.useCallback;
  (window as any).useEffect = React.useEffect;
  (window as any).useState = React.useState;
  (window as any).useRef = React.useRef;
}
import "@fontsource/jetbrains-mono/400.css";
import "@fontsource/jetbrains-mono/500.css";
import "@fontsource/jetbrains-mono/700.css";
import "@fontsource/inter/400.css";
import "@fontsource/inter/500.css";
import "@fontsource/inter/600.css";
import "@fontsource/inter/700.css";
import "./index.css";

createRoot(document.getElementById("root")!).render(<App />);
