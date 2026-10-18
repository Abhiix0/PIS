import type { ButtonHTMLAttributes } from "react";

export type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "accent" | "ghost";
};

export const Button = ({ variant = "primary", className, ...p }: ButtonProps) => (
  <button
    type="button"
    {...p}
    className={`btn ${variant === "primary" ? "" : variant} ${className ?? ""}`.trim()}
  />
);
