import { Button } from "./Button";
import { Card } from "./Card";

export const ErrorState = ({ message, onRetry }: { message: string; onRetry?: () => void }) => (
  <Card tone="error" role="alert" className="stack">
    <strong>Something went wrong</strong>
    <p>{message}</p>
    {onRetry && <Button onClick={onRetry}>Retry</Button>}
  </Card>
);
