import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { MemoryRouter } from "react-router-dom";
import App from "./App";
import "@fontsource-variable/inter";
import "./styles/tokens.css";
import "./components";

// Dev-only: DEV is a build-time constant, so the mock module is dropped from production bundles.
const mock = import.meta.env.DEV && import.meta.env.VITE_MOCK_API === "1" ? await import("./api/mock") : null;
mock?.installMock();

// MemoryRouter: the Tauri webview has no URL bar and deep links are not used yet.
createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <MemoryRouter>
      <App native={mock?.mockNative} />
    </MemoryRouter>
  </StrictMode>,
);
