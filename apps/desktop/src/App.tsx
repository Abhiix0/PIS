import { Navigate, Route, Routes } from "react-router-dom";
import { ConnectionProvider, useConnection } from "./connection";
import { AppShell, Badge, Button, Card, ErrorState, Loading, PageHeader } from "./components";
import { SessionProvider, useSession } from "./auth/session";
import type { Native } from "./auth/native";
import { DEMO } from "./lib/assessment";
import Assessment from "./screens/Assessment";
import Dashboard from "./screens/Dashboard";
import History from "./screens/History";
import Integrations from "./screens/Integrations";
import Overview from "./screens/Overview";
import Plan from "./screens/Plan";
import Privacy from "./screens/Privacy";

function Status() {
  const { status } = useConnection();
  const text = { checking: "… Checking API", online: "✓ API online", offline: "✕ API offline" }[status];
  return (
    <span className="row">
      {DEMO && <Badge tone="info">Sample data</Badge>}
      <Badge
        tone={{ checking: "neutral", online: "ok", offline: "danger" }[status] as "neutral" | "ok" | "danger"}
      >
        {text}
      </Badge>
    </span>
  );
}

function Settings() {
  const { signOut } = useSession();
  const { status, recheck } = useConnection();
  return (
    <>
      <PageHeader
        title="Settings"
        actions={
          <Button variant="ghost" onClick={() => void signOut()}>
            Sign out
          </Button>
        }
      />
      {status === "offline" && <ErrorState message="Cannot reach the server." onRetry={recheck} />}
      <Privacy />
    </>
  );
}

function SignIn() {
  const { state, notice, signIn, cancel } = useSession();
  return (
    <main className="signin">
      <Card className="signin-card">
        <h1>Placement Intelligence</h1>
        <p className="muted">
          A readiness proxy score and development plan built from your public coding and GitHub activity.
        </p>
        {notice && (
          <p role="alert" className="err">
            ! {notice}
          </p>
        )}
        {state === "signing-in" ? (
          <>
            <Loading label="Waiting for you to finish signing in in your browser…" />
            <Button variant="ghost" onClick={cancel}>
              Cancel
            </Button>
          </>
        ) : (
          <Button variant="accent" onClick={() => void signIn()}>
            Sign in
          </Button>
        )}
      </Card>
    </main>
  );
}

const NAV = [
  { to: "/overview", label: "Overview" },
  { to: "/integrations", label: "Integrations" },
  { to: "/assessment", label: "Assessment" },
  { to: "/plan", label: "Development plan" },
  { to: "/history", label: "History" },
  { to: "/dashboard", label: "Profile" },
  { to: "/settings", label: "Settings" },
];

function Shell() {
  const { state } = useSession();
  if (state === "loading")
    return (
      <main className="signin">
        <Loading />
      </main>
    );
  if (state !== "signed-in") return <SignIn />;
  return (
    <AppShell title="Placement Intelligence" nav={NAV} status={<Status />}>
      <Routes>
        <Route path="/overview" element={<Overview />} />
        <Route path="/integrations" element={<Integrations />} />
        <Route path="/assessment" element={<Assessment />} />
        <Route path="/plan" element={<Plan />} />
        <Route path="/history" element={<History />} />
        <Route path="/dashboard" element={<Dashboard />} />
        <Route path="/settings" element={<Settings />} />
        <Route path="*" element={<Navigate to="/overview" replace />} />
      </Routes>
    </AppShell>
  );
}

export default function App({ native }: { native?: Native }) {
  return (
    <ConnectionProvider>
      <SessionProvider native={native}>
        <Shell />
      </SessionProvider>
    </ConnectionProvider>
  );
}
