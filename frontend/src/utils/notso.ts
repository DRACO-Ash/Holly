// The source artefacts a NOTSO lists. UDL carries them in msgBody.NOTSO_Image_Metadata as a
// JSON string (sometimes already an array). Everything in it is untrusted: only string fields
// are kept, and a link is offered only for a safe http or https URL.
import { safeHttpUrl } from "./links";

export interface NotsoArtefact {
  id?: string;
  filename?: string;
  caption?: string;
  url?: string;
  // The URL when it is safe to link to, otherwise null.
  href: string | null;
}

function text(value: unknown): string | undefined {
  return typeof value === "string" ? value : undefined;
}

function entriesOf(value: unknown): unknown[] {
  if (Array.isArray(value)) return value;
  if (typeof value !== "string") return [];
  try {
    const parsed: unknown = JSON.parse(value);
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function toArtefact(entry: unknown): NotsoArtefact | null {
  if (!entry || typeof entry !== "object") return null;
  const record = entry as Record<string, unknown>;
  const url = text(record.url);
  return {
    id: text(record.id),
    filename: text(record.filename),
    caption: text(record.caption),
    url,
    href: safeHttpUrl(url),
  };
}

export function parseArtefacts(raw: Record<string, unknown> | null | undefined): NotsoArtefact[] {
  const msgBody = raw?.["msgBody"];
  if (!msgBody || typeof msgBody !== "object") return [];
  const value = (msgBody as Record<string, unknown>)["NOTSO_Image_Metadata"];
  return entriesOf(value)
    .map(toArtefact)
    .filter((artefact): artefact is NotsoArtefact => artefact !== null);
}
