// Find anything: one box, from any page, for objects, notices, chat and pages. Objects come first,
// because the question is usually about one. Keyboard first, as a combobox.
import { useCallback, useEffect, useMemo, useRef, useState, type KeyboardEvent } from "react";
import { useNavigate } from "react-router-dom";
import { listEventTimers } from "../../api/event_timers";
import { listMattermostMessages } from "../../api/mattermost";
import { useLens, type LensState } from "../../context/lens";
import { useFocusTrap, useOutsidePress } from "./useFocusTrap";
import type { EventTimer, HandoverObject, MattermostMessage } from "../../types";
import {
  firstObjectIn,
  matchNotices,
  matchObjects,
  namesNumber,
  noticesOf,
  topUrgency,
} from "../../utils/lens";
import { stampUtc } from "../../utils/ops";

type Group = "Objects" | "Notices" | "Chat" | "Pages" | "Do";

interface Result {
  id: string;
  group: Group;
  icon: string;
  tone: string;
  title: string;
  sub: string;
  hint: string;
  run: (shift: boolean) => void;
}

const PAGES: Array<[string, string]> = [
  ["Dashboard", "/"],
  ["Notifications", "/notifications"],
  ["Maneuvers", "/maneuvers"],
  ["Comms", "/comms"],
  ["Handover", "/handover"],
  ["Procedures", "/procedures"],
  ["Shift log", "/shift-log"],
];

const CHAT_MIN = 3;
const CHAT_DELAY_MS = 180;

function inTime(iso: string, now: number): string {
  const m = Math.max(0, Math.round((Date.parse(iso) - now) / 60_000));
  return m < 60 ? `${m} min` : `${Math.floor(m / 60)} h ${String(m % 60).padStart(2, "0")} min`;
}

function ago(iso: string | null, now: number): string {
  if (!iso) return "time unknown";
  const h = Math.round((now - Date.parse(iso)) / 3_600_000);
  return h < 1 ? "within the hour" : `${h} h ago`;
}

function plural(n: number, word: string): string {
  return `${n} ${word}${n === 1 ? "" : "s"}`;
}

function objectSub(o: HandoverObject, lens: LensState, timers: EventTimer[], now: number): string {
  const own = noticesOf(lens.notices, o.sat_no);
  const open = own.filter((n) => n.status === "OPEN");
  const urgency = topUrgency(own);
  const timer = timers
    .filter((t) => namesNumber(t.label, String(o.sat_no)) && Date.parse(t.target_time) > now)
    .sort((a, b) => Date.parse(a.target_time) - Date.parse(b.target_time))[0];
  return [
    open.length > 0 && urgency
      ? `${plural(open.length, "open NOTSO")} (${urgency.toUpperCase()})`
      : plural(open.length, "open NOTSO"),
    plural(o.maneuvers, "provider record"),
    timer ? `timer in ${inTime(timer.target_time, now)}` : null,
    `latest ${ago(o.latest_at, now)}`,
  ]
    .filter(Boolean)
    .join(" · ");
}

function pageResults(term: string, go: (to: string) => void): Result[] {
  return PAGES.filter(([label]) => label.toLowerCase().startsWith(term)).map(([label, to]) => ({
    id: `page-${to}`,
    group: "Pages",
    icon: "›",
    tone: "var(--color-text-muted)",
    title: label,
    sub: "Go to page",
    hint: "go",
    run: () => go(to),
  }));
}

function results(
  query: string,
  lens: LensState,
  chat: MattermostMessage[],
  timers: EventTimer[],
  go: (to: string) => void,
): Result[] {
  const term = query.trim().toLowerCase();
  if (!term) return pageResults("", go);
  const now = Date.now();
  const objects = matchObjects(lens.objects.values(), term).map<Result>((o) => ({
    id: `obj-${o.sat_no}`,
    group: "Objects",
    icon: "◆",
    tone: "var(--kind-rpo)",
    title: `${o.name ?? "Object"} #${o.sat_no}`,
    sub: objectSub(o, lens, timers, now),
    hint: "↵ lens",
    run: (shift) => (shift ? lens.toggleWatch(o.sat_no) : lens.open(o.sat_no, null)),
  }));
  const notices = matchNotices(lens.notices, term).map<Result>((n) => ({
    id: `notice-${n.id}`,
    group: "Notices",
    icon: "▣",
    tone: "var(--amber)",
    title: `${n.notice ?? "Notice"} · ${n.event_class ?? ""}`,
    sub: [
      n.status,
      n.urgency.toUpperCase(),
      n.udl_created_at && stampUtc(Date.parse(n.udl_created_at)),
    ]
      .filter(Boolean)
      .join(" · "),
    hint: "open",
    run: () => go(`/notifications/${n.id}`),
  }));
  const messages = chat.map<Result>((m) => {
    const sat = firstObjectIn(m.message, (id) => lens.objects.has(id));
    return {
      id: `chat-${m.id}`,
      group: "Chat",
      icon: "■",
      tone: "var(--channel-1)",
      title: `"${m.message}"`,
      sub: `${m.user_display_name ?? m.user_id} · #${m.channel_name ?? "channel"} · ${stampUtc(Date.parse(m.posted_at))}`,
      hint: sat ? "lens" : "comms",
      run: () => (sat ? lens.open(Number(sat), null) : go("/comms")),
    };
  });
  const top = objects[0];
  const actions: Result[] = top
    ? [
        {
          id: "do-timer",
          group: "Do",
          icon: "＋",
          tone: "var(--color-accent)",
          title: `Set a timer on ${top.title}`,
          sub: "Opens the lens with the timer form",
          hint: "do",
          run: () => lens.open(Number(top.id.slice(4)), null, "timer"),
        },
      ]
    : [];
  return [...objects, ...notices, ...messages, ...pageResults(term, go), ...actions];
}

export default function Palette() {
  const lens = useLens();
  const navigate = useNavigate();
  const [query, setQuery] = useState("");
  const [active, setActive] = useState(0);
  const [chat, setChat] = useState<MattermostMessage[]>([]);
  const [timers, setTimers] = useState<EventTimer[]>([]);
  const input = useRef<HTMLInputElement>(null);
  const panel = useRef<HTMLDialogElement>(null);
  useFocusTrap(panel);
  useOutsidePress(panel, lens.closePalette);

  useEffect(() => input.current?.focus(), []);
  useEffect(() => {
    listEventTimers()
      .then((list) => setTimers(list.items))
      .catch(() => setTimers([]));
  }, []);
  useEffect(() => {
    const term = query.trim();
    if (term.length < CHAT_MIN) {
      setChat([]);
      return undefined;
    }
    let live = true;
    const id = globalThis.setTimeout(() => {
      listMattermostMessages({ q: term, followed: true, limit: 4 })
        .then((page) => {
          if (live) setChat(page.items);
        })
        .catch(() => {
          if (live) setChat([]);
        });
    }, CHAT_DELAY_MS);
    return () => {
      live = false;
      globalThis.clearTimeout(id);
    };
  }, [query]);
  useEffect(() => setActive(0), [query]);

  const go = useCallback((to: string) => navigate(to), [navigate]);
  const list = useMemo(
    () => results(query, lens, chat, timers, go),
    [query, lens, chat, timers, go],
  );

  const choose = (r: Result | undefined, shift: boolean) => {
    if (!r) return;
    // Shift and Enter pins an object and leaves Find open for the next one.
    if (!(shift && r.group === "Objects")) lens.closePalette();
    r.run(shift);
  };
  const onKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setActive((i) => Math.min(list.length - 1, i + 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActive((i) => Math.max(0, i - 1));
    } else if (e.key === "Enter") {
      e.preventDefault();
      choose(list[active], e.shiftKey);
    }
  };

  const current = list[active];
  return (
    <>
      <div className="lens-scrim" aria-hidden="true" />
      <dialog
        open
        ref={panel}
        className="lens-palette"
        aria-modal="true"
        aria-label="Find anything"
      >
        <input
          ref={input}
          type="search"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={onKeyDown}
          placeholder="Find an object, notice, message or page"
          aria-label="Find an object, notice, message or page"
          aria-describedby="lens-palette-status"
          maxLength={200}
        />
        <p id="lens-palette-status" className="visually-hidden" aria-live="polite">
          {current
            ? `${plural(list.length, "result")}. Enter opens ${current.title}.`
            : "No results."}
        </p>
        <ul className="lens-palette-list" aria-label="Results">
          {list.length === 0 && <li className="lens-empty">Nothing in the window matches.</li>}
          {list.map((r, i) => (
            <li key={r.id}>
              {r.group !== list[i - 1]?.group && (
                <span className="lens-group" aria-hidden="true">
                  {r.group}
                </span>
              )}
              <button
                type="button"
                tabIndex={-1}
                aria-current={i === active ? "true" : undefined}
                className={`lens-option${i === active ? " active" : ""}`}
                // Only a moving pointer selects, so a mouse resting where Find opens never
                // takes the keyboard's selection.
                onMouseMove={() => i !== active && setActive(i)}
                onClick={(e) => choose(r, e.shiftKey)}
              >
                <span style={{ color: r.tone }} aria-hidden="true">
                  {r.icon}
                </span>
                <span>
                  <span className="visually-hidden">{r.group}: </span>
                  <b>{r.title}</b>
                  <br />
                  <small>{r.sub}</small>
                </span>
                <small className="lens-hint">{r.hint}</small>
              </button>
            </li>
          ))}
        </ul>
        <div className="lens-keys">
          <span>
            <kbd>↑</kbd>
            <kbd>↓</kbd> move
          </span>
          <span>
            <kbd>↵</kbd> open
          </span>
          <span>
            <kbd>⇧↵</kbd> pin to watch
          </span>
          <span>
            <kbd>Esc</kbd> close
          </span>
        </div>
      </dialog>
    </>
  );
}
