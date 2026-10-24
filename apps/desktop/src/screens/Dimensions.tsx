import type { Dimension, Recommendation } from "../api/v1";
import { Badge, Banner, Card, StatusBadge, Table } from "../components";
import { FEATURE_DEFS, STATE_LABEL } from "../lib/assessment";

const when = (t: string | null) => (t ? new Date(t).toLocaleString() : "—");

const shown = (v: Dimension["values"][number]) =>
  v.value_state === "measured_zero"
    ? "0 (reported by the provider)"
    : v.value === null
      ? "Not available"
      : String(v.value);

export function DimensionCard({ d }: { d: Dimension }) {
  const id = `dim-${d.dimension}`;
  return (
    <Card className="stack" aria-labelledby={id}>
      <div className="row">
        <h2 id={id}>{d.title}</h2>
        <StatusBadge status={d.evidence_state} />
      </div>
      {d.last_sync && (
        <Banner tone="warn">
          ! Last sync {d.last_sync.status}
          {d.last_sync.error_code ? ` (${d.last_sync.error_code})` : ""}. Values below are from the last
          successful import.
        </Banner>
      )}
      {d.values.length === 0 ? (
        <p>No evidence yet for this area ({STATE_LABEL[d.evidence_state].toLowerCase()}).</p>
      ) : (
        <div className="tbl-wrap">
          <Table>
            <thead>
              <tr>
                <th>Item</th>
                <th>Value</th>
                <th>Kind</th>
                <th>Collected</th>
                <th>Meaning</th>
              </tr>
            </thead>
            <tbody>
              {d.values.map((v) => (
                <tr key={v.name}>
                  <td>{v.name}</td>
                  <td>{shown(v)}</td>
                  <td>
                    <Badge tone={v.provenance === "observed" ? "ok" : "warn"}>{v.provenance}</Badge>
                  </td>
                  <td>
                    {when(v.synced_at ?? v.collected_at)}
                    {v.sync_run_id ? ` (run ${v.sync_run_id.slice(0, 8)})` : ""}
                  </td>
                  <td>{FEATURE_DEFS[v.name] ?? "Provider-reported value."}</td>
                </tr>
              ))}
            </tbody>
          </Table>
        </div>
      )}
      <p>
        <strong>Rule {d.rule.id}:</strong> {d.rule.text}
      </p>
      <p>
        <strong>Coverage:</strong> {d.coverage}
      </p>
      <ul>
        {d.caveats.map((c) => (
          <li key={c}>{c}</li>
        ))}
      </ul>
    </Card>
  );
}

export function RecommendationList({ items }: { items: Recommendation[] }) {
  return (
    <ol>
      {items.map((r) => (
        <li key={r.id}>
          {r.action} <span className="muted">{r.reason}</span>
          <div className="muted">
            Rule {r.rule_id} · evidence:{" "}
            {r.evidence_refs
              .map(
                (e) =>
                  `${e.dimension}${e.name ? ` ${e.name}` : ""}${e.sync_run_id ? ` (run ${e.sync_run_id.slice(0, 8)})` : ""}`,
              )
              .join(", ")}
          </div>
        </li>
      ))}
    </ol>
  );
}

export const LegacyNotice = () => (
  <Banner>
    This snapshot was made before the current assessment rules, so it has no per-area breakdown. Run a new
    assessment from the Overview.
  </Banner>
);
