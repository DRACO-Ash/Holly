import { apiClient } from "./client";
import type { HandoverObjectList, HandoverStory, StoryNote, ThreadLinkDecision } from "../types";

const windowParams = (hours?: number) => (hours === undefined ? {} : { hours });

export async function getHandoverObjects(hours?: number): Promise<HandoverObjectList> {
  const { data } = await apiClient.get<HandoverObjectList>("/handover/objects", {
    params: windowParams(hours),
  });
  return data;
}

export async function getHandoverStory(satNo: number, hours?: number): Promise<HandoverStory> {
  const { data } = await apiClient.get<HandoverStory>(`/handover/objects/${satNo}`, {
    params: windowParams(hours),
  });
  return data;
}

export async function decideThreadLink(decision: ThreadLinkDecision): Promise<ThreadLinkDecision> {
  const { data } = await apiClient.post<ThreadLinkDecision>("/handover/thread-links", decision);
  return data;
}

export async function addHandoverNote(satNo: number, text: string): Promise<StoryNote> {
  const { data } = await apiClient.post<StoryNote>(`/handover/objects/${satNo}/notes`, { text });
  return data;
}

export async function deleteHandoverNote(noteId: string): Promise<void> {
  await apiClient.delete(`/handover/notes/${noteId}`);
}
