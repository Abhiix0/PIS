export type StatProps = { label: string; value: string | number };

export const Stat = ({ label, value }: StatProps) => (
  <dl className="stat">
    <dt>{label}</dt>
    <dd>{value}</dd>
  </dl>
);
