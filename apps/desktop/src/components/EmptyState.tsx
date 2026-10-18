import { Card } from "./Card";

export const EmptyState = ({ title, hint }: { title: string; hint?: string }) => (
  <Card>
    <strong>{title}</strong>
    {hint && <p>{hint}</p>}
  </Card>
);
