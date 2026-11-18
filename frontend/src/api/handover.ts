import { apiClient } from "./client";
import type {
  HandoverObjectList,
  HandoverStory,
  ObjectWatch,
  ObjectWatchList,
  StoryNote,
  ThreadLinkDecision,
} from "../types";

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

// The analyst's own watch list and "last looked" times, for the Object Lens.
export async function getWatch(): Promise<ObjectWatchList> {
  const { data } = await apiClient.get<ObjectWatchList>("/handover/watch");
  return data;
}

export async function setWatch(satNo: number, pinned: boolean): Promise<ObjectWatch> {
  const { data } = await apiClient.put<ObjectWatch>(`/handover/watch/${satNo}`, { pinned });
  return data;
}

export async function markSeen(satNo: number): Promise<ObjectWatch> {
  const { data } = await apiClient.post<ObjectWatch>(`/handover/watch/${satNo}/seen`);
  return data;
}
