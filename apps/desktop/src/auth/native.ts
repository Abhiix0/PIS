// Bridge to the Rust shell. The refresh token lives in Windows Credential Manager; the webview never persists it.
import { invoke } from "@tauri-apps/api/core";
import { openUrl } from "@tauri-apps/plugin-opener";

export const native = {
  loadRefresh: () => invoke<string | null>("token_load"),
  saveRefresh: (t: string) => invoke<void>("token_save", { token: t }),
  clearRefresh: () => invoke<void>("token_clear"),
  /** Binds 127.0.0.1:<random port> and returns the port. */
  listen: () => invoke<number>("auth_listen"),
  /** Resolves with the redirect's raw query string; rejects on timeout. */
  waitCallback: () => invoke<string>("auth_wait"),
  openBrowser: (url: string) => openUrl(url),
};
export type Native = typeof native;
