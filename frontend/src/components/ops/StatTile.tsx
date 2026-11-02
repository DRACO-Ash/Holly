import type { ReactNode } from "react";

// A large count with its label. Given onToggle it is a filter button that says whether it is on.
export default function StatTile({
  count,
  label,
  detail,
  tone = "neutral",
  pressed,
  onToggle,
}: Readonly<{
  count: number | string;
  label: string;
  detail?: ReactNode;
  tone?: string;
  pressed?: boolean;
  onToggle?: () => void;
}>) {
  const body = (
    <>
      <span className="stat-count">{count}</span>
      <span className="stat-label">{label}</span>
      {detail && <span className="stat-detail">{detail}</span>}
    </>
  );
  if (!onToggle) return <div className={`stat-tile tone-${tone}`}>{body}</div>;
  return (
    <button
      type="button"
      className={`stat-tile stat-toggle tone-${tone}`}
      aria-pressed={pressed ?? false}
      onClick={onToggle}
    >
      {body}
    </button>
  );
}
