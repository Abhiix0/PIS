import { Empty, ErrorState, Loading } from "../components/ui";
import { FEATURE_DEFS, hasScore } from "../lib/assessment";
import { useLatest } from "./useLatest";

const when = (t: string) => new Date(t).toLocaleString();

export default function Assessment() {
  const [l, reload] = useLatest();
  if (l.s === "loading") return <Loading />;
  if (l.s === "error") return <ErrorState message={l.message} onRetry={reload} />;
  if (l.s === "empty")
    return (
      <>
        <h1>Assessment</h1>
        <Empty title="No assessment yet" hint="Run one from the Overview." />
      </>
    );
  const { a, ev } = l;
  return (
    <>
      <h1>Assessment</h1>
      <p>
        Snapshot {when(a.created_at)} · evidence {ev.evidence_version} · model{" "}
        {a.model_version ?? "none (no model used)"}
      </p>
      <h2>Result</h2>
      <p>
        {hasScore(a)
          ? `Readiness proxy score ${a.readiness_score} (ML estimate).`
          : `No ML estimate. ${a.reason}`}
      </p>
      <h2>Evidence</h2>
      <table>
        <thead>
          <tr>
            <th>Item</th>
            <th>Value</th>
            <th>Kind</th>
            <th>Source</th>
            <th>Meaning</th>
          </tr>
        </thead>
        <tbody>
          {ev.cgpa && (
            <tr>
              <td>CGPA</td>
              <td>{ev.cgpa.value}</td>
              <td>User-entered</td>
              <td>Your profile</td>
              <td>Self-reported; not verified.</td>
            </tr>
          )}
          {(["github", "leetcode"] as const).flatMap((p) =>
            Object.entries(ev[p]?.values ?? {}).map(([k, v]) => (
              <tr key={`${p}-${k}`}>
                <td>{k}</td>
                <td>{v}</td>
                <td>Observed ({ev[p]!.provenance})</td>
                <td>
                  {p}, collected {when(ev[p]!.synced_at)} (run {ev[p]!.sync_run_id.slice(0, 8)})
                </td>
                <td>{FEATURE_DEFS[k] ?? "Provider-reported value."}</td>
              </tr>
            )),
          )}
        </tbody>
      </table>
      <h2>Limitations</h2>
      <ul>
        <li>This is an evidence summary. It does not predict hiring or placement outcomes.</li>
        <li>
          The readiness model was trained on a formula over a few demo students, not real placement results.
        </li>
        <li>Provider counts come from public profiles and can lag or be incomplete.</li>
      </ul>
    </>
  );
}
