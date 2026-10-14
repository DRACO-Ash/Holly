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

export function extractErrorMessage(err: unknown, fallback: string): string {
  const detail = responseOf(err)?.data?.detail;
  if (typeof detail === "string") return detail;
  if (err instanceof Error) return err.message;
  return fallback;
}
