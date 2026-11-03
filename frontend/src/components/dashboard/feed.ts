// The dashboard's reading of the assistant feed: its urgency buckets, the satellites each item
// names, and the filters the band, the timeline and the board apply to it.
import type { TimeRange } from "../ops/ActivityTimeline";
import { inRange } from "../ops/consoleFilters";
import type { ActivityNotice, AssistantFeedItem } from "../../types";
import { URGENCY_ORDER, type Urgency, timeOf, urgencyOf } from "../../utils/ops";

export function formatWindow(hours: number): string {
  if (hours > 0 && hours % 24 === 0) {
    const days = hours / 24;
    return days === 1 ? "1 day" : `${days} days`;
  }
  return hours === 1 ? "1 hour" : `${hours} hours`;
}

export function feedBuckets(
  items: readonly AssistantFeedItem[],
): Map<Urgency, AssistantFeedItem[]> {
  const buckets = new Map<Urgency, AssistantFeedItem[]>(URGENCY_ORDER.map((u) => [u, []]));
  for (const item of items) buckets.get(urgencyOf(item.urgency))?.push(item);
  return buckets;
}

export function feedSatIds(item: AssistantFeedItem): string[] {
  const n = item.notification;
  if (n.sat_ids && n.sat_ids.length > 0) return n.sat_ids;
  return n.sat_no === null ? [] : [String(n.sat_no)];
}

// A feed item in the activity overview's shape, so the shared rows' helpers read it.
export function asActivityNotice(item: AssistantFeedItem): ActivityNotice {
  const n = item.notification;
  return {
    id: n.id,
    notice: n.notso_identifier ?? n.notice_id,
    event_class: n.event_class,
    event_type: n.event_type,
    status: n.status,
    region: n.region,
    udl_created_at: n.udl_created_at,
    sat_ids: feedSatIds(item),
    urgency: item.urgency,
    top_action: item.top_action,
  };
}

export interface FeedFilter {
  urgencies: ReadonlySet<Urgency>;
  range: TimeRange | null;
  satellite: string | null;
}

export function keepItem(item: AssistantFeedItem, filter: FeedFilter): boolean {
  if (filter.urgencies.size > 0 && !filter.urgencies.has(urgencyOf(item.urgency))) return false;
  if (!inRange(timeOf(item.notification.udl_created_at), filter.range)) return false;
  return filter.satellite === null || feedSatIds(item).includes(filter.satellite);
}
