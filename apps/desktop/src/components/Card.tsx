import type { HTMLAttributes } from "react";

export type CardProps = HTMLAttributes<HTMLElement> & { tone?: "default" | "info" | "error" };

export const Card = ({ tone = "default", className, ...p }: CardProps) => (
  <section {...p} className={`card ${tone === "default" ? "" : tone} ${className ?? ""}`.trim()} />
);
