import type { HTMLAttributes } from "react";

export type BadgeProps = HTMLAttributes<HTMLSpanElement> & {
  tone?: "neutral" | "ok" | "warn" | "danger" | "info";
};

export const Badge = ({ tone = "neutral", className, ...p }: BadgeProps) => (
  <span {...p} className={`badge ${tone === "neutral" ? "" : tone} ${className ?? ""}`.trim()} />
);

// Status is never colour-only: every tone carries a glyph and a word.
const STATUS: Record<string, [BadgeProps["tone"], string]> = {
  active: ["ok", "✓ Active"],
  succeeded: ["ok", "✓ Succeeded"],
  partial: ["warn", "! Partial"],
  running: ["info", "… Running"],
  failed: ["danger", "✕ Failed"],
  stale: ["warn", "! Stale"],
  sufficient: ["ok", "✓ Sufficient"],
  no_evidence: ["neutral", "– No evidence"],
  source_failed: ["danger", "✕ Sync failed"],
};
export const StatusBadge = ({ status }: { status: string }) => {
  const [tone, text] = STATUS[status] ?? ["neutral", status];
  return <Badge tone={tone}>{text}</Badge>;
};
