// The Object Lens's pieces in Holly's frame: the Find button in the header, the watch strip above
// every page, and the layer that holds the open lens or Find.
import { useEffect, useState } from "react";
import { getHandoverStory } from "../../api/handover";
import { useLens } from "../../context/lens";
import type { HandoverStory } from "../../types";
import { lensItems } from "../../utils/lens";
import { useNow } from "../ops/useNow";
import LensDrawer from "./LensDrawer";
import Palette from "./Palette";

export function FindButton() {
  const lens = useLens();
  if (!lens.enabled) return null;
  return (
    <button
      type="button"
      className="lens-find"
      onClick={lens.openPalette}
      aria-keyshortcuts="Control+K Meta+K /"
    >
      Find <kbd>Ctrl K</kbd>
    </button>
  );
}

function hoursMinutes(ms: number): string {
  const m = Math.max(0, Math.round(ms / 60_000));
  return `${Math.floor(m / 60)}:${String(m % 60).padStart(2, "0")}`;
}

function WatchPin({
  satNo,
  story,
  now,
}: Readonly<{ satNo: number; story?: HandoverStory; now: number }>) {
  const lens = useLens();
  const seen = lens.lastSeen(satNo);
  const fresh =
    story && seen !== null
      ? lensItems(story).filter((i) => i.at !== null && i.at > seen).length
      : 0;
  const next = story?.timers.find((t) => Date.parse(t.target_time) > now);
  return (
    <span className={`lens-pin${fresh > 0 ? " hot" : ""}`}>
      <button
        type="button"
        className="lens-pin-open"
        onClick={(e) => lens.open(satNo, e.currentTarget)}
      >
        {satNo} {story?.name ?? ""}
        {fresh > 0 && <i> {fresh} new</i>}
        {next && <i> ⏱ {hoursMinutes(Date.parse(next.target_time) - now)}</i>}
        {story && fresh === 0 && !next && <span className="lens-quiet"> quiet</span>}
      </button>
      <button
        type="button"
        className="lens-pin-off"
        aria-label={`Stop watching ${satNo}`}
        onClick={() => lens.toggleWatch(satNo)}
      >
        ×
      </button>
    </span>
  );
}

function storiesFrom(
  answers: PromiseSettledResult<HandoverStory>[],
): Record<number, HandoverStory> {
  const out: Record<number, HandoverStory> = {};
  answers.forEach((a) => {
    if (a.status === "fulfilled") out[a.value.sat_no] = a.value;
  });
  return out;
}

export function WatchStrip() {
  const lens = useLens();
  const now = useNow(15_000);
  const [stories, setStories] = useState<Record<number, HandoverStory>>({});
  const pinned = lens.watch.filter((r) => r.pinned).map((r) => r.sat_no);
  const key = pinned.join(",");
  useEffect(() => {
    if (!lens.enabled || !key) return undefined;
    let live = true;
    Promise.allSettled(key.split(",").map((sat) => getHandoverStory(Number(sat))))
      .then((answers) => {
        if (live) setStories(storiesFrom(answers));
      })
      .catch(() => undefined);
    return () => {
      live = false;
    };
  }, [lens.enabled, key, lens.version, lens.satNo]);
  if (!lens.enabled || pinned.length === 0) return null;
  return (
    <div className="lens-watch" role="region" aria-label="Objects on watch">
      <b>ON WATCH</b>
      {pinned.map((sat) => (
        <WatchPin key={sat} satNo={sat} story={stories[sat]} now={now} />
      ))}
      <span className="lens-watch-hint">Ctrl K or / to find anything</span>
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
