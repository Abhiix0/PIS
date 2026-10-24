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
export type EvidenceState = "no_evidence" | "stale" | "partial" | "sufficient" | "source_failed";
export interface DimensionValue {
  name: string;
  value: number | string | null;
  provenance: string;
  value_state: string;
  event_at_precision: string | null;
  collected_at: string | null;
  synced_at: string | null;
  sync_run_id: string | null;
}
export interface Dimension {
  dimension: string;
  title: string;
  evidence_state: EvidenceState;
  values: DimensionValue[];
  rule: { id: string; text: string };
  coverage: string;
  caveats: string[];
  last_sync?: { status: string; error_code: string | null };
}
export interface Recommendation {
  id: string;
  rule_id: string;
  priority: number;
  dimension: string;
  action: string;
  reason: string;
  evidence_refs: { dimension: string; name: string | null; sync_run_id: string | null }[];
  limitation: string;
}
export interface AssessmentResult {
  assessment_version: string;
  evidence_version: string;
  generated_at: string;
  stale_after_days: number;
  dimensions: Dimension[];
  recommendations: Recommendation[];
  limitations: string;
}
export interface Assessment {
  id: string;
  assessment_type: string;
  readiness_score: number | null;
  category: string | null;
  reason: string | null;
  model_version: string | null;
  result: AssessmentResult | null; // null for snapshots made before rules-v1
  created_at: string;
}
export interface Comparison {
  from: { id: string; created_at: string };
  to: { id: string; created_at: string };
  comparable: boolean;
  disclosures: string[];
  dimensions: {
    dimension: string;
    from_state?: EvidenceState;
    to_state?: EvidenceState;
    only_in?: "from" | "to";
    deltas: {
      name: string;
      from: number | string | null;
      to: number | string | null;
      delta: number | null;
    }[];
  }[];
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
export const compareAssessments = (earlier: string, later: string) =>
  request<Comparison>(`/api/v1/assessments/${earlier}/compare/${later}`);
