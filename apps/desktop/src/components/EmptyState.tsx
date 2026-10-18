import type { ReactNode } from "react";
import { Card } from "./Card";

export const EmptyState = ({
  title,
  hint,
  children,
}: {
  title: string;
  hint?: string;
  children?: ReactNode;
}) => (
  <Card className="stack">
    <strong>{title}</strong>
    {hint && <p>{hint}</p>}
    {children}
  </Card>
);
