import type { ReactNode } from "react";

export const PageHeader = ({
  title,
  sub,
  actions,
}: {
  title: string;
  sub?: ReactNode;
  actions?: ReactNode;
}) => (
  <div className="page-head">
    <div>
      <h1>{title}</h1>
      {sub && <p>{sub}</p>}
    </div>
    {actions}
  </div>
);
