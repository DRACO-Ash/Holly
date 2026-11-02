export interface ActiveFilter {
  key: string;
  label: string;
  onRemove: () => void;
}

// The filters in force, each a button that removes it, and one that clears them all.
export default function FilterChips({
  filters,
  onClear,
}: Readonly<{ filters: readonly ActiveFilter[]; onClear: () => void }>) {
  if (filters.length === 0) return null;
  return (
    <ul className="filter-chips" aria-label="Filters in force">
      {filters.map((filter) => (
        <li key={filter.key}>
          <button type="button" className="filter-chip" onClick={filter.onRemove}>
            {filter.label}
            <span aria-hidden="true">×</span>
            <span className="visually-hidden">: remove this filter</span>
          </button>
        </li>
      ))}
      {filters.length > 1 && (
        <li>
          <button type="button" className="filter-chip" onClick={onClear}>
            Clear all
          </button>
        </li>
      )}
    </ul>
  );
}
