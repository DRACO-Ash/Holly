// The screen effects each analyst can switch, as the Holly design document sets them: scanlines
// on, flicker off; and whether object numbers are links that open the Object Lens (on). The choice is kept in this browser only. A store that is blocked, full or
// holding anything unexpected falls back to the defaults, so the dashboard always renders.

export interface DisplayPrefs {
  scanlines: boolean;
  flicker: boolean;
  links: boolean;
}

export const DEFAULT_DISPLAY: Readonly<DisplayPrefs> = {
  scanlines: true,
  flicker: false,
  links: true,
};

export const DISPLAY_STORAGE_KEY = "holly.display";

type Store = Pick<Storage, "getItem" | "setItem">;

function browserStore(): Store | undefined {
  try {
    return typeof window === "undefined" ? undefined : window.localStorage;
  } catch {
    return undefined;
  }
}

export function loadDisplayPrefs(store: Store | undefined = browserStore()): DisplayPrefs {
  try {
    const raw = store?.getItem(DISPLAY_STORAGE_KEY);
    const saved: unknown = raw ? JSON.parse(raw) : null;
    if (typeof saved !== "object" || saved === null) return { ...DEFAULT_DISPLAY };
    const { scanlines, flicker, links } = saved as Record<string, unknown>;
    return {
      scanlines: typeof scanlines === "boolean" ? scanlines : DEFAULT_DISPLAY.scanlines,
      flicker: typeof flicker === "boolean" ? flicker : DEFAULT_DISPLAY.flicker,
      links: typeof links === "boolean" ? links : DEFAULT_DISPLAY.links,
    };
  } catch {
    return { ...DEFAULT_DISPLAY };
  }
}

export function saveDisplayPrefs(
  prefs: DisplayPrefs,
  store: Store | undefined = browserStore(),
): void {
  try {
    store?.setItem(
      DISPLAY_STORAGE_KEY,
      JSON.stringify({ scanlines: prefs.scanlines, flicker: prefs.flicker, links: prefs.links }),
    );
  } catch {
    // A blocked or full store keeps the choice for this page only.
  }
}
