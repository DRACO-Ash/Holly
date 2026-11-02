import { apiClient } from "./client";
import type { ActivityOverview } from "../types";

export async function getActivity(hours?: number): Promise<ActivityOverview> {
  const { data } = await apiClient.get<ActivityOverview>("/activity", {
    params: hours === undefined ? {} : { hours },
  });
  return data;
}
