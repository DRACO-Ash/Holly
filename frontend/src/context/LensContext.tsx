// The Object Lens's provider: whether it is on (the Links switch), which object's lens is open,
// the Find palette, the objects and notices Holly can link, and the analyst's own watch list and
// "last looked" times from the server. The state's shape and its hook are in lens.ts.
import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { getActivity } from "../api/activity";
import { getHandoverObjects, getWatch, markSeen, setWatch } from "../api/handover";
import type { ActivityNotice, HandoverObject, HandoverObjectList, ObjectWatch } from "../types";
import { LensContext, type LensForm, type LensState } from "./lens";

const REFRESH_MS = 60_000;
const noop = () => undefined;

const byNumber = (list: HandoverObjectList) =>
  new Map(list.objects.map((o) => [String(o.sat_no), o]));

const editable = (target: EventTarget | null) =>
  target instanceof HTMLElement &&
  (target.isContentEditable || ["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName));

function refocus(element: Element | null): void {
  if (element instanceof HTMLElement && document.contains(element)) element.focus();
}

function upsert(rows: readonly ObjectWatch[], row: ObjectWatch): ObjectWatch[] {
  return [...rows.filter((r) => r.sat_no !== row.sat_no), row];
}

export function LensProvider({
  enabled,
  children,
}: Readonly<{ enabled: boolean; children: ReactNode }>) {
  const [satNo, setSatNo] = useState<number | null>(null);
  const [form, setForm] = useState<LensForm>(null);
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [objects, setObjects] = useState<ReadonlyMap<string, HandoverObject>>(new Map());
  const [notices, setNotices] = useState<readonly ActivityNotice[]>([]);
  const [watch, setWatchRows] = useState<readonly ObjectWatch[]>([]);
  const [watchCap, setWatchCap] = useState(0);
  const [watchError, setWatchError] = useState<string | null>(null);
  const [version, setVersion] = useState(0);
  const opener = useRef<Element | null>(null);

  useEffect(() => {
    if (!enabled) {
      setSatNo(null);
      setPaletteOpen(false);
      return undefined;
    }
    let live = true;
    const load = () => {
      getHandoverObjects()
        .then((list) => live && setObjects(byNumber(list)))
        .catch(noop);
      getActivity()
        .then((overview) => live && setNotices(overview.notices))
        .catch(noop);
      getWatch()
        .then((list) => {
          if (!live) return;
          setWatchRows(list.items);
          setWatchCap(list.cap);
        })
        .catch(noop);
    };
    load();
    const id = globalThis.setInterval(load, REFRESH_MS);
    return () => {
      live = false;
      globalThis.clearInterval(id);
    };
  }, [enabled, version]);

  const noticeByNotso = useMemo(
    () =>
      new Map(
        notices.flatMap((n): Array<[string, ActivityNotice]> => (n.notice ? [[n.notice, n]] : [])),
      ),
    [notices],
  );

  const open = useCallback((sat: number, from?: Element | null, withForm: LensForm = null) => {
    if (from !== undefined) opener.current = from ?? document.activeElement;
    setPaletteOpen(false);
    setSatNo(sat);
    setForm(withForm);
    setWatchError(null);
  }, []);

  const close = useCallback(() => {
    if (satNo !== null) {
      markSeen(satNo)
        .then((row) => setWatchRows((rows) => upsert(rows, row)))
        .catch(noop);
    }
    setSatNo(null);
    setForm(null);
    const back = opener.current;
    opener.current = null;
    refocus(back);
  }, [satNo]);

  const openPalette = useCallback(() => {
    opener.current = document.activeElement;
    setPaletteOpen(true);
  }, []);

  const closePalette = useCallback(() => {
    setPaletteOpen(false);
    refocus(opener.current);
  }, []);

  const toggleWatch = useCallback(
    (sat: number) => {
      const pinned = watch.some((r) => r.sat_no === sat && r.pinned);
      setWatchError(null);
      setWatch(sat, !pinned)
        .then((row) => setWatchRows((rows) => upsert(rows, row)))
        .catch(() =>
          setWatchError(
            pinned
              ? "Holly could not take that off watch. Try again in a moment."
              : `Holly could not put that on watch. At most ${watchCap || "a few"} objects can be on watch.`,
          ),
        );
    },
    [watch, watchCap],
  );

  const lastSeen = useCallback(
    (sat: number) => {
      const at = watch.find((r) => r.sat_no === sat)?.last_seen_at;
      return at ? Date.parse(at) : null;
    },
    [watch],
  );

  const changed = useCallback(() => setVersion((v) => v + 1), []);

  useEffect(() => {
    if (!enabled) return undefined;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape" && (paletteOpen || satNo !== null)) {
        e.preventDefault();
        if (paletteOpen) closePalette();
        else close();
      } else if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        openPalette();
      } else if (e.key === "/" && !paletteOpen && !editable(e.target)) {
        e.preventDefault();
        openPalette();
      }
    };
    globalThis.addEventListener("keydown", onKey);
    return () => globalThis.removeEventListener("keydown", onKey);
  }, [enabled, paletteOpen, satNo, openPalette, closePalette, close]);

  const value = useMemo<LensState>(
    () => ({
      enabled,
      satNo,
      form,
      open,
      close,
      paletteOpen,
      openPalette,
      closePalette,
      objects,
      notices,
      noticeByNotso,
      watch,
      watchCap,
      watchError,
      toggleWatch,
      lastSeen,
      version,
      changed,
    }),
    [
      enabled,
      satNo,
      form,
      open,
      close,
      paletteOpen,
      openPalette,
      closePalette,
      objects,
      notices,
      noticeByNotso,
      watch,
      watchCap,
      watchError,
      toggleWatch,
      lastSeen,
      version,
      changed,
    ],
  );
  return <LensContext.Provider value={value}>{children}</LensContext.Provider>;
}
