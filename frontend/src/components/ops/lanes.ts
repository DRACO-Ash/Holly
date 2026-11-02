// The timeline's lanes for each view: notices by kind or by urgency, maneuvers by source.
import type { ActivityNotice } from "../../types";
import {
  EVENT_KINDS,
  type EventKind,
  KIND_LABELS,
  type ManeuverGroup,
  type ParsedEvent,
  URGENCY_LABELS,
  URGENCY_ORDER,
  maneuverStart,
  stampUtc,
  timeOf,
  urgencyOf,
} from "../../utils/ops";
import type { MarkShape, TimelineLane, TimelineMark } from "./ActivityTimeline";

export const KIND_SHAPES: Readonly<Record<EventKind, MarkShape>> = {
  maneuver: "dot",
  photometric: "square",
  rpo: "diamond",
  launch: "triangle",
  cancelled: "ring",
  other: "bar",
};

export function noticeTitle(notice: ActivityNotice, parsed: ParsedEvent | null): string {
  const objects = parsed?.objects.map((o) => (o.id ? `${o.name} (${o.id})` : o.name)).join(" vs ");
  return objects || notice.event_class || notice.notice || "Notice";
}

function noticeMark(
  notice: ActivityNotice,
  parsed: ParsedEvent | null,
  time: number,
): TimelineMark {
  const kind = parsed?.kind ?? "other";
  const urgency = urgencyOf(notice.urgency);
  return {
    id: notice.id,
    time,
    tone: kind,
    shape: KIND_SHAPES[kind],
    label: `${parsed?.kindLabel ?? KIND_LABELS[kind]}: ${noticeTitle(notice, parsed)}, ${stampUtc(time)}`,
    emphasis: urgency === "high" || urgency === "medium",
  };
}

// One lane per kind present, in the kinds' fixed order.
export function noticeLanesByKind(
  notices: readonly ActivityNotice[],
  parsedOf: (notice: ActivityNotice) => ParsedEvent | null,
): TimelineLane[] {
  const lanes = new Map<EventKind, TimelineMark[]>();
  for (const notice of notices) {
    const time = timeOf(notice.udl_created_at);
    if (time === null) continue;
    const parsed = parsedOf(notice);
    const kind = parsed?.kind ?? "other";
    const marks = lanes.get(kind) ?? [];
    marks.push(noticeMark(notice, parsed, time));
    lanes.set(kind, marks);
  }
  return EVENT_KINDS.filter((kind) => lanes.has(kind)).map((kind) => ({
    key: kind,
    label: KIND_LABELS[kind],
    tone: kind,
    marks: lanes.get(kind) ?? [],
  }));
}

// One lane per urgency present, most urgent first; each mark keeps its kind's hue and shape.
export function noticeLanesByUrgency(
  notices: readonly ActivityNotice[],
  parsedOf: (notice: ActivityNotice) => ParsedEvent | null,
): TimelineLane[] {
  const lanes = new Map<string, TimelineMark[]>();
  for (const notice of notices) {
    const time = timeOf(notice.udl_created_at);
    if (time === null) continue;
    const urgency = urgencyOf(notice.urgency);
    const marks = lanes.get(urgency) ?? [];
    marks.push(noticeMark(notice, parsedOf(notice), time));
    lanes.set(urgency, marks);
  }
  return URGENCY_ORDER.filter((u) => lanes.has(u)).map((u) => ({
    key: u,
    label: URGENCY_LABELS[u],
    tone: u,
    marks: lanes.get(u) ?? [],
  }));
}

// One lane per source provider, alphabetically, in the provider's hue.
export function maneuverLanes(
  groups: readonly ManeuverGroup[],
  slots: ReadonlyMap<string, number>,
  nameOf: (satNo: number | null) => string,
): TimelineLane[] {
  const lanes = new Map<string, TimelineMark[]>();
  for (const group of groups) {
    const time = maneuverStart(group.maneuver);
    if (time === null) continue;
    const source = group.maneuver.source ?? "Unknown";
    const marks = lanes.get(source) ?? [];
    marks.push({
      id: group.maneuver.id,
      time,
      tone: `source-${slots.get(source) ?? 4}`,
      shape: "dot",
      label: `${nameOf(group.maneuver.sat_no)}, ${source}, ${stampUtc(time)}`,
    });
    lanes.set(source, marks);
  }
  return [...lanes.keys()]
    .sort((a, b) => a.localeCompare(b))
    .map((source) => ({
      key: source,
      label: source,
      tone: `source-${slots.get(source) ?? 4}`,
      marks: lanes.get(source) ?? [],
    }));
}
