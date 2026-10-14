// Links that arrive in data (a UDL record's NOTSO link or artefact URL) are untrusted. Only an
// absolute http or https URL may become a clickable link; anything else (javascript:, data:,
// a relative path) is shown as text.

const ALLOWED_PROTOCOLS = new Set(["http:", "https:"]);

export function safeHttpUrl(value: string | null | undefined): string | null {
  if (!value) return null;
  try {
    const url = new URL(value);
    return ALLOWED_PROTOCOLS.has(url.protocol) ? url.href : null;
  } catch {
    return null;
  }
}

// Every link that opens a new tab carries this, so the opened page cannot reach back into
// Holly's window or learn which Holly page linked to it.
export const NEW_TAB_REL = "noopener noreferrer";
