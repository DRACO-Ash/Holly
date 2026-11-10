import { useState, type FormEvent } from "react";
import type { HandoverStory, LinkDecision, ThreadSuggestion } from "../../types";
import { ENTRY_LABELS, storyEntries, type StoryEntry } from "../../utils/handover";
import { dayHeading, groupByDay, stampUtc } from "../../utils/ops";
import { KindGlyph } from "../ops/Badges";

function Entry({
  entry,
  onDeleteNote,
}: Readonly<{ entry: StoryEntry; onDeleteNote: (key: string) => void }>) {
  return (
    <li className={`story-entry story-${entry.type}`}>
      <span className="story-time mono">
        {entry.at === null ? "time unknown" : stampUtc(entry.at)}
      </span>
      <div className="story-body">
        <p className="story-title">
          {entry.kind && <KindGlyph kind={entry.kind} />}
          <span className={`story-type story-type-${entry.type}`}>{ENTRY_LABELS[entry.type]}</span>
          <span>{entry.title}</span>
        </p>
        {entry.detail && <p className="story-detail">{entry.detail}</p>}
        <p className="story-source">
          <span>Source: {entry.source}</span>
          {entry.type === "note" && (
            <button type="button" className="link-button" onClick={() => onDeleteNote(entry.key)}>
              Delete note
            </button>
          )}
        </p>
      </div>
    </li>
  );
}

function Suggestion({
  suggestion,
  busy,
  onDecide,
}: Readonly<{
  suggestion: ThreadSuggestion;
  busy: boolean;
  onDecide: (s: ThreadSuggestion, d: LinkDecision) => void;
}>) {
  const post = suggestion.first_post;
  const more = suggestion.matching_posts - 1;
  return (
    <li className="handover-suggestion">
      <p className="story-title">
        <span className="story-type story-type-post">Chat</span>
        <span>
          {suggestion.reason} · {suggestion.channel_name ?? "channel"}
        </span>
      </p>
      <p className="story-detail">
        <span className="mono">{stampUtc(Date.parse(post.posted_at))}</span>{" "}
        {post.author ?? "Unknown"}: {post.message}
      </p>
      {more > 0 && <p className="console-hint">and {more} more matching in this thread</p>}
      <div className="handover-actions">
        <button type="button" disabled={busy} onClick={() => onDecide(suggestion, "confirmed")}>
          Confirm this thread
        </button>
        <button type="button" disabled={busy} onClick={() => onDecide(suggestion, "rejected")}>
          Not this one
        </button>
      </div>
    </li>
  );
}

function NoteForm({ onAdd }: Readonly<{ onAdd: (text: string) => Promise<boolean> }>) {
  const [text, setText] = useState("");
  const [saving, setSaving] = useState(false);
  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (!text.trim()) return;
    setSaving(true);
    if (await onAdd(text)) setText("");
    setSaving(false);
  };
  return (
    <form className="handover-note-form" onSubmit={(e) => void submit(e)}>
      <label htmlFor="handover-note">Add a note to this object&apos;s story</label>
      <textarea
        id="handover-note"
        value={text}
        onChange={(e) => setText(e.target.value)}
        maxLength={4000}
        rows={3}
      />
      <button type="submit" disabled={saving || !text.trim()}>
        {saving ? "Saving..." : "Add note"}
      </button>
    </form>
  );
}

// One object's story: suggested threads to decide on, then every item in time order, newest
// day first, each with its source, then the notes form.
export default function StoryView({
  story,
  now,
  busy,
  onDecide,
  onAddNote,
  onDeleteNote,
}: Readonly<{
  story: HandoverStory;
  now: number;
  busy: boolean;
  onDecide: (s: ThreadSuggestion, d: LinkDecision) => void;
  onAddNote: (text: string) => Promise<boolean>;
  onDeleteNote: (noteId: string) => void;
}>) {
  const entries = storyEntries(story);
  const days = groupByDay(entries, (e) => e.at);
  const deleteByKey = (key: string) => onDeleteNote(key.replace(/^note-/, ""));
  return (
    <div className="handover-story">
      <header className="console-panel-head">
        <h2>
          {story.name ?? "Unnamed object"} <span className="mono">({story.sat_no})</span>
        </h2>
        <p className="console-hint">
          {story.notices.length} notice publications, {story.maneuvers.length} provider records in
          the last {story.window_hours} hours; {story.threads.length} confirmed threads and{" "}
          {story.notes.length} notes.
        </p>
      </header>
      {story.truncated && (
        <p className="console-truncated">
          Holly holds more about this object than this view carries: part of it is shown.
        </p>
      )}
      {story.suggestions.length > 0 && (
        <section className="console-panel" aria-labelledby="handover-suggestions-title">
          <h3 id="handover-suggestions-title">Threads that may belong here</h3>
          <p className="console-hint">
            Holly found these by NOTSO or catalogue number. Only a thread you confirm joins the
            story.
          </p>
          <ul className="handover-suggestions">
            {story.suggestions.map((s) => (
              <Suggestion key={s.thread_id} suggestion={s} busy={busy} onDecide={onDecide} />
            ))}
          </ul>
        </section>
      )}
      {story.timers.length > 0 && (
        <section className="console-panel" aria-labelledby="handover-timers-title">
          <h3 id="handover-timers-title">Timers set</h3>
          <ul className="handover-timers">
            {story.timers.map((t) => (
              <li key={t.id}>
                <span className="mono">{stampUtc(Date.parse(t.target_time))}</span> {t.label}
              </li>
            ))}
          </ul>
        </section>
      )}
      {entries.length === 0 ? (
        <p className="console-empty">Nothing held about this object in the window.</p>
      ) : (
        days.map(({ day, items }) => (
          <section key={day ?? "unknown"} className="event-day">
            <h3 className="event-day-heading">
              {day === null ? "Time unknown" : dayHeading(day, now)}
            </h3>
            <ol className="story-list">
              {items.map((entry) => (
                <Entry key={entry.key} entry={entry} onDeleteNote={deleteByKey} />
              ))}
            </ol>
          </section>
        ))
      )}
      <NoteForm onAdd={onAddNote} />
    </div>
  );
}
