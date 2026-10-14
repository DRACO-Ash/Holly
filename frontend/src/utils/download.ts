// Downloads from Holly's API. A plain link cannot carry the analyst's sign-in token, so files
// are fetched with it and handed to the browser to save under the name the server gave.

const EXTENDED_NAME = /filename\*=UTF-8''([^;]+)/i;
const QUOTED_NAME = /filename="([^"]*)"/i;
const BARE_NAME = /filename=([^;"]+)/i;

// The file name a Content-Disposition header names: the RFC 6266 UTF-8 form when present,
// otherwise the plain form, otherwise the fallback.
export function filenameFromDisposition(
  header: string | null | undefined,
  fallback: string,
): string {
  if (!header) return fallback;
  const extended = EXTENDED_NAME.exec(header);
  if (extended) {
    try {
      return decodeURIComponent(extended[1].trim());
    } catch {
      // A malformed escape: fall back to the plain form below.
    }
  }
  const plain = QUOTED_NAME.exec(header)?.[1] ?? BARE_NAME.exec(header)?.[1]?.trim();
  return plain || fallback;
}

export function saveBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  // Revoke after the click has been handled, so the browser has started the download.
  setTimeout(() => URL.revokeObjectURL(url), 0);
}
