// Numbers become links: a catalogue number that names an object in the window, or a NOTSO number
// Holly holds, opens the Object Lens. Anything else stays text, and with the lens off (the Links
// switch, or outside the dashboard's frame) the text is exactly as before.
import type { MouseEvent } from "react";
import { useLens } from "../../context/lens";
import { linkParts } from "../../utils/lens";

function useOpener(satNo: number | null) {
  const lens = useLens();
  return (e: MouseEvent<HTMLButtonElement>) => {
    // A chip can sit inside a row that is itself a link or a button: only the chip acts.
    e.preventDefault();
    e.stopPropagation();
    if (satNo !== null) lens.open(satNo, e.currentTarget);
  };
}

export function SatChip({ id }: Readonly<{ id: string }>) {
  const lens = useLens();
  const known = lens.objects.get(id);
  const onClick = useOpener(known ? known.sat_no : null);
  if (!lens.enabled || !known) return <>{id}</>;
  return (
    <button
      type="button"
      className="lens-chip"
      onClick={onClick}
      aria-label={`Open the lens on ${known.name ?? "object"} ${id}`}
    >
      {id}
    </button>
  );
}

function NoticeChip({ notso }: Readonly<{ notso: string }>) {
  const lens = useLens();
  const first = lens.noticeByNotso.get(notso)?.sat_ids.find((s) => lens.objects.has(s));
  const onClick = useOpener(first ? Number(first) : null);
  if (!first) return <>{notso}</>;
  return (
    <button
      type="button"
      className="lens-chip lens-chip-notice"
      onClick={onClick}
      aria-label={`Open the lens on the object of notice ${notso}`}
    >
      {notso}
    </button>
  );
}

export function Linkify({ text }: Readonly<{ text: string }>) {
  const lens = useLens();
  if (!lens.enabled) return <>{text}</>;
  const parts = linkParts(
    text,
    (id) => lens.objects.has(id),
    (notso) => lens.noticeByNotso.has(notso),
  );
  if (parts.every((p) => p.kind === "text")) return <>{text}</>;
  return (
    <>
      {parts.map((p) => {
        if (p.kind === "sat") return <SatChip key={p.at} id={p.id} />;
        if (p.kind === "notice") return <NoticeChip key={p.at} notso={p.notso} />;
        return <span key={p.at}>{p.text}</span>;
      })}
    </>
  );
}
