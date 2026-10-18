import { useCallback, useEffect, useState, type FormEvent } from "react";
import { ApiError } from "../api/client";
import { getIntegrations, getMe, putProfile, type Integration, type Profile } from "../api/v1";
import { Button, EmptyState, ErrorState, Input, Loading } from "../components";

export const friendly = (e: unknown) =>
  e instanceof ApiError
    ? e.kind === "network" || e.kind === "timeout"
      ? "Cannot reach the server. Check your connection and try again."
      : e.status === 403
        ? "You don't have permission to do that. Contact support if this is unexpected."
        : e.status === 429
          ? "Too many requests. Wait a moment and try again."
          : `${e.message}${e.requestId ? ` (ref ${e.requestId})` : ""}`
    : "Something went wrong.";

// Mirrors the server's limits; the server remains the authority.
export function validate(f: { display_name: string; graduation_year: string; cgpa: string }) {
  const err: Record<string, string> = {};
  if (!f.display_name.trim() || f.display_name.length > 100)
    err.display_name = "Enter a name (1–100 characters).";
  const y = f.graduation_year.trim();
  if (y && !(/^\d{4}$/.test(y) && +y >= 2000 && +y <= 2100))
    err.graduation_year = "Enter a year between 2000 and 2100.";
  const c = f.cgpa.trim();
  if (c && !(Number.isFinite(+c) && +c >= 0 && +c <= 10)) err.cgpa = "CGPA must be between 0 and 10.";
  return err;
}

function ProfileForm({ initial, onSaved }: { initial: Profile | null; onSaved: (p: Profile) => void }) {
  const [f, setF] = useState({
    display_name: initial?.display_name ?? "",
    branch: initial?.branch ?? "",
    graduation_year: initial?.graduation_year?.toString() ?? "",
    cgpa: initial?.cgpa?.toString() ?? "",
  });
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [failure, setFailure] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const set = (k: keyof typeof f) => (e: { target: { value: string } }) =>
    setF({ ...f, [k]: e.target.value });

  async function submit(ev: FormEvent) {
    ev.preventDefault();
    const v = validate(f);
    setErrors(v);
    if (Object.keys(v).length) return;
    setSaving(true);
    setFailure(null);
    try {
      onSaved(
        await putProfile({
          display_name: f.display_name.trim(),
          branch: f.branch.trim() || null,
          graduation_year: f.graduation_year.trim() ? +f.graduation_year : null,
          cgpa: f.cgpa.trim() ? +f.cgpa : null,
        }),
      );
    } catch (e) {
      setFailure(friendly(e)); // the form keeps the user's input so they can retry
    } finally {
      setSaving(false);
    }
  }

  return (
    <form onSubmit={submit} noValidate>
      <Input label="Name" value={f.display_name} onChange={set("display_name")} error={errors.display_name} />
      <Input label="Branch" value={f.branch} onChange={set("branch")} />
      <Input
        label="Graduation year"
        inputMode="numeric"
        value={f.graduation_year}
        onChange={set("graduation_year")}
        error={errors.graduation_year}
      />
      <Input label="CGPA" inputMode="decimal" value={f.cgpa} onChange={set("cgpa")} error={errors.cgpa} />
      {failure && (
        <p role="alert" className="err">
          {failure}
        </p>
      )}
      <Button type="submit" disabled={saving}>
        {saving ? "Saving…" : "Save profile"}
      </Button>
    </form>
  );
}

const when = (t: string | null) => (t ? new Date(t).toLocaleString() : "never");

export default function Dashboard() {
  const [data, setData] = useState<{ profile: Profile | null; items: Integration[] } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [editing, setEditing] = useState(false);

  const load = useCallback(() => {
    Promise.all([getMe(), getIntegrations()]).then(
      ([me, i]) => setData({ profile: me.profile, items: i.items }),
      (e) => setError(friendly(e)),
    );
  }, []);
  useEffect(load, [load]);

  if (error)
    return (
      <ErrorState
        message={error}
        onRetry={() => {
          setError(null);
          load();
        }}
      />
    );
  if (!data) return <Loading />;
  const { profile, items } = data;
  return (
    <>
      <h1>Profile</h1>
      <section aria-labelledby="h-profile">
        <h2 id="h-profile">Profile</h2>
        {!profile || editing ? (
          <>
            {!profile && <p>No profile yet. Add your details to get started.</p>}
            <ProfileForm
              initial={profile}
              onSaved={(p) => {
                setData({ ...data, profile: p });
                setEditing(false);
              }}
            />
          </>
        ) : (
          <>
            <p>
              <strong>{profile.display_name}</strong>
              {profile.branch && ` · ${profile.branch}`}
              {profile.graduation_year && ` · Class of ${profile.graduation_year}`}
              {profile.cgpa !== null && ` · CGPA ${profile.cgpa}`}
            </p>
            <Button onClick={() => setEditing(true)}>Edit profile</Button>
          </>
        )}
      </section>
      <section aria-labelledby="h-int">
        <h2 id="h-int">Integrations</h2>
        {items.length === 0 ? (
          <EmptyState
            title="No integrations connected"
            hint="Connect GitHub or LeetCode from the Integrations screen."
          />
        ) : (
          <ul>
            {items.map((i) => (
              <li key={i.id}>
                {i.provider} ({i.external_username}): {i.status}. Last successful sync:{" "}
                {when(i.last_success_at)}
              </li>
            ))}
          </ul>
        )}
      </section>
    </>
  );
}
