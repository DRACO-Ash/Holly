import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { listChannels, reviewAllChannels, sweepNow, updateChannel } from "../api/mattermost";
import ChannelConversation from "../components/comms/ChannelConversation";
import ChannelSwitchboard from "../components/comms/ChannelSwitchboard";
import CommsFeed from "../components/comms/CommsFeed";
import { type FeedScope, toggled } from "../components/comms/scope";
import SweepStrip from "../components/comms/SweepStrip";
import { useAuth } from "../context/AuthContext";
import type { MattermostChannel, MattermostChannels } from "../types";
import {
  type CommsView,
  channelLabel,
  loadLastSeen,
  loadView,
  plural,
  saveLastSeen,
  saveView,
  sweepSummary,
} from "../utils/comms";
import { extractErrorMessage } from "../utils/errors";

// The channel list is read again this often, as the server sweeps for the bot's channels.
export const CHANNELS_POLL_MS = 60_000;
// The width at and below which the console stacks, as tokens.css lays it out.
const NARROW = "(max-width: 760px)";

interface Undo {
  channel: MattermostChannel;
  following: boolean;
}

// On a narrow screen the stage sits below the channel list: bring it into view once a channel is
// picked, at once for anyone who asks the system for less motion.
function revealStage(stage: HTMLElement | null) {
  if (!stage || !window.matchMedia?.(NARROW).matches) return;
  const still = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  stage.scrollIntoView?.({ behavior: still ? "auto" : "smooth", block: "start" });
}

// The Comms console: every channel the bot can read, on the left, with a follow switch for each;
// on the right, either every followed channel in one feed under the last 24 hours of each, or one
// channel as a conversation.
export default function MattermostPage() {
  const { user } = useAuth();
  const [data, setData] = useState<MattermostChannels | null>(null);
  const [now, setNow] = useState(() => new Date());
  const [view, setView] = useState<CommsView>(loadView);
  const [scope, setScope] = useState<FeedScope>({ kind: "following" });
  const [selected, setSelected] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [sweeping, setSweeping] = useState(false);
  const [reviewing, setReviewing] = useState(false);
  const [notice, setNotice] = useState("");
  const [undo, setUndo] = useState<Undo | null>(null);
  const [error, setError] = useState<string | null>(null);
  // The channel list's own failure, cleared by the next read that succeeds.
  const [loadError, setLoadError] = useState<string | null>(null);
  // When this user last looked: undefined until it is read, null on a first visit. Read at once
  // when the user is already known, as after any move within the dashboard, so the channels are
  // asked for once.
  const [lastSeen, setLastSeen] = useState<string | null | undefined>(() =>
    user ? loadLastSeen(user.id) : undefined,
  );
  const seenSaved = useRef(false);
  const noticeRef = useRef<HTMLOutputElement | null>(null);
  const stageRef = useRef<HTMLElement | null>(null);

  // Each read is numbered, and only the latest one asked for may land: an answer to an earlier
  // read, for an earlier last visit say, arriving late changes nothing.
  const reads = useRef(0);
  const refresh = useCallback(async () => {
    const read = ++reads.current;
    try {
      const channels = await listChannels(lastSeen ?? undefined);
      if (read !== reads.current) return;
      setData(channels);
      setNow(new Date());
      setLoadError(null);
    } catch (err) {
      if (read === reads.current) {
        setLoadError(extractErrorMessage(err, "Failed to load the channels."));
      }
    }
  }, [lastSeen]);

  useEffect(() => {
    void refresh();
    const timer = window.setInterval(() => void refresh(), CHANNELS_POLL_MS);
    return () => window.clearInterval(timer);
  }, [refresh]);

  // Read once, then this visit becomes the last.
  useEffect(() => {
    if (!user || seenSaved.current) return;
    seenSaved.current = true;
    if (lastSeen === undefined) setLastSeen(loadLastSeen(user.id));
    saveLastSeen(user.id, new Date().toISOString());
  }, [user, lastSeen]);

  const channels = useMemo(() => data?.channels ?? [], [data]);
  const byId = useMemo(() => new Map(channels.map((c) => [c.mm_channel_id, c])), [channels]);
  const fresh = channels.filter((c) => c.is_new);
  // The conversation shows the channel chosen, or the first open one.
  const conversation =
    (selected ? byId.get(selected) : undefined) ?? channels.find((c) => c.status === "open");
  let selectedIds: string[] = [];
  if (view === "feed") selectedIds = scope.kind === "chosen" ? [...scope.ids] : [];
  else if (conversation) selectedIds = [conversation.mm_channel_id];

  function begin() {
    setNotice("");
    setUndo(null);
    setError(null);
  }

  function choose(next: CommsView) {
    setView(next);
    saveView(next);
  }

  function select(channelId: string) {
    if (view === "feed") setScope(toggled(scope, channelId));
    else setSelected(channelId);
    revealStage(stageRef.current);
  }

  function replace(updated: MattermostChannel) {
    setData((current) =>
      current
        ? {
            ...current,
            channels: current.channels.map((c) =>
              // A change answers with the channel alone; its count since the last visit stands.
              c.mm_channel_id === updated.mm_channel_id
                ? { ...updated, new_since: c.new_since }
                : c,
            ),
          }
        : current,
    );
  }

  async function follow(channel: MattermostChannel, following: boolean) {
    begin();
    setBusyId(channel.mm_channel_id);
    try {
      const updated = await updateChannel(channel.mm_channel_id, { following });
      replace(updated);
      setNotice(
        following
          ? `Following #${channelLabel(updated)} for everyone. Holly pulls its messages from the next cycle.`
          : `No longer following #${channelLabel(updated)}, for everyone. Holly keeps what it pulled.`,
      );
      setUndo({ channel: updated, following: !following });
    } catch (err) {
      setError(extractErrorMessage(err, "The channel could not be changed."));
    } finally {
      setBusyId(null);
    }
  }

  async function sweep() {
    begin();
    setSweeping(true);
    try {
      const result = await sweepNow();
      // A failed sweep is shown once, by the strip and the warning under it.
      if (result.ok !== false) setNotice(sweepSummary(result));
      await refresh();
    } catch (err) {
      setError(extractErrorMessage(err, "The sweep could not run."));
    } finally {
      setSweeping(false);
    }
  }

  async function review() {
    begin();
    setReviewing(true);
    try {
      const count = await reviewAllChannels();
      setNotice(`Marked ${plural(count, "channel")} reviewed.`);
      await refresh();
      // The banner and its button are gone: keep the keyboard where the news is.
      noticeRef.current?.focus();
    } catch (err) {
      setError(extractErrorMessage(err, "The channels could not be marked reviewed."));
    } finally {
      setReviewing(false);
    }
  }

  return (
    <div className="comms">
      <header className="comms-top">
        <div>
          <h1>Comms</h1>
          <p className="muted-paragraph">
            Team chat Holly pulls from Mattermost. The assistant reads it as soft context when it
            evaluates each NOTSO.
          </p>
        </div>
        <fieldset className="segmented">
          <legend className="visually-hidden">Layout</legend>
          <button type="button" aria-pressed={view === "feed"} onClick={() => choose("feed")}>
            Feed
          </button>
          <button
            type="button"
            aria-pressed={view === "channels"}
            onClick={() => choose("channels")}
          >
            Channels
          </button>
        </fieldset>
      </header>

      {data && (
        <SweepStrip sweep={data.sweep} sweeping={sweeping} onSweep={() => void sweep()} now={now} />
      )}
      {data?.sweep.ok === false && data.sweep.problem && (
        <div className="form-error" role="alert">
          The last channel sweep failed: {data.sweep.problem}{" "}
          {data.sweep.configured
            ? "Holly keeps pulling the channels it already knows."
            : "Holly pulls nothing until both are set."}
        </div>
      )}
      {fresh.length > 0 && (
        <div className="comms-banner">
          <p>
            {fresh.length === 1 ? "A new channel was" : `${fresh.length} new channels were`} found
            and followed: {fresh.map((c) => `#${channelLabel(c)}`).join(", ")}. Switch off any you
            do not want.
          </p>
          <button
            type="button"
            aria-disabled={reviewing || undefined}
            onClick={() => {
              if (!reviewing) void review();
            }}
          >
            {reviewing ? "Marking..." : "Mark reviewed"}
          </button>
        </div>
      )}
      <div className="comms-notice-row">
        <output className="comms-notice" ref={noticeRef} tabIndex={-1}>
          {notice}
        </output>
        {undo && (
          <button
            type="button"
            className="comms-undo"
            onClick={() => void follow(undo.channel, undo.following)}
          >
            Undo
          </button>
        )}
      </div>
      {loadError && (
        <div className="form-error" role="alert">
          {loadError}
        </div>
      )}
      {error && (
        <div className="form-error" role="alert">
          {error}
        </div>
      )}

      {data === null && !loadError && <p className="muted">Loading channels...</p>}
      {data && (
        <div className={`comms-console view-${view}`}>
          <ChannelSwitchboard
            channels={channels}
            selectedIds={selectedIds}
            picking={view === "feed"}
            busyId={busyId}
            onSelect={select}
            onFollow={(channel, on) => void follow(channel, on)}
            now={now}
          />
          <section
            className="comms-stage"
            aria-label={view === "feed" ? "Feed" : "Conversation"}
            ref={stageRef}
          >
            {view === "feed" && (
              <CommsFeed
                channels={channels}
                scope={scope}
                onScope={setScope}
                lastSeen={lastSeen ?? null}
                now={now}
              />
            )}
            {view === "channels" && conversation && (
              <ChannelConversation
                key={conversation.mm_channel_id}
                channel={conversation}
                channels={channels}
                busy={busyId === conversation.mm_channel_id}
                onFollow={(channel, on) => void follow(channel, on)}
                lastSeen={lastSeen ?? null}
                now={now}
              />
            )}
            {view === "channels" && !conversation && (
              <p className="muted">
                No channel yet. Holly finds the bot&apos;s channels every cycle; add the bot to a
                channel and it appears here.
              </p>
            )}
          </section>
        </div>
      )}
    </div>
  );
}
