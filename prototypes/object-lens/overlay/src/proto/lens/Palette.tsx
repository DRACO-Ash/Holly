// Find anything: one box, from any page, for objects, notices, chat and pages. Objects come first,
// because the question is usually about one. Keyboard first, as a combobox.
import { useEffect, useMemo, useRef, useState, type KeyboardEvent } from "react";
import { useNavigate } from "react-router-dom";
import { listEventTimers } from "../../api/event_timers";
import { listMattermostMessages } from "../../api/mattermost";
import type { EventTimer, MattermostMessage } from "../../types";
import { stampUtc } from "../../utils/ops";
import { useLens } from "./LensContext";

interface Result {
  id: string;
  group: "Objects" | "Notices" | "Chat" | "Pages" | "Do";
  icon: string;
  tone: string;
  title: string;
  sub: string;
  hint: string;
  run: (shift: boolean) => void;
}

const PAGES: Array<[string, string]> = [
  ["Dashboard", "/"], ["Notifications", "/notifications"], ["Maneuvers", "/maneuvers"], ["Comms", "/comms"],
  ["Handover", "/handover"], ["Procedures", "/procedures"], ["Shift log", "/shift-log"],
];

function ago(iso: string | null): string {
  if (!iso) return "time unknown";
  const h = Math.round((Date.now() - Date.parse(iso)) / 3_600_000);
  return h < 1 ? "within the hour" : `${h} h ago`;
}

function inTime(iso: string): string {
  const m = Math.round((Date.parse(iso) - Date.now()) / 60_000);
  return m < 60 ? `${m} min` : `${Math.floor(m / 60)} h ${String(m % 60).padStart(2, "0")} min`;
}

export default function Palette() {
  const lens = useLens();
  const navigate = useNavigate();
  const [q, setQ] = useState("");
  const [active, setActive] = useState(0);
  const [chat, setChat] = useState<MattermostMessage[]>([]);
  const [timers, setTimers] = useState<EventTimer[]>([]);
  const input = useRef<HTMLInputElement>(null);

  useEffect(() => input.current?.focus(), []);
  useEffect(() => {
    void listEventTimers().then((list) => setTimers(list.items));
  }, []);
  useEffect(() => {
    const term = q.trim();
    if (term.length < 3) {
      setChat([]);
      return undefined;
    }
    const id = globalThis.setTimeout(() => {
      void listMattermostMessages({ q: term, followed: true, limit: 4 }).then((page) => setChat(page.items));
    }, 180);
    return () => globalThis.clearTimeout(id);
  }, [q]);

  const results = useMemo<Result[]>(() => {
    const term = q.trim().toLowerCase();
    if (!term) {
      return PAGES.map(([label, to]) => ({
        id: `page-${to}`, group: "Pages" as const, icon: "›", tone: "var(--color-text-muted)", title: label,
        sub: "Go to page", hint: "go", run: () => navigate(to),
      }));
    }
    const objects = [...lens.objects.values()]
      .filter((o) => String(o.sat_no).includes(term) || (o.name ?? "").toLowerCase().includes(term) || o.kinds.some((k) => k.toLowerCase().includes(term)))
      .slice(0, 4)
      .map<Result>((o) => {
        const own = lens.notices.filter((n) => n.sat_ids.includes(String(o.sat_no)));
        const open = own.filter((n) => n.status === "OPEN");
        const urgent = ["high", "medium", "low"].find((u) => open.some((n) => n.urgency === u));
        const timer = timers
          .filter((t) => t.label.includes(String(o.sat_no)) && Date.parse(t.target_time) > Date.now())
          .sort((a, b) => Date.parse(a.target_time) - Date.parse(b.target_time))[0];
        const bits = [
          `${open.length} open NOTSO${open.length === 1 ? "" : "s"}${urgent ? ` (${o.kinds.join(", ")}, ${urgent.toUpperCase()})` : ""}`,
          `${o.maneuvers} provider record${o.maneuvers === 1 ? "" : "s"}`,
          timer ? `timer in ${inTime(timer.target_time)}` : null,
          `latest ${ago(o.latest_at)}`,
        ].filter(Boolean);
        return {
          id: `obj-${o.sat_no}`, group: "Objects", icon: "◆", tone: "var(--kind-rpo)",
          title: `${o.name ?? "Object"} #${o.sat_no}`, sub: bits.join(" · "), hint: "↵ lens",
          run: (shift) => (shift ? lens.toggleWatch(o.sat_no) : lens.open(o.sat_no, null)),
        };
      });
    const notices = lens.notices
      .filter((n) => (n.notice ?? "").toLowerCase().includes(term) || (n.event_class ?? "").toLowerCase().includes(term))
      .slice(0, 3)
      .map<Result>((n) => ({
        id: `n-${n.id}`, group: "Notices", icon: "▣", tone: "var(--amber)", title: `${n.notice ?? "Notice"} · ${n.event_class ?? ""}`,
        sub: `${n.status ?? ""} · ${n.urgency.toUpperCase()} · ${n.udl_created_at ? stampUtc(Date.parse(n.udl_created_at)) : ""}`,
        hint: "open", run: () => navigate(`/notifications/${n.id}`),
      }));
    const messages = chat.map<Result>((m) => {
      const sat = (m.message.match(/\d+/g) ?? []).find((d) => lens.objects.has(d));
      return {
        id: `m-${m.id}`, group: "Chat", icon: "■", tone: "var(--channel-1)", title: `"${m.message}"`,
        sub: `${m.user_display_name ?? m.user_id} · #${m.channel_name ?? "channel"} · ${stampUtc(Date.parse(m.posted_at))}`,
        hint: sat ? "lens" : "comms", run: () => (sat ? lens.open(Number(sat), null) : navigate("/comms")),
      };
    });
    const pages = PAGES.filter(([label]) => label.toLowerCase().startsWith(term)).map<Result>(([label, to]) => ({
      id: `page-${to}`, group: "Pages", icon: "›", tone: "var(--color-text-muted)", title: label, sub: "Go to page", hint: "go", run: () => navigate(to),
    }));
    const top = objects[0];
    const actions: Result[] = top
      ? [{
          id: "do-timer", group: "Do", icon: "＋", tone: "var(--color-accent)", title: `Set a timer on ${top.title}`, sub: "Opens the lens with the timer form",
          hint: "do", run: () => lens.open(Number(top.id.slice(4)), null, "timer"),
        }]
      : [];
    return [...objects, ...notices, ...messages, ...pages, ...actions];
  }, [q, lens, chat, timers, navigate]);

  useEffect(() => setActive(0), [q]);
  const choose = (r: Result | undefined, shift: boolean) => {
    if (!r) return;
    if (!(shift && r.group === "Objects")) lens.closePalette();
    r.run(shift);
  };
  const onKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setActive((i) => Math.min(results.length - 1, i + 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActive((i) => Math.max(0, i - 1));
    } else if (e.key === "Enter") {
      e.preventDefault();
      choose(results[active], e.shiftKey);
    }
  };

  let group = "";
  return (
    <>
      <div className="lx-scrim" onClick={lens.closePalette} aria-hidden="true" />
      <div className="lx-pal" role="dialog" aria-modal="true" aria-label="Find anything">
        <input
          ref={input}
          value={q}
          onChange={(e) => setQ(e.target.value)}
          onKeyDown={onKeyDown}
          placeholder="Find an object, notice, message or page"
          role="combobox"
          aria-expanded="true"
          aria-controls="lx-pal-list"
          aria-activedescendant={results[active] ? `lx-opt-${results[active].id}` : undefined}
          aria-autocomplete="list"
        />
        <div id="lx-pal-list" role="listbox" className="lx-pal-list">
          {results.length === 0 && <p className="lx-empty">Nothing in the window matches.</p>}
          {results.map((r, i) => {
            const heading = r.group !== group ? (group = r.group) : null;
            return (
              <div key={r.id} role="presentation">
                {heading && <div className="lx-grp" role="presentation">{heading}</div>}
                <div
                  id={`lx-opt-${r.id}`}
                  role="option"
                  aria-selected={i === active}
                  className={`lx-row${i === active ? " sel" : ""}`}
                  // Only a moving pointer selects, so a mouse resting where the palette opens
                  // never takes the keyboard's selection.
                  onMouseMove={() => i !== active && setActive(i)}
                  onClick={(e) => choose(r, e.shiftKey)}
                >
                  <span style={{ color: r.tone }} aria-hidden="true">{r.icon}</span>
                  <span><b>{r.title}</b><br /><small>{r.sub}</small></span>
                  <small className="lx-hint">{r.hint}</small>
                </div>
              </div>
            );
          })}
        </div>
        <div className="lx-keys">
          <span><kbd>↑</kbd><kbd>↓</kbd> move</span><span><kbd>↵</kbd> open</span><span><kbd>⇧↵</kbd> pin to watch</span><span><kbd>Esc</kbd> close</span>
        </div>
      </div>
    </>
  );
}
