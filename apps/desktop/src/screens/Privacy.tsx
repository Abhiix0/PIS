import { useEffect, useState } from "react";
import { deleteAccount, exportMyData, getPrivacy, putPrivacy } from "../api/v1";
import { useSession } from "../auth/session";
import { Button, Card, ErrorState } from "../components";

export default function Privacy() {
  const { signOut } = useSession();
  const [consent, setConsent] = useState(false);
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");
  const [confirm, setConfirm] = useState(false);

  useEffect(() => {
    getPrivacy().then(
      (r) => setConsent(r.research_consent),
      () => setErr("Could not load privacy settings."),
    );
  }, []);

  const act = async (fn: () => Promise<void>) => {
    setErr("");
    try {
      await fn();
    } catch {
      setErr("That did not work. Nothing was changed; try again.");
    }
  };

  const download = () =>
    act(async () => {
      const blob = new Blob([JSON.stringify(await exportMyData(), null, 2)], { type: "application/json" });
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = "pis-export.json";
      a.click();
      URL.revokeObjectURL(a.href);
      setMsg("Export downloaded.");
    });

  return (
    <section aria-labelledby="privacy-h" className="stack">
      <h2 id="privacy-h">Privacy and your data</h2>
      {err && <ErrorState message={err} />}
      {msg && <p role="status">{msg}</p>}
      <Card>
        <h3>What is stored</h3>
        <ul>
          <li>Your profile (name, branch, graduation year, CGPA) - to build your assessment.</li>
          <li>
            Public GitHub/LeetCode usernames and the activity counts synced from them - the assessment
            evidence.
          </li>
          <li>Assessment snapshots - your history. No provider passwords or tokens are stored.</li>
        </ul>
        <p className="muted">
          Backups: database backups are kept for a limited period set by the operator and are not edited;
          deleted data leaves them when they expire.
        </p>
      </Card>
      <Card className="stack">
        <h3>Optional research use</h3>
        <label className="check">
          <input
            type="checkbox"
            checked={consent}
            onChange={(e) =>
              void act(async () => setConsent((await putPrivacy(e.target.checked)).research_consent))
            }
          />
          Allow my daily GitHub activity to be used for research
        </label>
        <p className="muted">
          This is separate from using your data to show your own assessment, which needs no consent. If you
          turn this on, the operator may export your daily GitHub contribution counts for research, under a
          random code with no name, email or username. Off by default; you can turn it off any time. Turning
          it off keeps your data out of future exports. Files already exported cannot be recalled or edited,
          because they hold no link back to you. Deleting your account also turns this off.
        </p>
      </Card>
      <Card className="stack">
        <h3>Export</h3>
        <div>
          <Button variant="ghost" onClick={() => void download()}>
            Download my data (JSON)
          </Button>
        </div>
      </Card>
      <Card className="stack danger-zone">
        <h3>Delete account</h3>
        <p>
          Permanently erases your profile, connections, imported data and assessments, and signs you out
          everywhere.
        </p>
        <label className="check">
          <input type="checkbox" checked={confirm} onChange={(e) => setConfirm(e.target.checked)} />I
          understand this cannot be undone
        </label>
        <div>
          <Button
            variant="danger"
            disabled={!confirm}
            onClick={() =>
              void act(async () => {
                await deleteAccount();
                await signOut();
              })
            }
          >
            Delete my account
          </Button>
        </div>
      </Card>
    </section>
  );
}
