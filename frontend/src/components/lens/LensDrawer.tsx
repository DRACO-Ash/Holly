// The Object Lens: one object's story over whatever page is open. It reads the V0.19 story
// (/handover/objects/{sat_no}) and nothing else, so it shows only what Holly already shows.
import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { createEventTimer } from "../../api/event_timers";
import { addHandoverNote, getHandoverStory } from "../../api/handover";
import { useLens } from "../../context/lens";
import type { HandoverStory } from "../../types";
import {
  countdown,
  lensItems,
  noticesOf,
  splitBySeen,
  stripX,
  topUrgency,
  type LensItem,
} from "../../utils/lens";
import { parseEventClass, stampUtc } from "../../utils/ops";
import { useNow } from "../ops/useNow";
import { Linkify } from "./Linkify";
import { useFocusTrap, useOutsidePress } from "./useFocusTrap";

const H = 3_600_000;
const DAY = 24 * H;
const LOAD_FAILED = "Holly could not load this object's story. Try again in a moment.";
const SAVE_FAILED = "Holly could not save that. Try again in a moment.";

interface Mark {
  key: string;
  at: number;
  className: string;
  label: string;
}

function lanes(story: HandoverStory): Array<[string, Mark[]]> {
  const at = (iso: string | null) => (iso ? Date.parse(iso) : Number.NaN);
  const keep = (marks: Mark[]) => marks.filter((m) => Number.isFinite(m.at));
  const posts = story.threads.flatMap((t) => t.posts);
  return [
    [
      "NOTSO",
      keep(
        story.notices.map((n) => ({
          key: n.id,
          at: at(n.udl_created_at),
          className: "lens-mark diamond tone-notice",
          label: n.notice ?? "notice",
        })),
      ),
    ],
    [
      "Provider",
      keep(
        story.maneuvers.map((m) => ({
          key: m.id,
          at: at(m.event_start_time),
          className: "lens-mark tone-maneuver",
          label: m.source ?? "provider record",
        })),
      ),
    ],
    [
      "Chat",
      keep([
        ...posts.map((p) => ({
          key: p.post_id,
          at: at(p.posted_at),
          className: "lens-mark square tone-post",
          label: p.author ?? "post",
        })),
        ...story.suggestions.map((s) => ({
          key: `s-${s.thread_id}`,
          at: at(s.first_post.posted_at),
          className: "lens-mark square hollow",
          label: "suggested thread",
        })),
      ]),
    ],
    [
      "Notes",
      keep(
        story.notes.map((n) => ({
          key: n.id,
          at: at(n.created_at),
          className: "lens-mark square tone-note",
          label: n.author ?? "note",
        })),
      ),
    ],
    [
      "Timers",
      keep(
        story.timers.map((t) => ({
          key: t.id,
          at: at(t.target_time),
          className: "lens-mark diamond tone-note",
          label: t.label,
        })),
      ),
    ],
  ];
}

function Strip({
  story,
  now,
  seenAt,
}: Readonly<{ story: HandoverStory; now: number; seenAt: number | null }>) {
  const start = Date.parse(story.window_start);
  const future = story.timers.map((t) => Date.parse(t.target_time) + H).filter((t) => t > now);
  const end = Math.max(now + 6 * H, ...future);
  const left = (t: number) => ({ left: `${stripX(t, start, end)}%` });
  const days: number[] = [];
  for (let d = Math.ceil(start / DAY) * DAY; d < end; d += DAY) days.push(d);
  return (
    <div className="lens-strip" aria-hidden="true">
      {lanes(story).map(([name, marks]) => (
        <div className="lens-lane" key={name}>
          <span className="lens-lane-name">{name}</span>
          <div className="lens-track">
            {days.map((d) => (
              <span key={d} className="lens-tick" style={left(d)} />
            ))}
            {marks.map((m) => (
              <span key={m.key} className={m.className} style={left(m.at)} title={m.label} />
            ))}
            {seenAt !== null && <span className="lens-seen-line" style={left(seenAt)} />}
            <span className="lens-now" style={left(now)} />
          </div>
        </div>
      ))}
      <div className="lens-lane">
        <span />
        <div className="lens-axis">
          {days.map((d) => (
            <span key={d} style={left(d)}>
              {new Date(d).toUTCString().slice(5, 11)}
            </span>
          ))}
        </div>
      </div>
    </div>
  );
}

function ItemRow({ item, fresh }: Readonly<{ item: LensItem; fresh: boolean }>) {
  return (
    <li className="lens-item">
      <time>{item.at === null ? "time unknown" : stampUtc(item.at)}</time>
      <div>
        <p className="lens-item-title">
          <span className={`lens-src tone-${item.tone}`}>{item.tag}</span>
          <Linkify text={item.title} />
          {fresh && <span className="lens-new">NEW</span>}
        </p>
        {item.detail && (
          <p className="lens-item-detail">
            <Linkify text={item.detail} />
          </p>
        )}
        <p className="lens-item-source">Source: {item.source}</p>
      </div>
    </li>
  );
}

function NoteForm({ satNo, done }: Readonly<{ satNo: number; done: (failed: boolean) => void }>) {
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (!text.trim()) return;
    setBusy(true);
    try {
      await addHandoverNote(satNo, text.trim());
      done(false);
    } catch {
      setBusy(false);
      done(true);
    }
  };
  return (
    <form className="lens-form" onSubmit={(e) => void submit(e)}>
      <label htmlFor="lens-note">Note on this object</label>
      <textarea
        id="lens-note"
        rows={2}
        maxLength={4000}
        value={text}
        onChange={(e) => setText(e.target.value)}
      />
      <button type="submit" className="lens-btn primary" disabled={busy || !text.trim()}>
        Add note
      </button>
    </form>
  );
}

function TimerForm({
  story,
  done,
}: Readonly<{ story: HandoverStory; done: (failed: boolean) => void }>) {
  const [label, setLabel] = useState(`Check ${story.name ?? "object"} (${story.sat_no})`);
  const [minutes, setMinutes] = useState(60);
  const [busy, setBusy] = useState(false);
  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    try {
      await createEventTimer({
        label: label.trim(),
        target_time: new Date(Date.now() + minutes * 60_000).toISOString(),
        event_key: story.notices[0]?.event_key ?? null,
        pre_alert_minutes: 15,
      });
      done(false);
    } catch {
      setBusy(false);
      done(true);
    }
  };
  return (
    <form className="lens-form lens-form-row" onSubmit={(e) => void submit(e)}>
      <label>
        <span>Timer</span>
        <input value={label} maxLength={200} onChange={(e) => setLabel(e.target.value)} />
      </label>
      <label>
        <span>In minutes</span>
        <input
          type="number"
          min={1}
          max={2880}
          value={minutes}
          onChange={(e) => setMinutes(Number(e.target.value))}
        />
      </label>
      <button
        type="submit"
        className="lens-btn primary"
        disabled={busy || !label.trim() || Number.isNaN(minutes) || minutes < 1}
      >
        Set timer
      </button>
    </form>
  );
}

function Items({ items, seenAt }: Readonly<{ items: LensItem[]; seenAt: number | null }>) {
  if (seenAt === null) {
    return (
      <>
        <h3 className="lens-h">
          <span>Everything Holly holds</span>
          <span>first look</span>
        </h3>
        <ul className="lens-list">
          {items.map((i) => (
            <ItemRow key={i.key} item={i} fresh={false} />
          ))}
        </ul>
      </>
    );
  }
  const [fresh, earlier] = splitBySeen(items, seenAt);
  return (
    <>
      <h3 className="lens-h">
        <span>Since you last looked</span>
        <span>{fresh.length} new</span>
      </h3>
      {fresh.length === 0 ? (
        <p className="lens-empty">Nothing new.</p>
      ) : (
        <ul className="lens-list">
          {fresh.map((i) => (
            <ItemRow key={i.key} item={i} fresh />
          ))}
        </ul>
      )}
      <h3 className="lens-h">
        <span>Before that</span>
        <span>{earlier.length} items</span>
      </h3>
      <ul className="lens-list">
        {earlier.map((i) => (
          <ItemRow key={i.key} item={i} fresh={false} />
        ))}
      </ul>
    </>
  );
}

export default function LensDrawer({ satNo }: Readonly<{ satNo: number }>) {
  const lens = useLens();
  const navigate = useNavigate();
  const now = useNow(1000);
  const [story, setStory] = useState<HandoverStory | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [form, setForm] = useState(lens.form);
  // Fixed when the lens opens, so what is new stays marked while the analyst reads.
  const [seenAt] = useState(() => lens.lastSeen(satNo));
  const closeRef = useRef<HTMLButtonElement>(null);
  const panel = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    let live = true;
    getHandoverStory(satNo)
      .then((s) => {
        if (live) setStory(s);
      })
      .catch(() => {
        if (live) setError(LOAD_FAILED);
      });
    return () => {
      live = false;
    };
  }, [satNo, lens.version]);
  useEffect(() => closeRef.current?.focus(), []);

  // Focus stays in the lens while it is open; Esc is handled by the lens's provider.
  useFocusTrap(panel);
  // Find, when open over the lens, takes the press itself.
  const { paletteOpen, close } = lens;
  const pressedOutside = useCallback(() => {
    if (!paletteOpen) close();
  }, [paletteOpen, close]);
  useOutsidePress(panel, pressedOutside);

  const saved = (failed: boolean) => {
    if (failed) {
      setError(SAVE_FAILED);
      return;
    }
    setForm(null);
    setError(null);
    lens.changed();
    closeRef.current?.focus();
  };

  const known = lens.objects.get(String(satNo));
  const own = noticesOf(lens.notices, satNo);
  const urgency = topUrgency(own);
  const open = own.some((n) => n.status === "OPEN");
  const parsed = story?.notices.map((n) => parseEventClass(n.event_class));
  const partner = parsed
    ?.flatMap((p) => p?.objects ?? [])
    .find((o) => o.id && o.id !== String(satNo));
  const regime = parsed?.find((p) => p?.regime)?.regime ?? null;
  const next = story?.timers.find((t) => Date.parse(t.target_time) > now);
  const pinned = lens.watch.some((r) => r.sat_no === satNo && r.pinned);
  const toggleForm = (which: "note" | "timer") => setForm(form === which ? null : which);

  return (
    <>
      <div className="lens-scrim" aria-hidden="true" />
      <dialog
        open
        ref={panel}
        className="lens-drawer"
        aria-modal="true"
        aria-labelledby="lens-title"
      >
        <header className="lens-head">
          <div className="lens-eyebrow">
            <span>Object lens</span>
            <button
              ref={closeRef}
              type="button"
              className="lens-close"
              onClick={lens.close}
              aria-label="Close the lens"
            >
              <kbd>Esc</kbd> close
            </button>
          </div>
          <h2 id="lens-title" className="lens-title">
            {story?.name ?? known?.name ?? "Object"} <small>#{satNo}</small>
          </h2>
          <div className="lens-tags">
            {known?.kinds.map((k) => (
              <span key={k} className="lens-tag kind">
                {k}
              </span>
            ))}
            {partner?.id && (
              <span className="lens-tag kind">
                with <Linkify text={partner.id} /> {partner.name}
              </span>
            )}
            {regime && <span className="lens-tag">{regime}</span>}
            {urgency && (
              <span className={`lens-tag urgency-${urgency}`}>{urgency.toUpperCase()}</span>
            )}
            {open && <span className="lens-tag open">OPEN</span>}
            <button
              type="button"
              className={`lens-tag lens-pin-toggle${pinned ? " on" : ""}`}
              aria-pressed={pinned}
              onClick={() => lens.toggleWatch(satNo)}
            >
              {pinned ? "★ On watch" : "☆ Pin to watch"}
            </button>
          </div>
        </header>
        <div className="lens-body">
          {(error ?? lens.watchError) && (
            <p className="form-error" role="alert">
              {error ?? lens.watchError}
            </p>
          )}
          {!story && !error && <p className="muted">Loading the story...</p>}
          {story && (
            <>
              {next ? (
                <div className="lens-next">
                  <b>{countdown(Date.parse(next.target_time) - now)}</b>
                  <span>
                    <span>
                      <Linkify text={next.label} />
                    </span>
                    <em>Timer · due {stampUtc(Date.parse(next.target_time))}</em>
                  </span>
                </div>
              ) : (
                <div className="lens-next none">
                  <span>No timer set on this object.</span>
                </div>
              )}
              <h3 className="lens-h">
                <span>The window, every source</span>
                {seenAt !== null && (
                  <span className="lens-seen-key">┆ you last looked {stampUtc(seenAt)}</span>
                )}
              </h3>
              <Strip story={story} now={now} seenAt={seenAt} />
              {story.truncated && (
                <p className="console-truncated">
                  Holly holds more about this object than the lens carries: part of it is shown.
                </p>
              )}
              <Items items={lensItems(story)} seenAt={seenAt} />
            </>
          )}
        </div>
        {form === "note" && <NoteForm satNo={satNo} done={saved} />}
        {form === "timer" && story && <TimerForm story={story} done={saved} />}
        <footer className="lens-acts">
          <button
            type="button"
            className="lens-btn primary"
            onClick={() => {
              lens.close();
              navigate(`/handover?sat=${satNo}`);
            }}
          >
            Open full story
          </button>
          <button
            type="button"
            className="lens-btn"
            aria-pressed={form === "note"}
            onClick={() => toggleForm("note")}
          >
            Add note
          </button>
          <button
            type="button"
            className="lens-btn"
            aria-pressed={form === "timer"}
            onClick={() => toggleForm("timer")}
          >
            Set timer
          </button>
        </footer>
        <p className="lens-foot">
          Everything here is already in Holly; the lens reads it and sends nothing anywhere else.
        </p>
      </dialog>
    </>
  );
}
