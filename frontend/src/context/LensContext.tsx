// The Object Lens's provider: whether it is on (the Links switch), which object's lens is open,
// the Find palette, the objects and notices Holly can link, and the analyst's own watch list and
// "last looked" times from the server. The state's shape and its hook are in lens.ts.
import { isAxiosError } from "axios";
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

// Why a pin or an unpin did not happen: the cap only when the server says so (409).
function watchRefusal(error: unknown, pinned: boolean, cap: number): string {
  if (pinned) return "Holly could not take that off watch. Try again in a moment.";
  if (isAxiosError(error) && error.response?.status === 409) {
    return `Holly could not put that on watch: at most ${cap} objects can be on watch. Take one off first.`;
  }
  return "Holly could not put that on watch. Try again in a moment.";
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
  // Where focus returns: the element that opened the lens while nothing was open, and the one
  // that opened Find. Switching objects inside the lens keeps the first.
  const lensOpener = useRef<Element | null>(null);
  const findOpener = useRef<Element | null>(null);

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

  // Leaving an object's lens, by closing it or by moving to another object, is a look at it.
  const markLook = useCallback((sat: number) => {
    markSeen(sat)
      .then((row) => setWatchRows((rows) => upsert(rows, row)))
      .catch(noop);
  }, []);

  const open = useCallback(
    (sat: number, from?: Element | null, withForm: LensForm = null) => {
      if (satNo === null) {
        lensOpener.current = paletteOpen ? findOpener.current : (from ?? document.activeElement);
      } else if (satNo !== sat) {
        markLook(satNo);
      }
      setPaletteOpen(false);
      setSatNo(sat);
      setForm(withForm);
      setWatchError(null);
    },
    [satNo, paletteOpen, markLook],
  );

  const close = useCallback(() => {
    if (satNo !== null) markLook(satNo);
    setSatNo(null);
    setForm(null);
    const back = lensOpener.current;
    lensOpener.current = null;
    refocus(back);
  }, [satNo, markLook]);

  const openPalette = useCallback(() => {
    if (!paletteOpen) findOpener.current = document.activeElement;
    setPaletteOpen(true);
  }, [paletteOpen]);

  const closePalette = useCallback(() => {
    setPaletteOpen(false);
    refocus(findOpener.current);
  }, []);

  const toggleWatch = useCallback(
    (sat: number) => {
      const pinned = watch.some((r) => r.sat_no === sat && r.pinned);
      setWatchError(null);
      setWatch(sat, !pinned)
        .then((row) => setWatchRows((rows) => upsert(rows, row)))
        .catch((error: unknown) => setWatchError(watchRefusal(error, pinned, watchCap)));
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
        return;
      }
      const find = (e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k";
      const slash = e.key === "/" && !paletteOpen && !editable(e.target);
      if (find || slash) {
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
