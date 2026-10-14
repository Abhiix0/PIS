import { NavLink, Navigate, Route, Routes } from "react-router-dom";
import { ConnectionProvider, useConnection } from "./connection";
import { Button, ErrorState, Loading } from "./components/ui";
import { SessionProvider, useSession } from "./auth/session";
import Assessment from "./screens/Assessment";
import Dashboard from "./screens/Dashboard";
import History from "./screens/History";
import Integrations from "./screens/Integrations";
import Overview from "./screens/Overview";
import Plan from "./screens/Plan";

function Status() {
  const { status } = useConnection();
  const text = { checking: "Checking API…", online: "API online", offline: "API offline" }[status];
  return <span className={`pill ${status}`}>{text}</span>;
}

function Settings() {
  const { signOut } = useSession();
  const { status, recheck } = useConnection();
  return (
    <>
      <h1>Settings</h1>
      {status === "offline" && <ErrorState message="Cannot reach the server." onRetry={recheck} />}
      <Button onClick={() => void signOut()}>Sign out</Button>
    </>
  );
}

function SignIn() {
  const { state, notice, signIn, cancel } = useSession();
  return (
    <main className="signin">
      <h1>Placement Intelligence</h1>
      {notice && <p role="alert">{notice}</p>}
      {state === "signing-in" ? (
        <>
          <Loading label="Waiting for you to finish signing in in your browser…" />
          <Button onClick={cancel}>Cancel</Button>
        </>
      ) : (
        <Button onClick={() => void signIn()}>Sign in</Button>
      )}
    </main>
  );
}

function Shell() {
  const { state } = useSession();
  if (state === "loading") return <Loading />;
  if (state !== "signed-in") return <SignIn />;
  return (
    <div className="shell">
      <header>
        <strong>Placement Intelligence</strong>
        <Status />
      </header>
      <nav aria-label="Primary">
        <NavLink to="/overview">Overview</NavLink>
        <NavLink to="/integrations">Integrations</NavLink>
        <NavLink to="/assessment">Assessment</NavLink>
        <NavLink to="/plan">Development plan</NavLink>
        <NavLink to="/history">History</NavLink>
        <NavLink to="/dashboard">Profile</NavLink>
        <NavLink to="/settings">Settings</NavLink>
      </nav>
      <main>
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
      </main>
    </div>
  );
}

export default function App() {
  return (
    <ConnectionProvider>
      <SessionProvider>
        <Shell />
      </SessionProvider>
    </ConnectionProvider>
  );
}
