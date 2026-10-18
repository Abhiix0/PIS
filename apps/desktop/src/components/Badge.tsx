import type { HTMLAttributes } from "react";

export type BadgeProps = HTMLAttributes<HTMLSpanElement> & {
  tone?: "neutral" | "ok" | "warn" | "danger" | "info";
};

export const Badge = ({ tone = "neutral", className, ...p }: BadgeProps) => (
  <span {...p} className={`badge ${tone === "neutral" ? "" : tone} ${className ?? ""}`.trim()} />
);
