import type { ReactNode } from "react";

export type BannerProps = { tone?: "info" | "warn" | "danger"; children: ReactNode };

export const Banner = ({ tone = "info", children }: BannerProps) => (
  <p
    className={`banner ${tone === "info" ? "" : tone}`.trim()}
    role={tone === "danger" ? "alert" : undefined}
  >
    {children}
  </p>
);

export const Stale = ({ since, children }: { since: string; children: ReactNode }) => (
  <div>
    <Banner tone="warn">Showing data from {since}; may be out of date</Banner>
    {children}
  </div>
);
export const Partial = ({ missing, children }: { missing: string; children: ReactNode }) => (
  <div>
    <Banner tone="warn">Partial: {missing} unavailable</Banner>
    {children}
  </div>
);
