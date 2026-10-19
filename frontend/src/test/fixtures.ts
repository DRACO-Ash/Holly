// Synthetic records for the dashboard's tests, built to the API's types. Every value is made up
// for the tests; none is drawn from a real notice, satellite, analyst or event.
import type {
  AssistantEvaluation,
  AssistantFeedItem,
  EventTimer,
  NotificationDetail,
  User,
} from "../types";

export function aUser(overrides: Partial<User> = {}): User {
  return {
    id: "user-1",
    username: "test.analyst",
    email: null,
    role: "analyst",
    is_active: true,
    created_at: "2026-01-01T00:00:00Z",
    ...overrides,
  };
}

export function aNotification(overrides: Partial<NotificationDetail> = {}): NotificationDetail {
  return {
    id: "n-1",
    udl_id: "udl-test-1",
    msg_type: "TACREP_NOTSO",
    data_mode: "TEST",
    source: "test-source",
    classification_marking: "U",
    created_by: "test.creator",
    orig_network: "test-network",
    udl_created_at: "2026-01-02T03:04:05Z",
    notso_identifier: "NOTSO-TEST-1",
    notice_id: "NOTICE-TEST-1",
    event_id: "EVENT-TEST-1",
    event_class: "Test event class",
    event_type: "other",
    status: "OPEN",
    subject: "Synthetic subject",
    description: null,
    region: "Test region",
    notso_link: null,
    company_name: "Test author",
    publish_date: "2026-01-02T03:00:00Z",
    effective_from: "2026-01-02T04:00:00Z",
    effective_until: null,
    sat_no: 90001,
    sat_ids: null,
    created_at: "2026-01-02T03:05:00Z",
    updated_at: "2026-01-02T03:05:00Z",
    raw: { synthetic: true },
    ...overrides,
  };
}

export function anEvaluation(overrides: Partial<AssistantEvaluation> = {}): AssistantEvaluation {
  return {
    id: "eval-1",
    notification_id: "n-1",
    summary: "Synthetic plain summary",
    structured: {
      summary: "Synthetic structured summary",
      applicable_procedures: [],
      next_actions: [],
      open_questions: [],
    },
    procedures_used: [],
    model: "test-model",
    error: null,
    evaluated_at: "2026-01-02T05:06:07Z",
    ...overrides,
  };
}

export function aFeedItem(overrides: Partial<AssistantFeedItem> = {}): AssistantFeedItem {
  return {
    notification: aNotification(),
    evaluation: null,
    urgency: "none",
    top_action: null,
    event_summary: null,
    event_publication_count: null,
    event_key: null,
    assistant_cleared: true,
    ...overrides,
  };
}

// A timer whose target is `minutesAhead` from now (negative for one already due).
export function aTimer(minutesAhead: number, overrides: Partial<EventTimer> = {}): EventTimer {
  return {
    id: "timer-1",
    event_key: null,
    label: "Synthetic timer",
    target_time: new Date(Date.now() + minutesAhead * 60_000).toISOString(),
    pre_alert_minutes: 5,
    recurrence: "none",
    pre_alert_fired_at: null,
    dismissed_at: null,
    dismissed_by: null,
    created_by: null,
    shift_date: null,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    ...overrides,
  };
}
