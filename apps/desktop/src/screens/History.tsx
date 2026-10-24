import { useEffect, useState } from "react";
import { compareAssessments, listAssessments, type Assessment, type Comparison } from "../api/v1";
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
      // older snapshot first so deltas read forward in time; the server decides what is comparable
      const [x, y] = pick
        .map((id) => items!.find((i) => i.id === id)!)
        .sort((p, q) => p.created_at.localeCompare(q.created_at)) as [Assessment, Assessment];
      setCmp(await compareAssessments(x.id, y.id));
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
              ! These snapshots cannot be compared value by value.
            </p>
          )}
          {cmp.disclosures.map((t) => (
            <Banner key={t}>{t}</Banner>
          ))}
          {cmp.dimensions.map((d) => (
            <div key={d.dimension} className="stack">
              <h2>{d.dimension}</h2>
              {d.only_in ? (
                <p>Present only in the {d.only_in === "from" ? "earlier" : "later"} snapshot.</p>
              ) : (
                <div className="tbl-wrap">
                  <Table>
                    <thead>
                      <tr>
                        <th>Item</th>
                        <th>Earlier</th>
                        <th>Later</th>
                        <th>Change</th>
                      </tr>
                    </thead>
                    <tbody>
                      {d.deltas.map((x) => (
                        <tr key={x.name}>
                          <td>{x.name}</td>
                          <td>{x.from ?? "—"}</td>
                          <td>{x.to ?? "—"}</td>
                          <td>{x.delta ?? "—"}</td>
                        </tr>
                      ))}
                    </tbody>
                  </Table>
                </div>
              )}
            </div>
          ))}
        </Card>
      )}
    </>
  );
}
