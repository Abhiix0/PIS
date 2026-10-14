import { Empty, ErrorState, Loading } from "../components/ui";
import { DISCLAIMER, priorities } from "../lib/assessment";
import { useLatest } from "./useLatest";

export default function Plan() {
  const [l, reload] = useLatest();
  if (l.s === "loading") return <Loading />;
  if (l.s === "error") return <ErrorState message={l.message} onRetry={reload} />;
  if (l.s === "empty")
    return (
      <>
        <h1>Development plan</h1>
        <Empty title="No assessment yet" hint="Run one from the Overview to get priorities." />
      </>
    );
  const ps = priorities(l.ev);
  return (
    <>
      <h1>Development plan</h1>
      <p className="muted">{DISCLAIMER} These come from fixed rules, not from the ML model.</p>
      {ps.length === 0 ? (
        <Empty
          title="No priorities from current evidence"
          hint="Nothing in your latest snapshot triggers a suggestion."
        />
      ) : (
        <ol>
          {ps.map((p) => (
            <li key={p.id}>
              {p.text} <span className="muted">Evidence: {p.evidence}</span>
            </li>
          ))}
        </ol>
      )}
    </>
  );
}
