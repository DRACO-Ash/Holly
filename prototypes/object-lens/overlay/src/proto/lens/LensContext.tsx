// The Object Lens prototype's shared state: whether the lens is on (the hallway test switches it),
// which object's lens is open, the find palette, the objects and notices Holly can link, the
// watch list and when each object was last looked at. The last two live in this browser only.
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { getActivity } from "../../api/activity";
import { getHandoverObjects } from "../../api/handover";
import type { ActivityNotice, HandoverObject } from "../../types";

export type LensForm = "note" | "timer" | null;

export interface LensState {
  enabled: boolean;
  setEnabled: (on: boolean) => void;
  satNo: number | null;
  form: LensForm;
  open: (satNo: number, opener?: Element | null, form?: LensForm) => void;
  close: () => void;
  paletteOpen: boolean;
  openPalette: () => void;
  closePalette: () => void;
  closeAll: () => void;
  objects: ReadonlyMap<string, HandoverObject>;
  notices: readonly ActivityNotice[];
  noticeByNotso: ReadonlyMap<string, ActivityNotice>;
  watch: readonly number[];
  toggleWatch: (satNo: number) => void;
  lastSeen: (satNo: number) => number;
  markSeen: (satNo: number) => void;
  version: number;
  changed: () => void;
}

const LensContext = createContext<LensState | null>(null);

export const metric = (name: "lens" | "palette" | "chip") =>
  globalThis.dispatchEvent(new CustomEvent("proto-metric", { detail: name }));

const ENABLED_KEY = "holly.proto.lens";
const WATCH_KEY = "holly.proto.watch";
const SEEN_KEY = "holly.proto.seen";
// Before an object's lens has ever been opened in this browser, "since you last looked" starts
// 4 hours back, standing in for the start of the analyst's shift.
const FIRST_LOOK = Date.now() - 4 * 3_600_000;

function read<T>(key: string, fallback: T): T {
  try {
    const raw = localStorage.getItem(key);
    return raw === null ? fallback : (JSON.parse(raw) as T);
  } catch {
    return fallback;
  }
}

function write(key: string, value: unknown): void {
  try {
    localStorage.setItem(key, JSON.stringify(value));
  } catch {
    // Storage refused: the prototype carries on without remembering.
  }
}

const editable = (target: EventTarget | null) =>
  target instanceof HTMLElement &&
  (target.isContentEditable || ["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName));

export function LensProvider({ children }: Readonly<{ children: ReactNode }>) {
  const [enabled, setEnabledState] = useState<boolean>(() => read(ENABLED_KEY, true));
  const [satNo, setSatNo] = useState<number | null>(null);
  const [form, setForm] = useState<LensForm>(null);
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [objects, setObjects] = useState<ReadonlyMap<string, HandoverObject>>(new Map());
  const [notices, setNotices] = useState<readonly ActivityNotice[]>([]);
  const [watch, setWatch] = useState<number[]>(() => read(WATCH_KEY, []));
  const [seen, setSeen] = useState<Record<string, number>>(() => read(SEEN_KEY, {}));
  const [version, setVersion] = useState(0);
  const opener = useRef<Element | null>(null);

  const setEnabled = useCallback((on: boolean) => {
    setEnabledState(on);
    write(ENABLED_KEY, on);
    if (!on) {
      setSatNo(null);
      setPaletteOpen(false);
    }
  }, []);

  useEffect(() => {
    if (!enabled) return undefined;
    let live = true;
    const load = () => {
      void getHandoverObjects().then((list) => {
        if (live) setObjects(new Map(list.objects.map((o) => [String(o.sat_no), o])));
      });
      void getActivity().then((overview) => {
        if (live) setNotices(overview.notices);
      });
    };
    load();
    const id = globalThis.setInterval(load, 60_000);
    return () => {
      live = false;
      globalThis.clearInterval(id);
    };
  }, [enabled, version]);

  const noticeByNotso = useMemo(
    () => new Map(notices.filter((n) => n.notice).map((n) => [n.notice as string, n])),
    [notices],
  );

  const open = useCallback((sat: number, from?: Element | null, withForm: LensForm = null) => {
    if (from !== undefined) opener.current = from ?? (document.activeElement as Element | null);
    setPaletteOpen(false);
    setSatNo(sat);
    setForm(withForm);
    metric("lens");
  }, []);

  const lastSeen = useCallback((sat: number) => seen[String(sat)] ?? FIRST_LOOK, [seen]);
  const markSeen = useCallback((sat: number) => {
    setSeen((prev) => {
      const next = { ...prev, [String(sat)]: Date.now() };
      write(SEEN_KEY, next);
      return next;
    });
  }, []);

  const close = useCallback(() => {
    if (satNo !== null) markSeen(satNo);
    setSatNo(null);
    setForm(null);
    const back = opener.current;
    opener.current = null;
    if (back instanceof HTMLElement && document.contains(back)) back.focus();
  }, [satNo, markSeen]);

  const openPalette = useCallback(() => {
    opener.current = document.activeElement;
    setPaletteOpen(true);
    metric("palette");
  }, []);
  const closePalette = useCallback(() => {
    setPaletteOpen(false);
    const back = opener.current;
    if (back instanceof HTMLElement && document.contains(back)) back.focus();
  }, []);
  const closeAll = useCallback(() => {
    setSatNo(null);
    setForm(null);
    setPaletteOpen(false);
  }, []);

  const toggleWatch = useCallback((sat: number) => {
    setWatch((prev) => {
      const next = prev.includes(sat) ? prev.filter((x) => x !== sat) : [...prev, sat];
      write(WATCH_KEY, next);
      return next;
    });
  }, []);

  const changed = useCallback(() => setVersion((v) => v + 1), []);

  useEffect(() => {
    if (!enabled) return undefined;
    const onKey = (e: KeyboardEvent) => {
      // Esc closes the palette, else the lens, wherever focus has gone.
      if (e.key === "Escape" && (paletteOpen || satNo !== null)) {
        e.preventDefault();
        if (paletteOpen) closePalette();
        else close();
      } else if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        openPalette();
      } else if (e.key === "/" && !editable(e.target) && !paletteOpen) {
        e.preventDefault();
        openPalette();
      }
    };
    globalThis.addEventListener("keydown", onKey);
    return () => globalThis.removeEventListener("keydown", onKey);
  }, [enabled, openPalette, paletteOpen, closePalette, close, satNo]);

  const value = useMemo<LensState>(
    () => ({
      enabled, setEnabled, satNo, form, open, close, paletteOpen, openPalette, closePalette, closeAll,
      objects, notices, noticeByNotso, watch, toggleWatch, lastSeen, markSeen, version, changed,
    }),
    [enabled, setEnabled, satNo, form, open, close, paletteOpen, openPalette, closePalette, closeAll,
      objects, notices, noticeByNotso, watch, toggleWatch, lastSeen, markSeen, version, changed],
  );
  return <LensContext.Provider value={value}>{children}</LensContext.Provider>;
}

export function useLens(): LensState {
  const lens = useContext(LensContext);
  if (!lens) throw new Error("useLens needs a LensProvider");
  return lens;
}
