import { apiClient } from "./client";
import type { Manual, ManualSummary } from "../types";

// The manuals this user may read: the server leaves out any their role may not.
export async function listManuals(): Promise<ManualSummary[]> {
  const { data } = await apiClient.get<ManualSummary[]>("/manuals");
  return data;
}

export async function getManual(slug: string): Promise<Manual> {
  const { data } = await apiClient.get<Manual>(`/manuals/${encodeURIComponent(slug)}`);
  return data;
}
