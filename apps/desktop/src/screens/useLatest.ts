import { useCallback, useEffect, useState } from "react";
import { listAssessments, type Assessment } from "../api/v1";
import { friendly } from "./Dashboard";

export type Latest =
  { s: "loading" } | { s: "error"; message: string } | { s: "empty" } | { s: "ready"; a: Assessment };

// One fetch per mount (and per reload); a response from a superseded load is ignored.
export function useLatest(): [Latest, () => void] {
  const [state, setState] = useState<Latest>({ s: "loading" });
  const [n, setN] = useState(0);
  useEffect(() => {
    let live = true;
    listAssessments(1)
      .then(({ items }): Latest => (items[0] ? { s: "ready", a: items[0] } : { s: "empty" }))
      .catch((e): Latest => ({ s: "error", message: friendly(e) }))
      .then((r) => {
        if (live) setState(r);
      });
    return () => {
      live = false;
    };
  }, [n]);
  const reload = useCallback(() => {
    setState({ s: "loading" });
    setN((x) => x + 1);
  }, []);
  return [state, reload];
}
