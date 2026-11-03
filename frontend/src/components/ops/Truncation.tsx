import type { ActivityOverview } from "../../types";

// Says when the overview carries only part of the window, so a count is never taken for the
// whole. Notices and maneuvers are cut to the newest; element sets to the satellites with the
// lowest catalogue numbers.
export default function Truncation({ data }: Readonly<{ data: ActivityOverview }>) {
  const cut = [data.truncated.notices && "notices", data.truncated.maneuvers && "maneuvers"].filter(
    (part): part is string => Boolean(part),
  );
  return (
    <>
      {cut.length > 0 && (
        <p className="console-truncated">
          The window holds more {cut.join(" and ")} than this view carries: it shows the newest, and
          its counts cover only those.
        </p>
      )}
      {data.truncated.elsets && (
        <p className="console-truncated">
          The window names more satellites than this view carries element sets for: those with the
          lowest catalogue numbers have one, and a regime may be missing for the rest.
        </p>
      )}
    </>
  );
}
