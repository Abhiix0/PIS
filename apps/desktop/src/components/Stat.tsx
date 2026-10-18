import type { ReactNode } from "react";
import { Card } from "./Card";

export type StatProps = { label: string; value: string | number; hint?: ReactNode };

export const Stat = ({ label, value, hint }: StatProps) => (
  <dl className="stat">
    <dt>{label}</dt>
    <dd>{value}</dd>
    {hint && <dd className="hint">{hint}</dd>}
  </dl>
);

export const StatCard = ({ small, ...p }: StatProps & { small?: boolean }) => (
  <Card className={`statcard ${small ? "sm" : ""}`.trim()}>
    <Stat {...p} />
  </Card>
);
