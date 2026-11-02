import type { ActivityOverview } from "../../types";

// Says when the overview carries only the newest part of the window, so a count is never
// taken for the whole.
export default function Truncation({ data }: Readonly<{ data: ActivityOverview }>) {
  const cut = [
    data.truncated.notices && "notices",
    data.truncated.maneuvers && "maneuvers",
    data.truncated.elsets && "element sets",
  ].filter((part): part is string => Boolean(part));
  if (cut.length === 0) return null;
  return (
    <p className="console-truncated">
      The window holds more {cut.join(" and ")} than this view carries: it shows the newest, and its
      counts cover only those.
    </p>
  );
}
