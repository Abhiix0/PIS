import { useEffect, useState } from "react";
import { getEvidence, listAssessments, type Assessment } from "../api/v1";
import {
  Badge,
  Banner,
  Button,
  Card,
  EmptyState,
  ErrorState,
  Loading,
  PageHeader,
  Table,
} from "../components";
import { compare, type Comparison } from "../lib/assessment";
import { friendly } from "./Dashboard";

export default function History() {
  const [items, setItems] = useState<Assessment[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pick, setPick] = useState<string[]>([]);
  const [cmp, setCmp] = useState<Comparison | null>(null);
  const [n, setN] = useState(0);
  useEffect(() => {
    let live = true;
    listAssessments(50).then(
      (r) => live && setItems(r.items),
      (e) => live && setError(friendly(e)),
    );
    return () => {
      live = false;
    };
  }, [n]);
  if (error)
    return (
      <ErrorState
        message={error}
        onRetry={() => {
          setError(null);
          setN(n + 1);
        }}
      />
    );
  if (!items) return <Loading />;
  if (!items.length)
    return (
      <>
        <PageHeader title="History" />
        <EmptyState
          title="No assessments yet"
          hint="Run an assessment from the Overview to start your history."
        />
      </>
    );

  const toggle = (id: string) => {
    setCmp(null);
    setPick(pick.includes(id) ? pick.filter((x) => x !== id) : [...pick, id].slice(-2));
  };
  async function run() {
    try {
      // older snapshot first so deltas read forward in time
      const sel = pick
        .map((id) => items!.find((i) => i.id === id)!)
        .sort((p, q) => p.created_at.localeCompare(q.created_at));
      const [x, y] = sel as [Assessment, Assessment];
      const [ex, ey] = await Promise.all([getEvidence(x.id), getEvidence(y.id)]);
      setCmp(compare({ a: x, ev: ex.evidence }, { a: y, ev: ey.evidence }));
    } catch (e) {
      setError(friendly(e));
    }
  }
  return (
    <>
      <PageHeader
        title="History"
        sub="Each assessment is a saved snapshot. Pick two to compare."
        actions={
          <Button disabled={pick.length !== 2} onClick={() => void run()}>
            Compare selected (pick 2)
          </Button>
        }
      />
      <Card>
        <ul className="plain">
          {items.map((a) => (
            <li key={a.id}>
              <label className="check">
                <input type="checkbox" checked={pick.includes(a.id)} onChange={() => toggle(a.id)} />
                <span>
                  {new Date(a.created_at).toLocaleString()} · model {a.model_version ?? "none"}{" "}
                  <Badge>{a.assessment_type.replace("_", " ")}</Badge>
                </span>
              </label>
            </li>
          ))}
        </ul>
      </Card>
      {cmp && (
        <Card aria-label="Comparison">
          {!cmp.comparable && (
            <p role="alert" className="err">
              ! These snapshots cannot be compared. {cmp.notes.join(" ")}
            </p>
          )}
          {cmp.comparable && (
            <>
              {cmp.notes.map((t) => (
                <Banner key={t}>{t}</Banner>
              ))}
              {cmp.deltas.length === 0 ? (
                <p>No observed values in either snapshot.</p>
              ) : (
                <Table>
                  <thead>
                    <tr>
                      <th>Item</th>
                      <th>Earlier</th>
                      <th>Later</th>
                    </tr>
                  </thead>
                  <tbody>
                    {cmp.deltas.map((d) => (
                      <tr key={d.key}>
                        <td>{d.key}</td>
                        <td>{d.from ?? "—"}</td>
                        <td>{d.to ?? "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </Table>
              )}
            </>
          )}
        </Card>
      )}
    </>
  );
}
