// The facilitator's console for the hallway test. It runs a participant through two halves of 5
// timed tasks, one half in today's Holly and one with the lens, alternating the order between
// participants, and records time, outcome, page changes, lens use and a 1 to 7 ease rating.
// Results stay in this browser until exported as CSV.
import { useCallback, useEffect, useRef, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { useNow } from "../../components/ops/useNow";
import { useLens } from "../lens/LensContext";
import { CONDITION_LABEL, TASKS, type Condition, type SetName } from "./tasks";

type Phase = "setup" | "ready" | "running" | "rate" | "between" | "done" | "explore";
type Outcome = "correct" | "wrong" | "gave up";

interface Session {
  participant: string;
  order: [Condition, Condition];
  half: 0 | 1;
  task: number;
  phase: Phase;
}

interface Row {
  participant: string;
  half: number;
  condition: Condition;
  set: SetName;
  task: number;
  question: string;
  outcome: Outcome;
  seconds: number;
  page_changes: number;
  lens_opens: number;
  palette_opens: number;
  chip_clicks: number;
  ease_1_to_7: number;
  started_at_utc: string;
}

const SESSION_KEY = "holly.proto.session";
const RESULTS_KEY = "holly.proto.results";
const SETS: [SetName, SetName] = ["A", "B"];

function load<T>(key: string, fallback: T): T {
  try {
    const raw = localStorage.getItem(key);
    return raw ? (JSON.parse(raw) as T) : fallback;
  } catch {
    return fallback;
  }
}
function save(key: string, value: unknown): void {
  try {
    localStorage.setItem(key, JSON.stringify(value));
  } catch {
    // Storage refused: results then live only until the page closes.
  }
}

const COLUMNS: Array<keyof Row> = [
  "participant", "half", "condition", "set", "task", "question", "outcome", "seconds", "page_changes",
  "lens_opens", "palette_opens", "chip_clicks", "ease_1_to_7", "started_at_utc",
];
const cell = (v: unknown) => {
  const s = String(v);
  return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
};

function exportCsv(rows: Row[]): void {
  const text = [COLUMNS.join(","), ...rows.map((r) => COLUMNS.map((c) => cell(r[c])).join(","))].join("\n");
  const url = URL.createObjectURL(new Blob([text], { type: "text/csv" }));
  const a = document.createElement("a");
  a.href = url;
  a.download = `holly-object-lens-hallway-test-${new Date().toISOString().slice(0, 10)}.csv`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

const median = (xs: number[]) => {
  if (xs.length === 0) return null;
  const s = [...xs].sort((a, b) => a - b);
  const m = Math.floor(s.length / 2);
  return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2;
};

function Summary({ rows }: Readonly<{ rows: Row[] }>) {
  const by = (c: Condition) => rows.filter((r) => r.condition === c);
  const line = (c: Condition) => {
    const rs = by(c);
    const t = median(rs.map((r) => r.seconds));
    const ease = median(rs.map((r) => r.ease_1_to_7));
    return (
      <tr key={c}>
        <td>{CONDITION_LABEL[c]}</td>
        <td>{rs.length}</td>
        <td>{rs.filter((r) => r.outcome === "correct").length}</td>
        <td>{t === null ? "none" : `${t.toFixed(0)} s`}</td>
        <td>{median(rs.map((r) => r.page_changes)) ?? "none"}</td>
        <td>{ease ?? "none"}</td>
      </tr>
    );
  };
  return (
    <table className="tc-table">
      <thead><tr><th>Condition</th><th>Tasks</th><th>Correct</th><th>Median time</th><th>Median page changes</th><th>Median ease</th></tr></thead>
      <tbody>{line("today")}{line("lens")}</tbody>
    </table>
  );
}

export default function TestConsole() {
  const lens = useLens();
  const navigate = useNavigate();
  const { pathname } = useLocation();
  const now = useNow(500);
  const [results, setResults] = useState<Row[]>(() => load(RESULTS_KEY, []));
  const participants = new Set(results.map((r) => r.participant));
  const [session, setSession] = useState<Session>(() =>
    load(SESSION_KEY, { participant: "", order: ["today", "lens"], half: 0, task: 0, phase: "setup" } as Session),
  );
  const [code, setCode] = useState(`P${participants.size + 1}`);
  const [lensFirst, setLensFirst] = useState(participants.size % 2 === 1);
  const [mini, setMini] = useState(false);
  const [showKey, setShowKey] = useState(false);
  const [outcome, setOutcome] = useState<Outcome | null>(null);
  const run = useRef({ start: 0, pages: 0, lens: 0, palette: 0, chip: 0, path: "/", seconds: 0, armed: false });

  const update = useCallback((next: Partial<Session>) => {
    setSession((prev) => {
      const s = { ...prev, ...next };
      save(SESSION_KEY, s);
      return s;
    });
  }, []);

  const condition = session.order[session.half];
  const set = SETS[session.half];
  const task = TASKS[set][session.task];

  useEffect(() => {
    if (session.phase === "explore") lens.setEnabled(true);
    else if (session.phase !== "setup" && session.phase !== "done") lens.setEnabled(condition === "lens");
  }, [session.phase, condition]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (session.phase !== "running") return;
    // Counting starts once the task's reset to the dashboard has landed.
    if (!run.current.armed) {
      if (pathname === "/") run.current.armed = true;
      return;
    }
    if (pathname !== run.current.path) {
      run.current.pages += 1;
      run.current.path = pathname;
    }
  }, [pathname, session.phase]);

  useEffect(() => {
    const onMetric = (e: Event) => {
      if (session.phase !== "running") return;
      const name = (e as CustomEvent<string>).detail;
      if (name === "lens") run.current.lens += 1;
      if (name === "palette") run.current.palette += 1;
      if (name === "chip") run.current.chip += 1;
    };
    globalThis.addEventListener("proto-metric", onMetric);
    return () => globalThis.removeEventListener("proto-metric", onMetric);
  }, [session.phase]);

  const start = () => {
    lens.closeAll();
    run.current = { start: Date.now(), pages: 0, lens: 0, palette: 0, chip: 0, path: "/", seconds: 0, armed: false };
    navigate("/");
    setShowKey(false);
    update({ phase: "running" });
  };
  const finish = (o: Outcome) => {
    run.current.seconds = Math.round((Date.now() - run.current.start) / 100) / 10;
    setOutcome(o);
    update({ phase: "rate" });
  };
  const rate = (ease: number) => {
    const row: Row = {
      participant: session.participant, half: session.half + 1, condition, set, task: task.n, question: task.question,
      outcome: outcome ?? "gave up", seconds: run.current.seconds, page_changes: run.current.pages,
      lens_opens: run.current.lens, palette_opens: run.current.palette, chip_clicks: run.current.chip,
      ease_1_to_7: ease, started_at_utc: new Date(run.current.start).toISOString(),
    };
    const next = [...results, row];
    setResults(next);
    save(RESULTS_KEY, next);
    lens.closeAll();
    if (session.task < 4) update({ task: session.task + 1, phase: "ready" });
    else if (session.half === 0) update({ half: 1, task: 0, phase: "between" });
    else update({ phase: "done" });
  };
  // A fresh participant gets a fresh world: no earlier participant's notes, timers, pins or
  // "last looked" times. The synthetic world is rebuilt by reloading the page.
  const fresh = (next: Session) => {
    save(SESSION_KEY, next);
    ["holly.proto.watch", "holly.proto.seen"].forEach((k) => localStorage.removeItem(k));
    globalThis.location.hash = "#/";
    globalThis.location.reload();
  };
  const begin = () => {
    const order: [Condition, Condition] = lensFirst ? ["lens", "today"] : ["today", "lens"];
    fresh({ participant: code.trim() || "P?", order, half: 0, task: 0, phase: "ready" });
  };
  const clear = () => {
    if (!globalThis.confirm("Delete every recorded result in this browser?")) return;
    setResults([]);
    save(RESULTS_KEY, []);
  };

  if (session.phase === "setup") {
    return (
      <div className="tc-modal" role="dialog" aria-modal="true" aria-labelledby="tc-title">
        <div className="tc-card">
          <p className="tc-eyebrow">Holly · Object Lens · hallway test</p>
          <h2 id="tc-title">Facilitator set-up</h2>
          <p>Each participant answers 5 questions twice: once in today's Holly and once with the lens, on a different object each time. Read each question aloud, press <b>Start task</b> as you finish reading, and mark the answer when they give it. Every name, number and message here is synthetic.</p>
          <div className="tc-fields">
            <label>Participant code<input value={code} onChange={(e) => setCode(e.target.value)} /></label>
            <fieldset>
              <legend>First half</legend>
              <label><input type="radio" checked={!lensFirst} onChange={() => setLensFirst(false)} /> Today's Holly first</label>
              <label><input type="radio" checked={lensFirst} onChange={() => setLensFirst(true)} /> Lens first</label>
            </fieldset>
          </div>
          <p className="tc-note">Alternate the order between participants. Suggested for {code}: {participants.size % 2 === 1 ? "lens first" : "today's Holly first"}.</p>
          <div className="tc-actions">
            <button type="button" className="lx-btn pri" onClick={begin}>Start session</button>
            <button type="button" className="lx-btn" onClick={() => update({ phase: "explore" })}>Explore freely, lens on</button>
          </div>
          <details>
            <summary>Answer key (facilitator only)</summary>
            {SETS.map((s) => (
              <div key={s}>
                <h3>Set {s}</h3>
                <ol>{TASKS[s].map((t) => <li key={t.n}>{t.question}<br /><span className="tc-key">{t.key}</span></li>)}</ol>
              </div>
            ))}
          </details>
          <details open={results.length > 0}>
            <summary>Results in this browser ({results.length} tasks, {participants.size} participants)</summary>
            <Summary rows={results} />
            <div className="tc-actions">
              <button type="button" className="lx-btn" disabled={results.length === 0} onClick={() => exportCsv(results)}>Export CSV</button>
              <button type="button" className="lx-btn" disabled={results.length === 0} onClick={clear}>Clear results</button>
            </div>
          </details>
        </div>
      </div>
    );
  }

  if (session.phase === "explore") {
    return (
      <button type="button" className="tc-pill" onClick={() => update({ phase: "setup" })}>
        Exploring, lens on · back to set-up
      </button>
    );
  }

  if (session.phase === "between" || session.phase === "done") {
    const mine = results.filter((r) => r.participant === session.participant);
    return (
      <div className="tc-modal" role="dialog" aria-modal="true" aria-labelledby="tc-title">
        <div className="tc-card">
          <p className="tc-eyebrow">{session.participant}</p>
          {session.phase === "between" ? (
            <>
              <h2 id="tc-title">Half 2: {CONDITION_LABEL[condition]}</h2>
              {condition === "lens" ? (
                <p className="tc-script">Read aloud: "Same Holly, one change. Object numbers are now links: click one to see everything about that object without leaving the page. Ctrl K, or the Find button, finds anything. Questions are about a different object now."</p>
              ) : (
                <p className="tc-script">Read aloud: "This is Holly as it is today, without the lens. Questions are about a different object now."</p>
              )}
              <button type="button" className="lx-btn pri" onClick={() => update({ phase: "ready" })}>Start half 2</button>
            </>
          ) : (
            <>
              <h2 id="tc-title">Session complete</h2>
              <Summary rows={mine} />
              <p className="tc-note">Ask: "What, if anything, would you change about the lens?" and note it beside the CSV.</p>
              <div className="tc-actions">
                <button type="button" className="lx-btn" onClick={() => exportCsv(results)}>Export all results (CSV)</button>
                <button type="button" className="lx-btn pri" onClick={() => fresh({ ...session, phase: "setup" })}>Next participant</button>
              </div>
            </>
          )}
        </div>
      </div>
    );
  }

  const seconds = session.phase === "running" ? Math.max(0, Math.floor((now - run.current.start) / 1000)) : run.current.seconds;
  const clock = `${String(Math.floor(seconds / 60)).padStart(2, "0")}:${String(Math.floor(seconds % 60)).padStart(2, "0")}`;
  if (mini) {
    return (
      <button type="button" className="tc-pill" onClick={() => setMini(false)}>
        Test · {session.participant} · {session.task + 1}/5 · {clock}
      </button>
    );
  }
  return (
    <section className="tc-panel" aria-label="Hallway test console">
      <header>
        <span>{session.participant} · half {session.half + 1} of 2 · {CONDITION_LABEL[condition]} · set {set} · task {session.task + 1} of 5</span>
        <button type="button" className="tc-min" onClick={() => setMini(true)} aria-label="Minimise the console">–</button>
      </header>
      <p className="tc-q">{task.question}</p>
      {session.phase === "ready" && (
        <div className="tc-actions"><button type="button" className="lx-btn pri" onClick={start}>Start task</button></div>
      )}
      {session.phase === "running" && (
        <>
          <p className="tc-clock">{clock}</p>
          <div className="tc-actions">
            <button type="button" className="lx-btn pri" onClick={() => finish("correct")}>Correct</button>
            <button type="button" className="lx-btn" onClick={() => finish("wrong")}>Wrong</button>
            <button type="button" className="lx-btn" onClick={() => finish("gave up")}>Gave up</button>
            <button type="button" className="lx-btn" aria-pressed={showKey} onClick={() => setShowKey(!showKey)}>Key</button>
          </div>
          {showKey && <p className="tc-key">{task.key}</p>}
        </>
      )}
      {session.phase === "rate" && (
        <>
          <p className="tc-note">Ask: "How easy was that, from 1, very hard, to 7, very easy?"</p>
          <div className="tc-scale" role="group" aria-label="Ease from 1 to 7">
            {[1, 2, 3, 4, 5, 6, 7].map((n) => (
              <button type="button" key={n} className="lx-btn" onClick={() => rate(n)}>{n}</button>
            ))}
          </div>
        </>
      )}
      <footer>
        <button type="button" className="tc-link" onClick={() => { if (globalThis.confirm("Abandon this session? Tasks already rated stay recorded.")) update({ phase: "setup" }); }}>
          Back to set-up
        </button>
      </footer>
    </section>
  );
}
