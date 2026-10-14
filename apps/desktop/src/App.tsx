import { NavLink, Navigate, Route, Routes } from "react-router-dom";
import { ConnectionProvider, useConnection } from "./connection";
import { Empty, ErrorState, Loading } from "./components/ui";

function Status() {
  const { status } = useConnection();
  const text = { checking: "Checking API…", online: "API online", offline: "API offline" }[status];
  return <span className={`pill ${status}`}>{text}</span>;
}

function Page({ title }: { title: string }) {
  const { status, recheck } = useConnection();
  return (
    <>
      <h1>{title}</h1>
      {status === "checking" && <Loading />}
      {status === "offline" && (
        <ErrorState
          message="Cannot reach the server. Check your connection and try again."
          onRetry={recheck}
        />
      )}
      {status === "online" && (
        <Empty title="Nothing here yet" hint="This screen is built in a later phase." />
      )}
    </>
  );
}

export default function App() {
  return (
    <ConnectionProvider>
      <div className="shell">
        <header>
          <strong>Placement Intelligence</strong>
          <Status />
        </header>
        <nav aria-label="Primary">
          <NavLink to="/dashboard">Dashboard</NavLink>
          <NavLink to="/settings">Settings</NavLink>
        </nav>
        <main>
          <Routes>
            <Route path="/dashboard" element={<Page title="Dashboard" />} />
            <Route path="/settings" element={<Page title="Settings" />} />
            <Route path="*" element={<Navigate to="/dashboard" replace />} />
          </Routes>
        </main>
      </div>
    </ConnectionProvider>
  );
}
