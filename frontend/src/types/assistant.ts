export type ActionUrgency = "high" | "medium" | "low";

export interface ApplicableProcedure {
  procedure_id: string | null;
  name: string;
  reason: string;
}

export interface NextAction {
  action: string;
  // An ActionUrgency as a rule; the server types it as any string.
  urgency: string;
  deadline: string | null;
  rationale: string;
}

export interface StructuredEvaluation {
  summary: string;
  applicable_procedures: ApplicableProcedure[];
  next_actions: NextAction[];
  open_questions: string[];
}

export interface AssistantEvaluation {
  id: string;
  notification_id: string;
  summary: string;
  structured: StructuredEvaluation;
  procedures_used: string[];
  model: string;
  error: string | null;
  evaluated_at: string;
}

export type FeedUrgency = "high" | "medium" | "low" | "none" | "pending";

export interface AssistantFeedItem {
  notification: import("./notification").Notification;
  evaluation: AssistantEvaluation | null;
  // A FeedUrgency as a rule; the server types it as any string.
  urgency: string;
  top_action: string | null;
  event_summary: string | null;
  event_publication_count: number | null;
  event_key: string | null;
  // False when the notice's classification marking keeps it from the assistant.
  assistant_cleared: boolean;
}

export interface AssistantFeed {
  items: AssistantFeedItem[];
  window_hours: number;
}
