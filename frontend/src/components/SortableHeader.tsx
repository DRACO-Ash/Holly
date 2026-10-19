import type { SortDirection } from "../types";

type Props<C extends string> = Readonly<{
  column: C;
  label: string;
  activeColumn: C;
  activeDirection: SortDirection;
  onChange: (column: C) => void;
}>;

const INDICATOR: Record<SortDirection, string> = { asc: "▲", desc: "▼" };
const ARIA_SORT: Record<SortDirection, "ascending" | "descending"> = {
  asc: "ascending",
  desc: "descending",
};

// aria-sort sits on the column header, and only on the column the list is sorted by.
export default function SortableHeader<C extends string>({
  column,
  label,
  activeColumn,
  activeDirection,
  onChange,
}: Props<C>) {
  const isActive = activeColumn === column;
  return (
    <th aria-sort={isActive ? ARIA_SORT[activeDirection] : undefined}>
      <button
        type="button"
        className={isActive ? "sort-header active" : "sort-header"}
        onClick={() => onChange(column)}
      >
        {label}
        <span className="sort-indicator">{isActive ? INDICATOR[activeDirection] : ""}</span>
      </button>
    </th>
  );
}
