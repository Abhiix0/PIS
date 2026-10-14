import { request } from "./client";

export interface Profile {
  id: string;
  display_name: string;
  branch: string | null;
  graduation_year: number | null;
  cgpa: number | null;
}
export type ProfileInput = Omit<Profile, "id">;
export interface Integration {
  id: string;
  provider: string;
  external_username: string;
  status: string;
  last_attempt_at: string | null;
  last_success_at: string | null;
}

export const getMe = () => request<{ user_id: string; profile: Profile | null }>("/api/v1/me");
export const putProfile = (p: ProfileInput) =>
  request<Profile>("/api/v1/me/profile", { method: "PUT", body: p });
export const getIntegrations = () => request<{ items: Integration[] }>("/api/v1/integrations");
export const logoutServer = () => request<void>("/auth/logout", { method: "POST" });
