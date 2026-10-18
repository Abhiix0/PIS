import type { ReactNode } from "react";
import { NavLink } from "react-router-dom";

export type AppShellProps = {
  title: string;
  nav: { to: string; label: string }[];
  status?: ReactNode;
  children: ReactNode;
};

export const AppShell = ({ title, nav, status, children }: AppShellProps) => (
  <div className="shell">
    <nav aria-label="Primary">
      <div className="brand">{title}</div>
      {nav.map((n) => (
        <NavLink key={n.to} to={n.to}>
          {n.label}
        </NavLink>
      ))}
    </nav>
    <header>
      <strong>{title}</strong>
      {status}
    </header>
    <main>{children}</main>
  </div>
);
