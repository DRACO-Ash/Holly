import type { RangeChoice } from "./consoleFilters";

const PRESETS = [6, 24, 72] as const;
const LABELS: Readonly<Record<(typeof PRESETS)[number], string>> = {
  6: "Last 6 h",
  24: "Last 24 h",
  72: "Last 3 days",
};

// The range by keyboard. A range dragged on the timeline shows here as custom, to clear.
export default function RangeButtons({
  choice,
  onChoose,
}: Readonly<{ choice: RangeChoice; onChoose: (choice: RangeChoice) => void }>) {
  const hours = choice !== null && "hours" in choice ? choice.hours : null;
  return (
    <fieldset className="segmented range-buttons">
      <legend className="visually-hidden">Time range</legend>
      <button type="button" aria-pressed={choice === null} onClick={() => onChoose(null)}>
        Whole window
      </button>
      {PRESETS.map((preset) => (
        <button
          key={preset}
          type="button"
          aria-pressed={hours === preset}
          onClick={() => onChoose({ hours: preset })}
        >
          {LABELS[preset]}
        </button>
      ))}
      {choice !== null && "from" in choice && (
        <button type="button" aria-pressed="true" onClick={() => onChoose(null)}>
          Dragged range: clear
        </button>
      )}
    </fieldset>
  );
}
