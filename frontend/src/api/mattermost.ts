import { apiClient } from "./client";
import type {
  MattermostChannel,
  MattermostChannels,
  MattermostListQuery,
  MattermostMessagePage,
  MattermostSweepResult,
} from "../types";

export async function listMattermostMessages(
  query: MattermostListQuery = {},
): Promise<MattermostMessagePage> {
  const { data } = await apiClient.get<MattermostMessagePage>("/mattermost/messages", {
    params: query,
    // Several channels go as channel_id=a&channel_id=b, as the server reads them.
    paramsSerializer: { indexes: null },
  });
  return data;
}

// With `since`, the user's last visit, each channel also counts the messages after it.
export async function listChannels(since?: string): Promise<MattermostChannels> {
  const { data } = await apiClient.get<MattermostChannels>(
    "/mattermost/channels",
    since ? { params: { since } } : undefined,
  );
  return data;
}

export async function updateChannel(
  channelId: string,
  change: { following?: boolean; reviewed?: true },
): Promise<MattermostChannel> {
  const { data } = await apiClient.patch<MattermostChannel>(
    `/mattermost/channels/${encodeURIComponent(channelId)}`,
    change,
  );
  return data;
}

export async function reviewAllChannels(): Promise<number> {
  const { data } = await apiClient.post<{ reviewed: number }>("/mattermost/channels/reviewed");
  return data.reviewed;
}

export async function sweepNow(): Promise<MattermostSweepResult> {
  const { data } = await apiClient.post<MattermostSweepResult>("/mattermost/sweep");
  return data;
}
