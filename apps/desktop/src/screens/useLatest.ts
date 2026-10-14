import { useCallback, useEffect, useState } from "react";
import { getEvidence, listAssessments, type Assessment, type Evidence } from "../api/v1";
import { friendly } from "./Dashboard";

export type Latest =
  | { s: "loading" }
  | { s: "error"; message: string }
  | { s: "empty" }
  | { s: "ready"; a: Assessment; ev: Evidence };

// One fetch per mount (and per reload); a response from a superseded load is ignored.
export function useLatest(): [Latest, () => void] {
  const [state, setState] = useState<Latest>({ s: "loading" });
  const [n, setN] = useState(0);
  useEffect(() => {
    let live = true;
    listAssessments(1)
      .then(async ({ items }): Promise<Latest> => {
        if (!items[0]) return { s: "empty" };
        const { evidence } = await getEvidence(items[0].id);
        return { s: "ready", a: items[0], ev: evidence };
      })
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
