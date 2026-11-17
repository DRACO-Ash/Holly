// The lens's pieces in Holly's frame: the Find button in the header, the watch strip above every
// page, and the layer that holds the open lens or palette.
import { useEffect, useState } from "react";
import { getHandoverStory } from "../../api/handover";
import { useNow } from "../../components/ops/useNow";
import type { HandoverStory } from "../../types";
import { storyEntries } from "../../utils/handover";
import LensDrawer from "./LensDrawer";
import { useLens } from "./LensContext";
import Palette from "./Palette";

export function FindButton() {
  const lens = useLens();
  if (!lens.enabled) return null;
  return (
    <button type="button" className="lx-find" onClick={lens.openPalette} aria-keyshortcuts="Control+K /">
      Find <kbd>Ctrl K</kbd>
    </button>
  );
}

function short(ms: number): string {
  const m = Math.max(0, Math.round(ms / 60_000));
  return `${Math.floor(m / 60)}:${String(m % 60).padStart(2, "0")}`;
}

export function WatchStrip() {
  const lens = useLens();
  const now = useNow(15_000);
  const [stories, setStories] = useState<Record<number, HandoverStory>>({});
  useEffect(() => {
    if (!lens.enabled) return;
    let live = true;
    lens.watch.forEach((sat) => {
      void getHandoverStory(sat).then((s) => live && setStories((prev) => ({ ...prev, [sat]: s })));
    });
    return () => {
      live = false;
    };
  }, [lens.enabled, lens.watch, lens.version, lens.satNo]);
  if (!lens.enabled || lens.watch.length === 0) return null;
  return (
    <div className="lx-watch" role="region" aria-label="Objects on watch">
      <b>ON WATCH</b>
      {lens.watch.map((sat) => {
        const s = stories[sat];
        const seen = lens.lastSeen(sat);
        const fresh = s ? storyEntries(s).filter((e) => e.at !== null && e.at > seen).length + s.suggestions.filter((x) => Date.parse(x.first_post.posted_at) > seen).length : 0;
        const next = s?.timers.find((t) => Date.parse(t.target_time) > now);
        return (
          <span key={sat} className={`lx-pin${fresh > 0 ? " hot" : ""}`}>
            <button type="button" className="lx-pin-open" onClick={(e) => lens.open(sat, e.currentTarget)}>
              {sat} {s?.name ?? ""}
              {fresh > 0 && <i> {fresh} new</i>}
              {next && <i> ⏱ {short(Date.parse(next.target_time) - now)}</i>}
              {s && fresh === 0 && !next && <span className="lx-quiet"> quiet</span>}
            </button>
            <button type="button" className="lx-pin-x" aria-label={`Stop watching ${sat}`} onClick={() => lens.toggleWatch(sat)}>×</button>
          </span>
        );
      })}
      <span className="lx-watch-hint">Ctrl K or / to find anything</span>
    </div>
  );
}

export function LensLayer() {
  const lens = useLens();
  if (!lens.enabled) return null;
  return (
    <>
      {lens.satNo !== null && <LensDrawer key={lens.satNo} satNo={lens.satNo} />}
      {lens.paletteOpen && <Palette />}
    </>
  );
}
