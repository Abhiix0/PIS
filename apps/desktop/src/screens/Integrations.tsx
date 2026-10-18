import { useEffect, useRef, useState, type FormEvent } from "react";
import {
  connectProvider,
  disconnectProvider,
  getIntegrations,
  getSyncRun,
  startSync,
  type Integration,
  type SyncRun,
} from "../api/v1";
import { Button, EmptyState, ErrorState, Input, Loading } from "../components";
import { friendly } from "./Dashboard";

const PROVIDERS = [
  {
    id: "github",
    name: "GitHub",
    collects:
      "Public repository count and commit counts for recently pushed public repositories. Public data only; no token or private repositories.",
  },
  {
    id: "leetcode",
    name: "LeetCode",
    collects:
      "Aggregate solved-problem counts (easy/medium/hard). No solve dates. Public profile only; may be disabled by the operator.",
  },
] as const;

// Distinct, user-facing meaning for each safe error code the backend can return.
export const OUTCOME: Record<string, string> = {
  rate_limited: "The provider is rate-limiting requests. Try again later; your earlier data is kept.",
  forbidden:
    "The provider refused access (the profile may be private or blocked). Check the username and its visibility.",
  unavailable: "The provider is having an outage. Try again later; your earlier data is kept.",
  not_found: "That account was not found at the provider. Check the username.",
  malformed: "The provider returned data we could not read. Your earlier data is kept.",
  abandoned: "The previous sync was interrupted. Run it again.",
  all_rejected: "Every record failed validation, so nothing was imported.",
  partial_result: "Only part of the data could be fetched; the rest was skipped.",
  disabled: "This integration is turned off.",
};
const POLL_MS = 2000;
const POLL_MAX = 60; // bounded: stop polling after ~2 minutes and tell the user

export const describeRun = (r: SyncRun) =>
  r.status === "succeeded"
    ? `Sync finished: ${r.records_created ?? 0} records imported.`
    : r.status === "partial"
      ? `Sync partly succeeded: ${r.records_created ?? 0} imported, ${r.records_rejected ?? 0} rejected. ${OUTCOME[r.safe_error_code ?? ""] ?? ""}`
      : `Sync failed. ${OUTCOME[r.safe_error_code ?? ""] ?? "Unexpected error; try again."}`;

const when = (t: string | null) => (t ? new Date(t).toLocaleString() : "never");

function Provider({
  p,
  conn,
  reload,
}: {
  p: (typeof PROVIDERS)[number];
  conn?: Integration;
  reload: () => void;
}) {
  const [wipe, setWipe] = useState(false);
  const [username, setUsername] = useState("");
  const [consent, setConsent] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const alive = useRef(true);
  useEffect(() => {
    alive.current = true;
    return () => {
      alive.current = false;
    };
  }, []);

  async function run(fn: () => Promise<void>) {
    setBusy(true);
    setMsg(null);
    try {
      await fn();
    } catch (e) {
      if (alive.current) setMsg(friendly(e));
    } finally {
      if (alive.current) setBusy(false);
    }
  }
  const connect = (ev: FormEvent) => {
    ev.preventDefault();
    if (username.trim() && consent)
      void run(async () => {
        await connectProvider(p.id, username.trim());
        reload();
      });
  };
  const sync = () =>
    run(async () => {
      const { id } = await startSync(p.id); // not replayed automatically: a failure is shown, the user decides
      setMsg("Sync running…");
      for (let i = 0; i < POLL_MAX && alive.current; i++) {
        await new Promise((r) => setTimeout(r, POLL_MS));
        const r = await getSyncRun(id);
        if (r.status !== "running") {
          setMsg(describeRun(r));
          return reload();
        }
      }
      if (alive.current) setMsg("Sync is taking longer than expected. Check again later.");
    });

  return (
    <section aria-labelledby={`h-${p.id}`}>
      <h2 id={`h-${p.id}`}>{p.name}</h2>
      <p>Collects: {p.collects}</p>
      {conn ? (
        <>
          <p>
            Account <strong>{conn.external_username}</strong> · {conn.status}
          </p>
          <p>
            Last attempt: {when(conn.last_attempt_at)} · Last successful sync: {when(conn.last_success_at)}
          </p>
          <Button onClick={() => void sync()} disabled={busy}>
            Sync now
          </Button>{" "}
          <Button
            disabled={busy}
            onClick={() =>
              void run(async () => {
                await disconnectProvider(p.id, wipe);
                reload();
              })
            }
          >
            Disconnect
          </Button>
          <p>
            <label>
              <input type="checkbox" checked={wipe} onChange={(e) => setWipe(e.target.checked)} /> Also delete
              data imported from {p.name}
            </label>
          </p>
          <p className="muted">
            Disconnecting stops syncing; no {p.name} credentials are stored, so none need revoking. Imported
            data is kept unless you tick the box. Past assessments keep the snapshot they were built from
            either way.
          </p>
        </>
      ) : (
        <form onSubmit={connect} noValidate>
          <Input
            label={`${p.name} username`}
            value={username}
            onChange={(e) => setUsername(e.target.value)}
          />
          <label>
            <input type="checkbox" checked={consent} onChange={(e) => setConsent(e.target.checked)} /> I agree
            PIS may read the public data listed above for this account.
          </label>
          <div>
            <Button type="submit" disabled={busy || !consent || !username.trim()}>
              Connect
            </Button>
          </div>
        </form>
      )}
      {msg && <p role="status">{msg}</p>}
    </section>
  );
}

export default function Integrations() {
  const [items, setItems] = useState<Integration[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [n, setN] = useState(0);
  useEffect(() => {
    let live = true;
    getIntegrations().then(
      (r) => live && setItems(r.items),
      (e) => live && setError(friendly(e)),
    );
    return () => {
      live = false;
    };
  }, [n]);
  const reload = () => setN((x) => x + 1);
  if (error)
    return (
      <ErrorState
        message={error}
        onRetry={() => {
          setError(null);
          reload();
        }}
      />
    );
  if (!items) return <Loading />;
  return (
    <>
      <h1>Integrations</h1>
      {items.length === 0 && (
        <EmptyState
          title="Nothing connected yet"
          hint="Connect an account to give the assessment evidence."
        />
      )}
      {PROVIDERS.map((p) => (
        <Provider key={p.id} p={p} conn={items.find((i) => i.provider === p.id)} reload={reload} />
      ))}
    </>
  );
}
