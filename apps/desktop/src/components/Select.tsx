import { useId, type SelectHTMLAttributes } from "react";

export type SelectProps = { label: string; error?: string } & SelectHTMLAttributes<HTMLSelectElement>;

export function Select({ label, error, children, ...rest }: SelectProps) {
  const id = useId();
  return (
    <div className="field">
      <label htmlFor={id}>{label}</label>
      <select id={id} aria-invalid={!!error} aria-describedby={error ? `${id}-e` : undefined} {...rest}>
        {children}
      </select>
      {error && (
        <span id={`${id}-e`} className="err">
          {error}
        </span>
      )}
    </div>
  );
}
