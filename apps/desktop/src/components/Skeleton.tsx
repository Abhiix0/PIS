import { Card } from "./Card";

export const Skeleton = ({ width = "100%" }: { width?: string }) => (
  <span className="skeleton" aria-hidden="true" style={{ width }} />
);

export const Loading = ({ label = "Loading…" }: { label?: string }) => (
  <Card role="status" aria-live="polite">
    {label}
    <Skeleton width="60%" />
  </Card>
);
