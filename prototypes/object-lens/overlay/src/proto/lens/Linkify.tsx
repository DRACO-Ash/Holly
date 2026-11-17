// Numbers become links: a whole catalogue number that names an object in the window, or a NOTSO
// number Holly holds, opens the lens. Anything else, a clock time, a distance or a longer number,
// stays plain text. With the lens off, text is shown exactly as today.
import type { MouseEvent } from "react";
import { metric, useLens } from "./LensContext";

const TOKEN = /([0-9a-f]{4}_\d{1,2}[A-Z][a-z]{2}-\d{4}Z)|(\d+)/g;

export function SatChip({ id, label }: Readonly<{ id: string; label?: string }>) {
  const lens = useLens();
  const known = lens.objects.get(id);
  if (!lens.enabled || !known) return <>{label ?? id}</>;
  const onClick = (e: MouseEvent<HTMLButtonElement>) => {
    e.preventDefault();
    e.stopPropagation();
    metric("chip");
    lens.open(Number(id), e.currentTarget);
  };
  return (
    <button type="button" className="lx-chip" onClick={onClick} aria-label={`Open the lens on ${known.name ?? "object"} ${id}`}>
      {label ?? id}
    </button>
  );
}

function NoticeChip({ notso }: Readonly<{ notso: string }>) {
  const lens = useLens();
  const notice = lens.noticeByNotso.get(notso);
  const first = notice?.sat_ids.find((s) => lens.objects.has(s));
  if (!first) return <>{notso}</>;
  const onClick = (e: MouseEvent<HTMLButtonElement>) => {
    e.preventDefault();
    e.stopPropagation();
    metric("chip");
    lens.open(Number(first), e.currentTarget);
  };
  return (
    <button type="button" className="lx-chip lx-chip-notice" onClick={onClick} aria-label={`Open the lens on the object of notice ${notso}`}>
      {notso}
    </button>
  );
}

export function Linkify({ text }: Readonly<{ text: string }>) {
  const lens = useLens();
  if (!lens.enabled) return <>{text}</>;
  const parts: Array<string | { notso?: string; sat?: string; at: number }> = [];
  let last = 0;
  for (const m of text.matchAll(TOKEN)) {
    const at = m.index ?? 0;
    const linkable = m[1] ? lens.noticeByNotso.has(m[1]) : lens.objects.has(m[2]);
    if (!linkable) continue;
    if (at > last) parts.push(text.slice(last, at));
    parts.push(m[1] ? { notso: m[1], at } : { sat: m[2], at });
    last = at + m[0].length;
  }
  if (parts.length === 0) return <>{text}</>;
  if (last < text.length) parts.push(text.slice(last));
  return (
    <>
      {parts.map((p, i) =>
        typeof p === "string" ? (
          // eslint-disable-next-line react/no-array-index-key -- the pieces of one string never reorder
          <span key={i}>{p}</span>
        ) : p.notso ? (
          <NoticeChip key={p.at} notso={p.notso} />
        ) : (
          <SatChip key={p.at} id={p.sat as string} />
        ),
      )}
    </>
  );
}
