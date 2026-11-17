// The lens: one object's story over whatever page is open. It reads the V0.19 story
// (/handover/objects/{sat_no}) and nothing else, so it shows only what Holly already shows.
import { useEffect, useMemo, useRef, useState, type FormEvent, type KeyboardEvent } from "react";
import { useNavigate } from "react-router-dom";
import { createEventTimer } from "../../api/event_timers";
import { addHandoverNote, getHandoverStory } from "../../api/handover";
import { useNow } from "../../components/ops/useNow";
import type { HandoverStory } from "../../types";
import { ENTRY_LABELS, storyEntries, type StoryEntry } from "../../utils/handover";
import { parseEventClass, stampUtc } from "../../utils/ops";
import { useLens } from "./LensContext";
import { Linkify } from "./Linkify";

const H = 3_600_000;

interface Item {
  key: string;
  at: number | null;
  tag: string;
  tone: string;
  title: string;
  detail: string | null;
  source: string;
}

const TONES: Record<StoryEntry["type"], string> = {
  notice: "var(--kind-rpo)",
  maneuver: "var(--source-1)",
  post: "var(--channel-3)",
  note: "var(--amber)",
};

function items(story: HandoverStory): Item[] {
  const fromEntries = storyEntries(story).map((e) => ({
    key: e.key, at: e.at, tag: ENTRY_LABELS[e.type], tone: TONES[e.type], title: e.title, detail: e.detail, source: e.source,
  }));
  const fromSuggestions = story.suggestions.map((s) => ({
    key: `suggested-${s.thread_id}`, at: Date.parse(s.first_post.posted_at), tag: "Chat", tone: "var(--channel-1)",
    title: `${s.first_post.author ?? "Unknown"} in #${s.channel_name ?? "channel"}`, detail: s.first_post.message,
    source: `Mattermost · suggested thread, not confirmed${s.matching_posts > 1 ? ` · ${s.matching_posts} matching` : ""}`,
  }));
  return [...fromEntries, ...fromSuggestions].sort((a, b) => (b.at ?? 0) - (a.at ?? 0));
}

function countdown(ms: number): string {
  const s = Math.max(0, Math.floor(ms / 1000));
  const hh = Math.floor(s / 3600);
  const mm = String(Math.floor((s % 3600) / 60)).padStart(2, "0");
  const ss = String(s % 60).padStart(2, "0");
  return `${hh}:${mm}:${ss}`;
}

function Lanes({ story, now, seenAt }: Readonly<{ story: HandoverStory; now: number; seenAt: number }>) {
  const start = Date.parse(story.window_start);
  const soonest = story.timers.map((t) => Date.parse(t.target_time)).filter((t) => t > now);
  const end = Math.max(now + 6 * H, ...soonest.map((t) => t + H));
  const x = (t: number) => `${Math.min(100, Math.max(0, ((t - start) / (end - start)) * 100))}%`;
  const dot = (key: string, t: number, color: string, shape = "", title = "") => (
    <span key={key} className={`lx-dot ${shape}`} style={{ left: x(t), background: color }} title={title} />
  );
  const posts = story.threads.flatMap((th) => th.posts.map((p) => ({ ...p, channel: th.channel_name })));
  const lanes: Array<[string, JSX.Element[]]> = [
    ["NOTSO", story.notices.filter((n) => n.udl_created_at).map((n) => dot(n.id, Date.parse(n.udl_created_at!), "var(--kind-rpo)", "dm", n.notice ?? ""))],
    ["Provider", story.maneuvers.filter((m) => m.event_start_time).map((m) =>
      dot(m.id, Date.parse(m.event_start_time!), m.source === "PROVIDER-B" ? "var(--source-2)" : "var(--source-1)", "", m.source ?? ""))],
    ["Chat", [
      ...posts.map((p) => dot(p.post_id, Date.parse(p.posted_at), "var(--channel-3)", "sq", p.author ?? "")),
      ...story.suggestions.map((s) => dot(`s-${s.thread_id}`, Date.parse(s.first_post.posted_at), "transparent", "sq hollow", "suggested")),
    ]],
    ["Notes", story.notes.map((n) => dot(n.id, Date.parse(n.created_at), "var(--amber)", "sq", n.author ?? ""))],
    ["Timers", story.timers.map((t) => dot(t.id, Date.parse(t.target_time), "var(--amber)", "dm", t.label))],
  ];
  const days: number[] = [];
  for (let d = Math.ceil(start / (24 * H)) * 24 * H; d < end; d += 24 * H) days.push(d);
  return (
    <div className="lx-lanes" aria-hidden="true">
      {lanes.map(([name, dots]) => (
        <div className="lx-lane" key={name}>
          <span className="lx-lane-name">{name}</span>
          <div className="lx-track">
            {days.map((d) => <span key={d} className="lx-tick" style={{ left: x(d) }} />)}
            {dots}
            <span className="lx-seen" style={{ left: x(seenAt) }} />
            <span className="lx-now" style={{ left: x(now) }} />
          </div>
        </div>
      ))}
      <div className="lx-axis">
        <span />
        <div className="lx-axis-track">
          {days.map((d) => (
            <span key={d} style={{ left: x(d) }}>
              {new Date(d).toISOString().slice(8, 10)} {new Date(d).toUTCString().slice(8, 11)}
            </span>
          ))}
        </div>
      </div>
    </div>
  );
}

function ItemRow({ item, fresh }: Readonly<{ item: Item; fresh: boolean }>) {
  return (
    <li className="lx-item">
      <time>{item.at === null ? "time unknown" : stampUtc(item.at)}</time>
      <div>
        <p className="lx-item-title">
          <span className="lx-src" style={{ color: item.tone, borderColor: item.tone }}>{item.tag}</span>
          <Linkify text={item.title} />
          {fresh && <span className="lx-new">NEW</span>}
        </p>
        {item.detail && <p className="lx-item-detail"><Linkify text={item.detail} /></p>}
        <p className="lx-item-source">Source: {item.source}</p>
      </div>
    </li>
  );
}

function NoteForm({ satNo, done }: Readonly<{ satNo: number; done: () => void }>) {
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (!text.trim()) return;
    setBusy(true);
    await addHandoverNote(satNo, text.trim());
    setBusy(false);
    done();
  };
  return (
    <form className="lx-form" onSubmit={(e) => void submit(e)}>
      <label htmlFor="lx-note">Note on this object</label>
      <textarea id="lx-note" rows={2} value={text} onChange={(e) => setText(e.target.value)} autoFocus />
      <button type="submit" className="lx-btn pri" disabled={busy || !text.trim()}>Add note</button>
    </form>
  );
}

function TimerForm({ story, done }: Readonly<{ story: HandoverStory; done: () => void }>) {
  const [label, setLabel] = useState(`Check ${story.name ?? story.sat_no} (${story.sat_no})`);
  const [minutes, setMinutes] = useState(60);
  const [busy, setBusy] = useState(false);
  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    await createEventTimer({
      label, target_time: new Date(Date.now() + minutes * 60_000).toISOString(),
      event_key: story.notices[0]?.event_key ?? null, pre_alert_minutes: 15,
    });
    setBusy(false);
    done();
  };
  return (
    <form className="lx-form lx-form-row" onSubmit={(e) => void submit(e)}>
      <label>Timer<input value={label} onChange={(e) => setLabel(e.target.value)} autoFocus /></label>
      <label>In minutes<input type="number" min={1} max={2880} value={minutes} onChange={(e) => setMinutes(Number(e.target.value))} /></label>
      <button type="submit" className="lx-btn pri" disabled={busy || !label.trim()}>Set timer</button>
    </form>
  );
}

export default function LensDrawer({ satNo }: Readonly<{ satNo: number }>) {
  const lens = useLens();
  const navigate = useNavigate();
  const now = useNow(1000);
  const [story, setStory] = useState<HandoverStory | null>(null);
  const [failed, setFailed] = useState(false);
  const [form, setForm] = useState(lens.form);
  const closeRef = useRef<HTMLButtonElement>(null);
  const panel = useRef<HTMLElement>(null);
  // Fixed when the lens opens, so what is new stays marked while the analyst reads.
  const seenAt = useMemo(() => lens.lastSeen(satNo), [satNo]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => setForm(lens.form), [lens.form, satNo]);
  useEffect(() => {
    let live = true;
    setFailed(false);
    getHandoverStory(satNo)
      .then((s) => live && setStory(s))
      .catch(() => live && setFailed(true));
    return () => {
      live = false;
    };
  }, [satNo, lens.version]);
  useEffect(() => closeRef.current?.focus(), [satNo]);

  const onKeyDown = (e: KeyboardEvent<HTMLElement>) => {
    if (e.key !== "Tab" || !panel.current) return;
    const focusable = panel.current.querySelectorAll<HTMLElement>("button, input, textarea, [href]");
    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    if (e.shiftKey && document.activeElement === first) {
      e.preventDefault();
      last.focus();
    } else if (!e.shiftKey && document.activeElement === last) {
      e.preventDefault();
      first.focus();
    }
  };

  const known = lens.objects.get(String(satNo));
  const own = lens.notices.filter((n) => n.sat_ids.includes(String(satNo)));
  const rank = ["high", "medium", "low"];
  const urgency = rank.find((u) => own.some((n) => n.urgency === u)) ?? null;
  const open = own.some((n) => n.status === "OPEN");
  const parsed = story?.notices.map((n) => parseEventClass(n.event_class)).find((p) => p && p.objects.length > 1);
  const partner = parsed?.objects.find((o) => o.id && o.id !== String(satNo));
  const regime = story?.notices.map((n) => parseEventClass(n.event_class)?.regime).find(Boolean) ?? null;
  const next = story?.timers.find((t) => Date.parse(t.target_time) > now);
  const all = story ? items(story) : [];
  const fresh = all.filter((i) => i.at !== null && i.at > seenAt);
  const earlier = all.filter((i) => !(i.at !== null && i.at > seenAt));
  const watched = lens.watch.includes(satNo);
  const refreshed = () => {
    setForm(null);
    lens.changed();
    closeRef.current?.focus();
  };

  return (
    <>
      <div className="lx-scrim" onClick={lens.close} aria-hidden="true" />
      <aside ref={panel} className="lx-drawer" role="dialog" aria-modal="true" aria-labelledby="lx-title" onKeyDown={onKeyDown}>
        <header className="lx-head">
          <div className="lx-eyebrow">
            <span>Object lens</span>
            <button ref={closeRef} type="button" className="lx-close" onClick={lens.close} aria-label="Close the lens">
              <kbd>Esc</kbd> close
            </button>
          </div>
          <h2 id="lx-title" className="lx-title">
            {story?.name ?? known?.name ?? "Object"} <small>#{satNo}</small>
          </h2>
          <div className="lx-tags">
            {known?.kinds.map((k) => <span key={k} className="lx-tag kind">{k}</span>)}
            {partner?.id && <span className="lx-tag rpo">with <Linkify text={partner.id} /> {partner.name}</span>}
            {regime && <span className="lx-tag">{regime}</span>}
            {urgency && <span className={`lx-tag u-${urgency}`}>{urgency.toUpperCase()}</span>}
            {open && <span className="lx-tag open">OPEN</span>}
            <button type="button" className={`lx-tag lx-pin-btn${watched ? " on" : ""}`} aria-pressed={watched} onClick={() => lens.toggleWatch(satNo)}>
              {watched ? "★ On watch" : "☆ Pin to watch"}
            </button>
          </div>
        </header>
        <div className="lx-body">
          {failed && <p className="form-error" role="alert">Holly could not load this object's story.</p>}
          {!story && !failed && <p className="muted">Loading the story...</p>}
          {story && (
            <>
              {next ? (
                <div className="lx-next">
                  <b>{countdown(Date.parse(next.target_time) - now)}</b>
                  <span>
                    <span><Linkify text={next.label} /></span>
                    <em>Timer · due {stampUtc(Date.parse(next.target_time))}</em>
                  </span>
                </div>
              ) : (
                <div className="lx-next lx-next-none"><span>No timer set on this object.</span></div>
              )}
              <h3 className="lx-h"><span>Last 5 days, every source</span><span className="lx-seen-key">┆ you last looked {stampUtc(seenAt)}</span></h3>
              <Lanes story={story} now={now} seenAt={seenAt} />
              <h3 className="lx-h"><span>Since you last looked</span><span>{fresh.length} new</span></h3>
              {fresh.length === 0 ? <p className="lx-empty">Nothing new.</p> : <ul className="lx-list">{fresh.map((i) => <ItemRow key={i.key} item={i} fresh />)}</ul>}
              <h3 className="lx-h"><span>Before that</span><span>{earlier.length} items</span></h3>
              <ul className="lx-list">{earlier.map((i) => <ItemRow key={i.key} item={i} fresh={false} />)}</ul>
            </>
          )}
        </div>
        {form === "note" && <NoteForm satNo={satNo} done={refreshed} />}
        {form === "timer" && story && <TimerForm story={story} done={refreshed} />}
        <footer className="lx-acts">
          <button
            type="button"
            className="lx-btn pri"
            onClick={() => {
              sessionStorage.setItem("holly.proto.openSat", String(satNo));
              lens.close();
              navigate("/handover");
            }}
          >
            Open full story
          </button>
          <button type="button" className="lx-btn" aria-pressed={form === "note"} onClick={() => setForm(form === "note" ? null : "note")}>Add note</button>
          <button type="button" className="lx-btn" aria-pressed={form === "timer"} onClick={() => setForm(form === "timer" ? null : "timer")}>Set timer</button>
        </footer>
        <p className="lx-foot">Everything here is already in Holly; the lens reads it and sends nothing anywhere else. Prototype: "last looked" is kept in this browser.</p>
      </aside>
    </>
  );
}
