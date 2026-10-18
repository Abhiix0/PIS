import type { TableHTMLAttributes } from "react";

export const Table = ({ className, ...p }: TableHTMLAttributes<HTMLTableElement>) => (
  <table {...p} className={`tbl ${className ?? ""}`.trim()} />
);
