export interface ManualSummary {
  slug: string;
  title: string;
}

export interface Manual extends ManualSummary {
  markdown: string;
}
