import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { MemoryRouter } from "react-router-dom";
import App from "./App";
import "@fontsource-variable/inter";
import "./styles/tokens.css";
import "./components";

// MemoryRouter: the Tauri webview has no URL bar and deep links are not used yet.
createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <MemoryRouter>
      <App />
    </MemoryRouter>
  </StrictMode>,
);
