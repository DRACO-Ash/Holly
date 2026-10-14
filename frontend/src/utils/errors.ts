// The message to show an analyst when a request fails. Holly's API answers with a JSON body
// whose `detail` is written for people, so that wins; otherwise the error's own message,
// otherwise the caller's fallback.

interface ErrorWithResponse {
  response?: { status?: number; data?: { detail?: unknown } };
}

function responseOf(err: unknown): ErrorWithResponse["response"] {
  if (err && typeof err === "object" && "response" in err) {
    return (err as ErrorWithResponse).response;
  }
  return undefined;
}

export function errorStatus(err: unknown): number | undefined {
  return responseOf(err)?.status;
}

// A request made for a file receives its error body as a Blob too. Read that body back as
// JSON, so the server's own detail reaches the analyst rather than the bare status line; a
// body that is not JSON leaves the error as it was.
export async function withJsonErrorBody(err: unknown): Promise<unknown> {
  const response = responseOf(err) as { data?: unknown } | undefined;
  if (response && response.data instanceof Blob) {
    try {
      response.data = JSON.parse(await response.data.text());
    } catch {
      // Not JSON: keep the Blob.
    }
  }
  return err;
}

export function extractErrorMessage(err: unknown, fallback: string): string {
  const detail = responseOf(err)?.data?.detail;
  if (typeof detail === "string") return detail;
  if (err instanceof Error) return err.message;
  return fallback;
}
