import { useId, type ButtonHTMLAttributes, type InputHTMLAttributes, type ReactNode } from "react";

export const Button = (p: ButtonHTMLAttributes<HTMLButtonElement>) => (
  <button type="button" {...p} className="btn" />
);

export const Loading = ({ label = "Loading…" }: { label?: string }) => (
  <div className="state" role="status" aria-live="polite">
    {label}
  </div>
);
export const Empty = ({ title, hint }: { title: string; hint?: string }) => (
  <div className="state">
    <strong>{title}</strong>
    {hint && <p>{hint}</p>}
  </div>
);
export const ErrorState = ({ message, onRetry }: { message: string; onRetry?: () => void }) => (
  <div className="state error" role="alert">
    <strong>Something went wrong</strong>
    <p>{message}</p>
    {onRetry && <Button onClick={onRetry}>Retry</Button>}
  </div>
);
export const Stale = ({ since, children }: { since: string; children: ReactNode }) => (
  <div>
    <p className="pill">Showing data from {since}; may be out of date</p>
    {children}
  </div>
);
export const Partial = ({ missing, children }: { missing: string; children: ReactNode }) => (
  <div>
    <p className="pill">Partial: {missing} unavailable</p>
    {children}
  </div>
);

export function Field({
  label,
  error,
  ...rest
}: { label: string; error?: string } & InputHTMLAttributes<HTMLInputElement>) {
  const id = useId();
  return (
    <div className="field">
      <label htmlFor={id}>{label}</label>
      <input id={id} aria-invalid={!!error} aria-describedby={error ? `${id}-e` : undefined} {...rest} />
      {error && (
        <span id={`${id}-e`} className="err">
          {error}
        </span>
      )}
    </div>
  );
}
