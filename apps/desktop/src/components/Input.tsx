import { useId, type InputHTMLAttributes } from "react";

export type InputProps = { label: string; error?: string } & InputHTMLAttributes<HTMLInputElement>;

export function Input({ label, error, ...rest }: InputProps) {
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
