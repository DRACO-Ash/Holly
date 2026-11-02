// The console views' filter state: a set toggled one value at a time, and the time range.
import type { TimeRange } from "./ActivityTimeline";

const HOUR = 3_600_000;

// The set with `value` added, or taken out if it was in it.
export function toggled<T>(set: ReadonlySet<T>, value: T): Set<T> {
  const next = new Set(set);
  if (next.has(value)) next.delete(value);
  else next.add(value);
  return next;
}

// The time range a view filters to: the whole window, the last few hours, or a range dragged on
// the timeline.
export type RangeChoice = { hours: number } | { from: number; to: number } | null;

export function resolveRange(choice: RangeChoice, now: number): TimeRange | null {
  if (choice === null) return null;
  if ("hours" in choice) return [now - choice.hours * HOUR, now];
  return [choice.from, choice.to];
}

export function inRange(time: number | null, range: TimeRange | null): boolean {
  if (range === null) return true;
  return time !== null && time >= range[0] && time <= range[1];
}
