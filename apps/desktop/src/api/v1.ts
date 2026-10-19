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

export interface SyncRun {
  id: string;
  provider: string;
  status: "running" | "succeeded" | "partial" | "failed";
  completed_at: string | null;
  records_created: number | null;
  records_rejected: number | null;
  safe_error_code: string | null;
}
export interface Assessment {
  id: string;
  assessment_type: string;
  readiness_score: number | null;
  category: string | null;
  reason: string | null;
  model_version: string | null;
  created_at: string;
}
export interface ProviderEvidence {
  sync_run_id: string;
  synced_at: string;
  provenance: string;
  values: Record<string, number | null>;
  activity_trend?: {
    direction: "up" | "flat" | "down" | null;
    rule: string;
    as_of: string;
    provenance: string;
  };
}
export interface Evidence {
  evidence_version: string;
  cgpa: { value: number; provenance: string } | null;
  github: ProviderEvidence | null;
  leetcode: ProviderEvidence | null;
}

export const connectProvider = (provider: string, username: string) =>
  request<Integration>(`/api/v1/integrations/${provider}`, { method: "PUT", body: { username } });
export const disconnectProvider = (provider: string, deleteData = false) =>
  request<void>(`/api/v1/integrations/${provider}${deleteData ? "?delete_data=true" : ""}`, {
    method: "DELETE",
  });
export const exportMyData = () => request<unknown>("/api/v1/me/export");
export const deleteAccount = () =>
  request<unknown>("/api/v1/me/data-requests/deletion?confirm=true", { method: "POST" });
export const getPrivacy = () => request<{ research_consent: boolean }>("/api/v1/me/privacy");
export const putPrivacy = (research: boolean) =>
  request<{ research_consent: boolean }>("/api/v1/me/privacy", { method: "PUT", body: { research } });
export const startSync = (provider: string) =>
  request<{ id: string }>(`/api/v1/integrations/${provider}/sync`, { method: "POST" });
export const getSyncRun = (id: string) => request<SyncRun>(`/api/v1/sync-runs/${id}`);
export const listSyncRuns = (provider: string) =>
  request<{ items: SyncRun[] }>(`/api/v1/sync-runs?provider=${provider}&limit=1`);
export const getDataQuality = () =>
  request<{ items: { provider: string; rejected_by_rule: Record<string, number> }[] }>(
    "/api/v1/me/data-quality",
  );
export const createAssessment = () => request<Assessment>("/api/v1/assessments", { method: "POST" });
export const listAssessments = (limit = 20) =>
  request<{ items: Assessment[] }>(`/api/v1/assessments?limit=${limit}`);
export const getEvidence = (id: string) =>
  request<{ assessment_id: string; evidence: Evidence }>(`/api/v1/assessments/${id}/evidence`);
