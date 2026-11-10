import { useCallback, useEffect, useRef, useState } from "react";
import {
  addHandoverNote,
  decideThreadLink,
  deleteHandoverNote,
  getHandoverObjects,
  getHandoverStory,
} from "../api/handover";
import ObjectRail from "../components/handover/ObjectRail";
import StoryView from "../components/handover/StoryView";
import ConsoleHeader from "../components/ops/ConsoleHeader";
import { useNow } from "../components/ops/useNow";
import type { HandoverObjectList, HandoverStory, LinkDecision, ThreadSuggestion } from "../types";

const LOAD_FAILED = "Holly could not load the objects. Try again in a moment.";
const STORY_FAILED = "Holly could not load this object's story. Try again in a moment.";
const SAVE_FAILED = "Holly could not save that. Try again in a moment.";
const savedElsewhereFailed = (satNo: number) =>
  `Holly could not save that on object ${satNo}. Open it and try again.`;

// Handover: pick an object with a live event and read its whole story, from what Holly already
// holds, with where every item came from. Nothing here is sent outside Holly.
export default function Handover() {
  const now = useNow();
  const [list, setList] = useState<HandoverObjectList | null>(null);
  const [loadedAt, setLoadedAt] = useState<number | null>(null);
  const [selected, setSelected] = useState<number | null>(null);
  const [story, setStory] = useState<HandoverStory | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  // The object whose story was asked for last, so a slower answer for another is dropped.
  const wanted = useRef<number | null>(null);

  useEffect(() => {
    let live = true;
    getHandoverObjects()
      .then((data) => {
        if (!live) return;
        setList(data);
        setLoadedAt(Date.now());
      })
      .catch(() => live && setError(LOAD_FAILED));
    return () => {
      live = false;
    };
  }, []);

  const loadStory = useCallback(async (satNo: number) => {
    wanted.current = satNo;
    try {
      const data = await getHandoverStory(satNo);
      if (wanted.current === satNo) setStory(data);
    } catch {
      if (wanted.current === satNo) setError(STORY_FAILED);
    }
  }, []);

  const select = (satNo: number) => {
    setSelected(satNo);
    setStory(null);
    setError(null);
    void loadStory(satNo);
  };

  // Acts on the object whose story is on screen. Its story is read again afterwards only if it
  // is still the one wanted, so picking another object meanwhile is never undone; a failure is
  // always told, naming the object once another is picked.
  const act = async (satNo: number, work: () => Promise<unknown>) => {
    setBusy(true);
    setError(null);
    try {
      await work();
      if (wanted.current === satNo) await loadStory(satNo);
      return true;
    } catch {
      setError(wanted.current === satNo ? SAVE_FAILED : savedElsewhereFailed(satNo));
      return false;
    } finally {
      setBusy(false);
    }
  };

  const onScreen = story?.sat_no ?? null;
  const decide = (s: ThreadSuggestion, decision: LinkDecision) => {
    if (onScreen === null) return;
    const body = { thread_id: s.thread_id, event_key: s.event_key, decision };
    void act(onScreen, () => decideThreadLink(body));
  };
  const addNote = async (text: string) =>
    onScreen !== null && act(onScreen, () => addHandoverNote(onScreen, text.trim()));
  const deleteNote = (noteId: string) => {
    if (onScreen === null || !globalThis.confirm("Delete this note?")) return;
    void act(onScreen, () => deleteHandoverNote(noteId));
  };

  return (
    <div className="console-page">
      <ConsoleHeader
        eyebrow="Handover"
        title="Each object's story"
        loadedAt={loadedAt}
        refreshing={false}
        now={now}
      >
        Pick an object with a live event to see everything Holly holds about it, oldest first, with
        where each item came from. Confirm the chat threads that belong to it and add your own
        notes.
      </ConsoleHeader>
      {error && (
        <div className="form-error" role="alert">
          {error}
        </div>
      )}
      {list?.truncated && (
        <p className="console-truncated">
          The window holds more notices than this list reads: it shows the objects named by the
          newest.
        </p>
      )}
      {list === null && !error && <p className="muted">Loading the objects...</p>}
      {list?.objects.length === 0 && (
        <p className="console-empty">
          No notice in the last {list.window_hours} hours names an object.
        </p>
      )}
      {list && list.objects.length > 0 && (
        <div className="handover-grid">
          <ObjectRail objects={list.objects} selected={selected} onSelect={select} />
          <section className="console-panel" aria-label="Story">
            {selected === null && (
              <p className="console-empty">Pick an object to read its story.</p>
            )}
            {selected !== null && story === null && !error && (
              <p className="muted">Loading the story...</p>
            )}
            {story && (
              <StoryView
                story={story}
                now={now}
                busy={busy}
                onDecide={decide}
                onAddNote={addNote}
                onDeleteNote={deleteNote}
              />
            )}
          </section>
        </div>
      )}
    </div>
  );
}
