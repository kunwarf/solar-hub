import * as React from "react";
import { createRoot } from "react-dom/client";
import App from "./App.tsx";

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
