// The Object Lens's shared state, as every page reads it. Outside its provider (LensContext.tsx)
// the lens is off, and every page shows plain text, as before the lens.
import { createContext, useContext } from "react";
import type { ActivityNotice, HandoverObject, ObjectWatch } from "../types";

export type LensForm = "note" | "timer" | null;

export interface LensState {
  enabled: boolean;
  satNo: number | null;
  form: LensForm;
  open: (satNo: number, opener?: Element | null, form?: LensForm) => void;
  close: () => void;
  paletteOpen: boolean;
  openPalette: () => void;
  closePalette: () => void;
  objects: ReadonlyMap<string, HandoverObject>;
  notices: readonly ActivityNotice[];
  noticeByNotso: ReadonlyMap<string, ActivityNotice>;
  watch: readonly ObjectWatch[];
  watchCap: number;
  watchError: string | null;
  toggleWatch: (satNo: number) => void;
  lastSeen: (satNo: number) => number | null;
  version: number;
  changed: () => void;
}

const noop = () => undefined;

export const LENS_OFF: LensState = {
  enabled: false,
  satNo: null,
  form: null,
  open: noop,
  close: noop,
  paletteOpen: false,
  openPalette: noop,
  closePalette: noop,
  objects: new Map(),
  notices: [],
  noticeByNotso: new Map(),
  watch: [],
  watchCap: 0,
  watchError: null,
  toggleWatch: noop,
  lastSeen: () => null,
  version: 0,
  changed: noop,
};

export const LensContext = createContext<LensState>(LENS_OFF);

export const useLens = (): LensState => useContext(LensContext);
